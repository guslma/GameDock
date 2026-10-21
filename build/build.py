"""Turns an official Ownfoil install into GameDock.

    python3 build.py <app dir> <locales dir> <branding dir>

1. Brand: the product name and logo become GameDock. The Sphaira menu keeps the name Ownfoil,
   since that is what the console shows.
2. Languages: one translated copy of the templates and scripts per file in locales/,
   plus English, in templates/<code>/ and static/js/<code>/.
3. Runtime: gamedock_i18n.py picks the language of each request and the menu gets a
   language switcher.
4. Users: the edit button of each user, disabled in Ownfoil, opens a form that saves
   through gamedock_users.py.
5. Library: the list view, also disabled in Ownfoil.

Every change looks for an exact piece of the official code and stops the build when it
is gone, so a new Ownfoil version can never ship half patched.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import translate

HERE = Path(__file__).parent
BRAND = "GameDock"
ENGLISH = {"en": "English"}


def patch(path, old, new, count=1):
    source = path.read_text(encoding="utf-8")
    if source.count(old) != count:
        sys.exit(f"{path.name}: expected {count}x {old!r}, found {source.count(old)}; Ownfoil changed")
    path.write_text(source.replace(old, new), encoding="utf-8")


# The Sphaira menu is called Ownfoil on the console, so texts about it keep that name
SPHAIRA_MENU = re.compile(r"(?<!menu do )(?<!menú de )(?<!→ )\bOwnfoil\b(?! menu)", re.I)


def keeps_name(text):
    return text.strip() == "Ownfoil"


def branded(text):
    return text if keeps_name(text) else SPHAIRA_MENU.sub(BRAND, text)


def patch_server(app):
    patch(app / "app.py", "app = create_app()\n",
          "app = create_app()\nimport gamedock_i18n\ngamedock_i18n.install(app)\n"
          "import gamedock_users\ngamedock_users.install(app)\n")
    patch(app / "app.py", "or 'Ownfoil'}", f"or '{BRAND}'}}")
    patch(app / "constants.py", '"name": "Ownfoil",', f'"name": "{BRAND}",')
    patch(app / "auth.py", 'realm="Ownfoil"', f'realm="{BRAND}"')
    shutil.copy(HERE / "gamedock_i18n.py", app / "gamedock_i18n.py")
    shutil.copy(HERE / "gamedock_users.py", app / "gamedock_users.py")


def replace_artwork(app, branding):
    """The GameDock logo and icons, in the same files and sizes the Ownfoil ones used."""
    for source in sorted(branding.rglob("*")):
        relative = source.relative_to(branding)
        if source.is_dir() or len(relative.parts) == 1:
            continue
        target = app / "static" / relative
        if not target.exists():
            sys.exit(f"static/{relative}: not in Ownfoil anymore; Ownfoil changed")
        shutil.copy(source, target)


def add_user_editing(templates):
    """Ownfoil shows the edit button of each user disabled; GameDock makes it work."""
    settings = templates / "settings.html"
    patch(settings,
          """'<button type="button" class="btn btn-outline-info btn-sm" disabled=""><i class="bi bi-pencil-square"></i></button> ' +""",
          """'<button type="button" class="btn btn-outline-info btn-sm" onclick="openEditUser(' + user['id'] + ')"><i class="bi bi-pencil-square" title="Edit user"></i></button> ' +""")
    patch(settings, '                <hr class="hr-settings">\n\n                <h2>Library</h2>',
          (HERE / "edit_user.html").read_text(encoding="utf-8")
          + '                <hr class="hr-settings">\n\n                <h2>Library</h2>')
    patch(settings, "    function submitNewUser() {",
          (HERE / "edit_user.js").read_text(encoding="utf-8") + "    function submitNewUser() {")


def add_list_view(templates):
    """Ownfoil ships the list button of the library disabled; GameDock fills it in. The view
    buttons become outlined so the selected one stands out."""
    index = templates / "index.html"
    patch(index, 'class="btn btn-primary view-toggle-btn', 'class="btn btn-outline-primary view-toggle-btn', count=3)
    patch(index, 'data-view="list" disabled="">', 'data-view="list" title="List">')
    patch(index, 'data-view="card"><i', 'data-view="card" title="Cards"><i')
    patch(index, 'data-view="icon"><i', 'data-view="icon" title="Icons"><i')
    patch(index,
          "        if (isIcon) {\n            renderIconView(data.apps.items);\n        } else {\n",
          "        $('#cardSizeRange').toggleClass('invisible', currentView === 'list');\n"
          "        if (isIcon) {\n            renderIconView(data.apps.items);\n"
          "        } else if (currentView === 'list') {\n            renderListView(data.apps.items.map(cardModel));\n"
          "        } else {\n")
    # The list shows the version the game reports (1.0.2), not Nintendo's number (131072)
    patch(index, "versions { version owned releaseDate }", "versions { version owned releaseDate displayVersion }")
    patch(index, "            release_date: v.releaseDate || 'Unknown',\n",
          "            release_date: v.releaseDate || 'Unknown',\n            display_version: v.displayVersion,\n")
    patch(index, "    function renderIconView(apps) {",
          (HERE / "library_list.js").read_text(encoding="utf-8") + "    function renderIconView(apps) {")
    patch(index, "<script src=\"{{ url_for('static', filename='js/format.js') }}\"></script>",
          (HERE / "library_list.css").read_text(encoding="utf-8")
          + "<script src=\"{{ url_for('static', filename='js/format.js') }}\"></script>")


def add_switcher(templates):
    shutil.copy(HERE / "language.html", templates / "language.html")
    # Next to Login / Logout, in both branches of the menu
    patch(templates / "nav.html",
          '<ul class="navbar-nav ms-auto">\n                <li class="nav-item">',
          '<ul class="navbar-nav ms-auto">\n                {% include \'language.html\' %}\n                <li class="nav-item">',
          count=2)


TEMPLATE_REFERENCE = re.compile(r"""({%-?\s*(?:extends|include|import|from)\s+)(['"])([^'"/]+\.html)\2""")
SCRIPT_REFERENCE = re.compile(r"""(filename=)(['"])js/([^'"/]+\.js)\2""")


def point_to_locale(source, code):
    """The translated templates extend, include and load the copies of the same language."""
    source = TEMPLATE_REFERENCE.sub(lambda m: f"{m.group(1)}{m.group(2)}{code}/{m.group(3)}{m.group(2)}", source)
    source = SCRIPT_REFERENCE.sub(lambda m: f"{m.group(1)}{m.group(2)}js/{code}/{m.group(3)}{m.group(2)}", source)
    source = source.replace('<html lang="en"', f'<html lang="{code}"')
    return source.replace('placeholder="Ownfoil"', f'placeholder="{BRAND}"')


PAGE_TITLES = ("Files", "Library", "Login", "Services", "Settings", "Setup", "Stats", "Tasks")


def translate_page_title(source, dictionary):
    """The server passes the page name in English (title='Files'); the tab shows it translated."""
    names = {name: dictionary[name] for name in PAGE_TITLES if name in dictionary}
    return source.replace("{{title}}", "{{ %s.get(title, title) }}" % json.dumps(names, ensure_ascii=False))


def build_locale(app, code, dictionary, statuses, report):
    templates, scripts = app / "templates", app / "static" / "js"
    copies = []
    for source in sorted(templates.glob("*.html")):
        target = templates / code / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy(source, target)
        copies.append(target)
    for source in sorted(scripts.glob("*.js")):
        target = scripts / code / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy(source, target)
        copies.append(target)
    missing = set()
    for path in copies:
        missing |= translate.translate_file(path, dictionary, statuses)
        if path.suffix == ".html":
            source = point_to_locale(path.read_text(encoding="utf-8"), code)
            if path.name == "base.html":
                source = translate_page_title(source, dictionary)
            path.write_text(source, encoding="utf-8")
    if code != "en":
        report.mkdir(exist_ok=True)
        (report / f"{code}.txt").write_text("\n".join(sorted(missing)) + "\n", encoding="utf-8")
    print(f"{code}: {len(dictionary)} texts, {len(missing)} not in the dictionary")


def main():
    app, locales_dir, branding = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    patch_server(app)
    replace_artwork(app, branding)
    add_user_editing(app / "templates")
    add_list_view(app / "templates")
    add_switcher(app / "templates")

    translate.collect_logic_strings(app)
    texts = translate.extract(translate.files(app))
    # English only changes the product name
    english = {t: branded(t) for t in texts if branded(t) != t}

    locales = dict(ENGLISH)
    report = app / "untranslated"
    build_locale(app, "en", english, {}, report)
    for path in sorted(locales_dir.glob("*.json")):
        dictionary, meta = translate.load_dictionary(path)
        dictionary = {**english, **{k: branded(v) for k, v in dictionary.items()}}
        build_locale(app, path.stem, dictionary, meta.get("@status", {}), report)
        locales[path.stem] = meta.get("@name", path.stem)
    (app / "templates" / "locales.json").write_text(json.dumps(locales, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
