"""Download history: who took which file, when, with which app.

Ownfoil only keeps a running count per file. GameDock records each download in its own
SQLite file next to the main database (config/downloads.db), so the Ownfoil schema and its
migrations stay untouched and the history is part of every config backup.

Consoles fetch a file in several Range requests, so one user taking the same file again
within DEDUP_WINDOW counts as the same download.
"""

import datetime
import logging
import os
import sqlite3
import threading

from constants import CONFIG_DIR, APP_TYPE_BASE, APP_TYPE_UPD, APP_TYPE_DLC

logger = logging.getLogger("main")

DB_FILE = os.path.join(CONFIG_DIR, "downloads.db")
DEDUP_WINDOW = datetime.timedelta(minutes=30)
KEEP_ROWS = 10000
_lock = threading.Lock()


def _connect():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    connection.execute("""CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL,
        user TEXT,
        client TEXT,
        ip TEXT,
        file_id INTEGER,
        filename TEXT,
        title_id TEXT,
        title_name TEXT,
        app_type TEXT,
        app_name TEXT,
        version TEXT,
        size INTEGER)""")
    connection.execute("CREATE INDEX IF NOT EXISTS ix_downloads_user ON downloads (user, at)")
    return connection


def _who(request):
    """The account behind a download: the shop login of a console app, else the web session."""
    if request.authorization and request.authorization.username:
        return request.authorization.username
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return current_user.user
    return None


def _client(request):
    from app import get_client_for_request
    client = get_client_for_request(request)
    if client:
        return client.CLIENT_NAME
    agent = request.headers.get("User-Agent", "")
    return "Browser" if "Mozilla" in agent else (agent.split("/")[0][:40] or None)


def _describe(filepath):
    """What a file is, resolved now so the history still reads right after it is deleted."""
    from db import Files
    from gamedock_notify import _name
    import titles as titles_lib

    file = Files.query.filter_by(filepath=filepath).first()
    info = {"file_id": None, "filename": os.path.basename(filepath), "title_id": None,
            "title_name": None, "app_type": None, "app_name": None, "version": None, "size": None}
    if file is None:
        return info
    info.update(file_id=file.id, size=file.size)
    app = file.apps[0] if file.apps else None
    if app is None:
        return info
    title_id = app.title.title_id
    info.update(title_id=title_id, title_name=_name(title_id, title_id), app_type=app.app_type)
    if app.app_type == APP_TYPE_DLC:
        info["app_name"] = _name(app.app_id, app.app_id)
    if app.app_type == APP_TYPE_UPD and app.app_version:
        info["version"] = str(titles_lib.get_update_number(app.app_version))
    return info


def record(request, filepath):
    """Store one download. Never lets a history problem get in the way of the file itself."""
    if request.method != "GET":
        return
    try:
        user = _who(request)
        from utils import client_address
        ip = client_address(request)
        now = datetime.datetime.now(datetime.timezone.utc)
        since = (now - DEDUP_WINDOW).isoformat()
        info = _describe(filepath)
        with _lock, _connect() as connection:
            repeated = connection.execute(
                "SELECT 1 FROM downloads WHERE filename = ? AND IFNULL(user, '') = ? AND IFNULL(ip, '') = ? AND at >= ?",
                (info["filename"], user or "", ip or "", since)).fetchone()
            if repeated:
                return
            connection.execute(
                "INSERT INTO downloads (at, user, client, ip, file_id, filename, title_id, title_name, app_type, app_name, version, size) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (now.isoformat(), user, _client(request), ip, info["file_id"], info["filename"], info["title_id"],
                 info["title_name"], info["app_type"], info["app_name"], info["version"], info["size"]))
            connection.execute(
                "DELETE FROM downloads WHERE id <= (SELECT id FROM downloads ORDER BY id DESC LIMIT 1 OFFSET ?)",
                (KEEP_ROWS,))
        logger.info(f"Download: {info['filename']} by {user or 'no user'} ({_client(request) or 'unknown app'})")
    except Exception:
        logger.exception("Could not record a download in the history")


def history(user=None, search="", limit=500):
    """The newest downloads, optionally for one user ("" for downloads without a user)."""
    query = "SELECT at, user, client, ip, filename, title_id, title_name, app_type, app_name, version, size FROM downloads"
    where, args = [], []
    if user is not None:
        where.append("IFNULL(user, '') = ?")
        args.append(user)
    if search:
        where.append("(title_name LIKE ? OR filename LIKE ? OR app_name LIKE ?)")
        args += [f"%{search}%"] * 3
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    keys = ["at", "user", "client", "ip", "filename", "title_id", "title_name", "app_type", "app_name", "version", "size"]
    with _lock, _connect() as connection:
        rows = [dict(zip(keys, row)) for row in connection.execute(query, args)]
        users = [dict(zip(["user", "count", "last", "size"], row)) for row in connection.execute(
            "SELECT user, COUNT(*), MAX(at), SUM(IFNULL(size, 0)) FROM downloads GROUP BY user ORDER BY MAX(at) DESC")]
    return rows, users


def clear():
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM downloads")


def install(app):
    from flask import jsonify, request
    from flask_login import login_required
    from auth import access_required

    @app.route("/api/gamedock/downloads", methods=["GET", "DELETE"])
    @login_required
    @access_required("admin")
    def gamedock_downloads():
        if request.method == "DELETE":
            clear()
            return jsonify({"success": True})
        user = request.args.get("user")
        rows, users = history(user=user if user is not None and user != "*" else None,
                              search=request.args.get("search", "").strip())
        return jsonify({"downloads": rows, "users": users})
