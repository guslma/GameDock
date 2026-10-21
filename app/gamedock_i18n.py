"""Serves every page in the visitor's language.

The build leaves one translated copy of the templates per language in
templates/<code>/. Each request picks a language (the one chosen in the menu, then
the browser's, then GAMEDOCK_LANGUAGE, then English) and renders that copy.
"""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from flask import g, has_request_context, redirect, request
from jinja2 import TemplateNotFound

LOCALES = json.loads((Path(__file__).parent / "templates" / "locales.json").read_text(encoding="utf-8"))
COOKIE = "gamedock_language"

try:
    # GameDock follows the Ownfoil releases, so it carries the same version number
    from constants import APP_VERSION as VERSION
except ImportError:
    VERSION = ""


def default_locale():
    wanted = os.environ.get("GAMEDOCK_LANGUAGE", "")
    return wanted if wanted in LOCALES else "en"


def match(accepted):
    """The first browser language we have, by exact code (pt-BR) or by language (pt)."""
    exact = {code.lower(): code for code in LOCALES}
    by_language = {}
    for code in LOCALES:
        by_language.setdefault(code.split("-")[0].lower(), code)
    for value, _quality in accepted:
        value = value.lower().replace("_", "-")
        if value in exact:
            return exact[value]
        if value.split("-")[0] in by_language:
            return by_language[value.split("-")[0]]
    return None


def current_locale():
    if not has_request_context():
        return default_locale()
    if "gamedock_locale" not in g:
        chosen = request.cookies.get(COOKIE)
        if chosen not in LOCALES:
            chosen = match(request.accept_languages) or default_locale()
        g.gamedock_locale = chosen
    return g.gamedock_locale


def install(app):
    env = app.jinja_env
    original = env.get_or_select_template

    def localized(name, parent=None, globals=None):
        # Pages ask for "index.html"; the translated copies include each other by full path
        if isinstance(name, str) and "/" not in name and has_request_context():
            try:
                return original(f"{current_locale()}/{name}", parent, globals)
            except TemplateNotFound:
                pass
        return original(name, parent, globals)

    env.get_or_select_template = localized

    @app.context_processor
    def languages():
        return {"gamedock_locale": current_locale(), "gamedock_locales": LOCALES, "gamedock_version": VERSION}

    @app.route("/language/<code>")
    def set_language(code):
        # Back to the page the visitor was on, but never to another site
        back = urlparse(request.referrer or "")
        target = back.path if back.path.startswith("/") and not back.path.startswith("//") else "/"
        if back.query:
            target += "?" + back.query
        response = redirect(target)
        if code in LOCALES:
            response.set_cookie(COOKIE, code, max_age=365 * 24 * 3600, samesite="Lax")
        return response
