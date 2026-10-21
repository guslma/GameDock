"""Builds one translated copy of the interface per language.

    python3 localize.py <app dir> <locales dir>

The templates and scripts are written in English. For every locales/<code>.json this
writes templates/<code>/ and static/js/<code>/, translated with translate.py, plus an
English copy in templates/en/. gamedock_i18n.py then serves each visitor the copy of
their language. The texts a language does not know yet are listed in untranslated/.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import translate

TEMPLATE_REFERENCE = re.compile(r"""({%-?\s*(?:extends|include|import|from)\s+)(['"])([^'"/]+\.html)\2""")
SCRIPT_REFERENCE = re.compile(r"""(filename=)(['"])js/([^'"/]+\.js)\2""")

# Page names the server passes to base.html as `title`
PAGE_TITLES = ("Library", "Login", "Overview", "Files", "Settings", "Connect your console", "Game")


def point_to_locale(source, code):
    """The translated templates extend, include and load the copies of the same language."""
    source = TEMPLATE_REFERENCE.sub(lambda m: f"{m.group(1)}{m.group(2)}{code}/{m.group(3)}{m.group(2)}", source)
    source = SCRIPT_REFERENCE.sub(lambda m: f"{m.group(1)}{m.group(2)}js/{code}/{m.group(3)}{m.group(2)}", source)
    return source.replace('<html lang="en"', f'<html lang="{code}"')


def translate_page_title(source, dictionary):
    """The tab shows the page name translated (the server passes title='Files')."""
    names = {name: dictionary[name] for name in PAGE_TITLES if name in dictionary}
    return source.replace("{{title}}", "{{ %s.get(title, title) }}" % json.dumps(names, ensure_ascii=False))


def build_locale(app, code, dictionary, statuses, report):
    templates, scripts = app / "templates", app / "static" / "js"
    copies = []
    for folder, pattern in ((templates, "*.html"), (scripts, "*.js")):
        for source in sorted(folder.glob(pattern)):
            target = folder / code / source.name
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
    app, locales_dir = Path(sys.argv[1]), Path(sys.argv[2])
    translate.collect_logic_strings(app)
    locales = {"en": "English"}
    report = app / "untranslated"
    build_locale(app, "en", {}, {}, report)
    for path in sorted(locales_dir.glob("*.json")):
        dictionary, meta = translate.load_dictionary(path)
        build_locale(app, path.stem, dictionary, meta.get("@status", {}), report)
        locales[path.stem] = meta.get("@name", path.stem)
    (app / "templates" / "locales.json").write_text(json.dumps(locales, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
