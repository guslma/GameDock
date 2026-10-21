"""What is missing from the library, and notifications on the phone.

missing_content() lists, for every game in the library, the newest update you do not
have and the DLC you do not have, from the same data the library's yellow icons use.

A background thread (start(), in the web server process) looks at the database every
minute and sends a notification through ntfy, Telegram or Discord when:
- games, updates or DLC join the library,
- a new update or DLC becomes available for a game you have,
- a file fails verification,
- a background task fails.
Its settings and what it already reported live in config/gamedock.json.
"""

import datetime
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from constants import CONFIG_DIR, APP_TYPE_BASE, APP_TYPE_UPD, APP_TYPE_DLC

logger = logging.getLogger("main")
SYSTEM_FILE = Path(CONFIG_DIR) / "gamedock.json"
CHECK_EVERY = 60
_lock = threading.Lock()

EVENTS = ("new_content", "missing_content", "verification", "task_failed")
DEFAULTS = {
    "provider": "",
    "ntfy_url": "",
    "ntfy_token": "",
    "telegram_token": "",
    "telegram_chat": "",
    "discord_webhook": "",
    "events": {name: True for name in EVENTS},
}


# --- settings file ------------------------------------------------------------------------------

def _read():
    try:
        return json.loads(SYSTEM_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(data):
    SYSTEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SYSTEM_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)  # holds tokens
    tmp.replace(SYSTEM_FILE)


def get_notify_settings():
    saved = _read().get("notify", {})
    merged = {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}
    merged["events"] = {**DEFAULTS["events"], **saved.get("events", {})}
    return merged


def save_notify_settings(values):
    with _lock:
        data = _read()
        current = get_notify_settings()
        for key in DEFAULTS:
            if key == "events":
                current["events"] = {name: bool(values.get("events", {}).get(name, current["events"][name])) for name in EVENTS}
            elif key in values:
                current[key] = str(values[key] or "").strip()
        data["notify"] = current
        _write(data)


def _state():
    return _read().get("notify_state", {})


def _save_state(state):
    with _lock:
        data = _read()
        data["notify_state"] = state
        _write(data)


# --- what is missing ----------------------------------------------------------------------------

def _name(title_id, fallback):
    from titledb.store import get_title_record
    record = get_title_record(title_id) or {}
    return record.get("name") or fallback


def _date(value):
    if not value:
        return ""
    value = str(value).replace("-", "")
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}" if len(value) == 8 and value.isdigit() else str(value)


def missing_content():
    """[{title_id, name, update: {...} | None, dlc: [...]}] for the games you have."""
    from db import db
    rows = db.session.execute(db.text(
        "SELECT t.title_id, a.app_id, a.app_type, a.app_version, a.owned, a.release_date, a.display_version "
        "FROM titles t JOIN apps a ON a.title_id = t.id WHERE t.have_base = 1")).all()
    by_title = {}
    for title_id, app_id, app_type, version, owned, released, display in rows:
        by_title.setdefault(title_id, []).append({
            "app_id": app_id, "type": app_type, "version": int(version or 0), "owned": bool(owned),
            "released": released, "display": display})
    out = []
    for title_id, apps in by_title.items():
        updates = [a for a in apps if a["type"] == APP_TYPE_UPD]
        owned_updates = [a for a in updates if a["owned"]]
        update = None
        if updates:
            newest = max(updates, key=lambda a: a["version"])
            have = max(owned_updates, key=lambda a: a["version"]) if owned_updates else None
            if not have or have["version"] < newest["version"]:
                update = {
                    "version": newest["version"],
                    "number": newest["version"] // 65536,
                    "released": _date(newest["released"]),
                    "have_number": have["version"] // 65536 if have else 0,
                    "have_display": (have or {}).get("display") or "",
                }
        dlc_newest = {}
        for a in apps:
            if a["type"] == APP_TYPE_DLC and (a["app_id"] not in dlc_newest or a["version"] > dlc_newest[a["app_id"]]["version"]):
                dlc_newest[a["app_id"]] = a
        dlc = [{"app_id": d["app_id"], "name": _name(d["app_id"], d["app_id"]), "released": _date(d["released"])}
               for d in dlc_newest.values() if not d["owned"]]
        if update or dlc:
            out.append({"title_id": title_id, "name": _name(title_id, title_id), "update": update,
                        "dlc": sorted(dlc, key=lambda d: d["name"])})
    return sorted(out, key=lambda t: t["name"].lower())


# --- messages -----------------------------------------------------------------------------------

TEXTS = {
    "en": {
        "new_title": "New in the library", "missing_title": "New content available",
        "verify_title": "Verification failed", "task_title": "Task failed", "test_title": "GameDock",
        "test": "Notifications are working.", "game": "game", "update": "update", "dlc": "DLC",
        "update_n": "update {n} (released {date})", "verify_line": "{name}: the file is corrupted or modified",
        "and_more": "and {n} more",
    },
    "pt-BR": {
        "new_title": "Novo na biblioteca", "missing_title": "Novidade disponível",
        "verify_title": "Falha na verificação", "task_title": "Tarefa falhou", "test_title": "GameDock",
        "test": "Os avisos estão funcionando.", "game": "jogo", "update": "atualização", "dlc": "DLC",
        "update_n": "atualização {n} (lançada em {date})", "verify_line": "{name}: o arquivo está corrompido ou modificado",
        "and_more": "e mais {n}",
    },
    "es": {
        "new_title": "Nuevo en la biblioteca", "missing_title": "Novedad disponible",
        "verify_title": "Falló la verificación", "task_title": "Una tarea falló", "test_title": "GameDock",
        "test": "Los avisos funcionan.", "game": "juego", "update": "actualización", "dlc": "DLC",
        "update_n": "actualización {n} (publicada el {date})", "verify_line": "{name}: el archivo está dañado o modificado",
        "and_more": "y {n} más",
    },
}


def _texts():
    language = os.environ.get("GAMEDOCK_LANGUAGE", "en")
    return TEXTS.get(language) or TEXTS.get(language.split("-")[0]) or TEXTS["en"]


def _lines(items, limit=15):
    t = _texts()
    shown = items[:limit]
    if len(items) > limit:
        shown.append(t["and_more"].format(n=len(items) - limit))
    return "\n".join(shown)


def _click_url():
    try:
        from settings import get_settings
        host = (get_settings()["shop"].get("host") or "").strip().strip("/")
        return f"https://{host}" if host else ""
    except Exception:
        return ""


# --- sending ------------------------------------------------------------------------------------

def _post(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status


def send(title, message, settings=None):
    """Sends one notification. Returns None when it went out, else the error text."""
    s = settings or get_notify_settings()
    provider = s["provider"]
    try:
        if provider == "ntfy":
            parsed = urllib.parse.urlparse(s["ntfy_url"])
            topic = parsed.path.strip("/")
            if not parsed.scheme or not topic:
                return "invalid_ntfy_url"
            payload = {"topic": topic, "title": title, "message": message, "tags": ["video_game"]}
            if _click_url():
                payload["click"] = _click_url()
            headers = {"Authorization": f"Bearer {s['ntfy_token']}"} if s["ntfy_token"] else {}
            _post(f"{parsed.scheme}://{parsed.netloc}", payload, headers)
        elif provider == "telegram":
            if not s["telegram_token"] or not s["telegram_chat"]:
                return "missing_telegram"
            _post(f"https://api.telegram.org/bot{s['telegram_token']}/sendMessage",
                  {"chat_id": s["telegram_chat"], "text": f"{title}\n{message}"})
        elif provider == "discord":
            if not s["discord_webhook"].startswith("https://"):
                return "invalid_discord"
            _post(s["discord_webhook"], {"content": f"**{title}**\n{message}"})
        else:
            return "no_provider"
    except Exception as e:  # the service answered with an error or could not be reached
        return str(e)[:200]
    return None


# --- what changed since the last look -----------------------------------------------------------

def _new_files(state, texts):
    """Files that joined the library and are identified, grouped by game."""
    from db import db
    last = state.get("last_file_id")
    if last is None:
        state["last_file_id"] = db.session.execute(db.text("SELECT COALESCE(MAX(id), 0) FROM files")).scalar()
        return []
    rows = db.session.execute(db.text(
        "SELECT f.id, f.identified, f.added_at, a.app_type, a.app_version, a.app_id, a.display_version, t.title_id "
        "FROM files f LEFT JOIN app_files af ON af.file_id = f.id LEFT JOIN apps a ON a.id = af.app_id "
        "LEFT JOIN titles t ON t.id = a.title_id WHERE f.id > :last ORDER BY f.id"), {"last": last}).all()
    lines, newest = [], last
    recent = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    for fid, identified, added_at, app_type, version, app_id, display, title_id in rows:
        if not identified:
            added = added_at if isinstance(added_at, datetime.datetime) else None
            if added is None or added > recent:
                break  # still being identified: report it on a later look
            newest = fid
            continue
        newest = max(newest, fid)
        if not title_id:
            continue
        name = _name(title_id, title_id)
        if app_type == APP_TYPE_BASE:
            line = f"{name} ({texts['game']})"
        elif app_type == APP_TYPE_UPD:
            line = f"{name}: {texts['update']} {display or 'v' + str(version)}"
        else:
            line = f"{name}: {texts['dlc']} {_name(app_id, app_id)}"
        if line not in lines:
            lines.append(line)
    state["last_file_id"] = newest
    return lines


def _new_missing(state, texts):
    """Updates and DLC that became available since the last look."""
    current, lines = {}, []
    for title in missing_content():
        if title["update"]:
            key = f"{title['title_id']}:update:{title['update']['version']}"
            current[key] = f"{title['name']}: " + texts["update_n"].format(n=title["update"]["number"], date=title["update"]["released"] or "?")
        for d in title["dlc"]:
            current[f"{title['title_id']}:dlc:{d['app_id']}"] = f"{title['name']}: {texts['dlc']} {d['name']}"
    known = state.get("known_missing")
    if known is not None:
        lines = [text for key, text in current.items() if key not in known]
    state["known_missing"] = sorted(current)
    return lines


def _new_verification_failures(state, texts):
    from db import db
    since = state.get("last_verified_at")
    newest = db.session.execute(db.text("SELECT MAX(verified_at) FROM files")).scalar()
    if since is None:
        state["last_verified_at"] = str(newest or "")
        return []
    rows = db.session.execute(db.text(
        "SELECT filename, verified_at FROM files WHERE verified_at > :since "
        "AND (signature_valid = 0 OR hash_valid = 0) ORDER BY verified_at"), {"since": since}).all()
    state["last_verified_at"] = str(newest or since)
    return [texts["verify_line"].format(name=row[0]) for row in rows]


def _new_failed_tasks(state):
    from db import db
    last = state.get("last_failed_task_id")
    if last is None:
        state["last_failed_task_id"] = db.session.execute(
            db.text("SELECT COALESCE(MAX(id), 0) FROM tasks WHERE status = 'failed'")).scalar()
        return []
    rows = db.session.execute(db.text(
        "SELECT id, task_name, error_message FROM tasks WHERE status = 'failed' AND id > :last ORDER BY id"),
        {"last": last}).all()
    if rows:
        state["last_failed_task_id"] = rows[-1][0]
    return [f"{row[1]}: {(row[2] or '').splitlines()[0][:160] if row[2] else ''}" for row in rows]


def check_once(app):
    settings = get_notify_settings()
    texts = _texts()
    with app.app_context():
        state = _state()
        found = {
            "new_content": (texts["new_title"], _new_files(state, texts)),
            "missing_content": (texts["missing_title"], _new_missing(state, texts)),
            "verification": (texts["verify_title"], _new_verification_failures(state, texts)),
            "task_failed": (texts["task_title"], _new_failed_tasks(state)),
        }
        _save_state(state)
    if not settings["provider"]:
        return
    for event, (title, lines) in found.items():
        if lines and settings["events"].get(event):
            error = send(title, _lines(lines), settings)
            if error:
                logger.warning(f"Notification not sent ({event}): {error}")
            else:
                logger.info(f"Notification sent: {title} ({len(lines)})")


def _loop(app):
    time.sleep(20)  # let the startup scan settle first
    while True:
        try:
            check_once(app)
        except Exception:
            logger.exception("Notification check failed")
        time.sleep(CHECK_EVERY)


def start(app):
    thread = threading.Thread(target=_loop, args=(app,), name="gamedock-notify", daemon=True)
    thread.start()


# --- routes -------------------------------------------------------------------------------------

def install(app):
    from flask import jsonify, request
    from flask_login import login_required

    from auth import access_required

    @app.route("/api/gamedock/missing")
    @login_required
    @access_required("admin")
    def gamedock_missing():
        return jsonify(missing_content())

    @app.route("/api/gamedock/notify", methods=["GET", "POST"])
    @login_required
    @access_required("admin")
    def gamedock_notify_settings():
        if request.method == "POST":
            save_notify_settings(request.get_json(silent=True) or {})
        settings = get_notify_settings()
        # Tokens never go back to the page: it only learns whether one is saved
        public = {k: v for k, v in settings.items() if k not in ("ntfy_token", "telegram_token", "discord_webhook")}
        public["has_ntfy_token"] = bool(settings["ntfy_token"])
        public["has_telegram_token"] = bool(settings["telegram_token"])
        public["has_discord_webhook"] = bool(settings["discord_webhook"])
        return jsonify({"success": True, "settings": public})

    @app.route("/api/gamedock/notify/test", methods=["POST"])
    @login_required
    @access_required("admin")
    def gamedock_notify_test():
        texts = _texts()
        error = send(texts["test_title"], texts["test"])
        return jsonify({"success": error is None, "error": error})
