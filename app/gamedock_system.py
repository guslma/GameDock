"""Log file and time zone information for Settings > Logs.

Every GameDock process (web server and task workers) appends its log lines to
data/logs/gamedock.log. The file is shared by the processes, so writes take a lock, and
it is trimmed to its newest part when it grows past MAX_BYTES.

The time zone comes from the installation: the TZ variable of the container, or the
host's /etc/localtime mounted into it. Python and the log timestamps use it on their own.
"""

import fcntl
import json
import logging
import os
import re
import time
from pathlib import Path

from constants import DATA_DIR

LOG_FILE = Path(DATA_DIR) / "logs" / "gamedock.log"
MAX_BYTES = 5 * 1024 * 1024
KEEP_BYTES = 2 * 1024 * 1024
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def current_timezone():
    """The zone this process runs in: TZ, else the zone /etc/localtime points to, else UTC."""
    if os.environ.get("TZ"):
        return os.environ["TZ"]
    try:
        # /etc/timezone, when the host's is mounted along with /etc/localtime
        name = open("/etc/timezone", encoding="utf-8").read().strip()
        if name:
            return name
    except OSError:
        pass
    try:
        target = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return "UTC"


class SharedFileHandler(logging.Handler):
    """Appends plain-text lines to the shared log file, trimming it when it gets big."""

    def __init__(self, formatter):
        super().__init__(level=logging.INFO)
        self.setFormatter(formatter)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        try:
            line = (ANSI.sub("", self.format(record)) + "\n").encode("utf-8")
            with open(LOG_FILE, "a+b") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0, os.SEEK_END)
                    if f.tell() > MAX_BYTES:
                        f.seek(f.tell() - KEEP_BYTES)
                        tail = f.read()
                        tail = tail[tail.find(b"\n") + 1:]
                        f.seek(0)
                        f.truncate()
                        f.write(tail)
                    f.write(line)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            self.handleError(record)


def log_to_file(formatter):
    """Adds the shared file to the root logger of this process (once)."""
    root = logging.getLogger()
    if not any(isinstance(h, SharedFileHandler) for h in root.handlers):
        root.addHandler(SharedFileHandler(formatter))


LEVELS = {"all": None, "warning": ("WARNING", "ERROR", "CRITICAL"), "error": ("ERROR", "CRITICAL")}
LEVEL_IN_LINE = re.compile(r"^\[[^\]]+\] (\w+) ")


def read_log(lines=500, level="all", search=""):
    """The newest lines of the log, oldest first, optionally filtered."""
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - KEEP_BYTES))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return [], 0
    rows = text.splitlines()
    if size > KEEP_BYTES and rows:
        rows = rows[1:]  # the first one may be cut in half
    wanted = LEVELS.get(level)
    out, current = [], None
    for row in rows:
        match = LEVEL_IN_LINE.match(row)
        if match:
            current = match.group(1)
        # Lines without a level (a traceback) belong to the entry above them
        if wanted and current not in wanted:
            continue
        if search and search.lower() not in row.lower():
            continue
        out.append(row)
    return out[-lines:], size


def install(app):
    from flask import Response, jsonify, request
    from flask_login import login_required

    from auth import access_required

    @app.route("/api/logs")
    @login_required
    @access_required("admin")
    def gamedock_logs():
        try:
            lines = max(50, min(int(request.args.get("lines", 500)), 5000))
        except ValueError:
            lines = 500
        rows, size = read_log(lines, request.args.get("level", "all"), request.args.get("search", "").strip())
        return jsonify({"lines": rows, "size": size, "timezone": current_timezone(), "now": time.strftime("%Y-%m-%d %H:%M:%S")})

    @app.route("/api/logs/download")
    @login_required
    @access_required("admin")
    def gamedock_logs_download():
        rows, _ = read_log(100000)
        return Response("\n".join(rows) + "\n", mimetype="text/plain",
                        headers={"Content-Disposition": "attachment; filename=gamedock.log"})
