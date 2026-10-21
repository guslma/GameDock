"""Translates the Ownfoil web interface with a dictionary of exact texts.

Only whole visible texts are replaced: text between HTML tags, a few attributes
(placeholder, title, aria-label, alt) and user-facing JavaScript strings. Code,
selectors, URLs and identifiers are never touched, so a text the dictionary does
not know simply stays in English.

    python3 translate.py <app dir> <out.json>    lists the texts found, to start a new language
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ATTRIBUTES = ("placeholder", "title", "aria-label", "alt", "data-bs-title", "data-title", "data-label")
LETTERS = re.compile(r"[A-Za-z]{2,}")
TAG = re.compile(r"<[^<>]+>")
JINJA = re.compile(r"{{.*?}}|{%.*?%}|{#.*?#}", re.S)

# JavaScript strings that look like code, not text: selectors, paths, identifiers, CSS, events
CODE_LIKE = re.compile(
    r"^(?:[#.\[/]|https?:|[a-z]+[A-Z_\-:][\w\-:]*$|[\w\-]+$|.*[{};=]|.*\.(?:js|css|png|svg|json|html)$)"
)


def files(app_dir):
    root = Path(app_dir)
    return sorted(list(root.glob("templates/*.html")) + list(root.glob("static/js/*.js")))


def is_text(value):
    value = value.strip()
    if not value or not LETTERS.search(JINJA.sub("", value)):
        return False
    if JINJA.fullmatch(value):
        return False
    return True


def looks_like_sentence(value):
    """A JavaScript string worth translating: has words and does not look like code."""
    stripped = value.strip()
    if not is_text(stripped):
        return False
    if " " not in stripped:
        # A single word is a label only when it is Capitalized (Title, Added); anything else is code
        return bool(re.fullmatch(r"[A-ZÀ-Ý][a-zà-ÿ]+:?", stripped))
    if re.search(r"[{};]|=>|\$\(|document\.|\.(?:querySelector|addEventListener)", stripped):
        return False
    return True


# --- JavaScript ---------------------------------------------------------------------------------

def js_strings(source):
    """Yields (start, end, quote, content) for every string literal, skipping comments.
    For template literals only the static parts between ${...} are yielded."""
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if source.startswith("//", i):
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if source.startswith("/*", i):
            j = source.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and source[j] != c:
                if source[j] == "\\":
                    j += 1
                elif source[j] == "\n":
                    break
                j += 1
            yield i + 1, j, c, source[i + 1:j]
            i = j + 1
            continue
        if c == "`":
            j = i + 1
            part_start = j
            while j < n and source[j] != "`":
                if source[j] == "\\":
                    j += 2
                    continue
                if source.startswith("${", j):
                    yield part_start, j, "`", source[part_start:j]
                    depth, j = 1, j + 2
                    while j < n and depth:
                        if source[j] == "{":
                            depth += 1
                        elif source[j] == "}":
                            depth -= 1
                        elif source[j] in "'\"`":
                            # skip nested literals inside the expression
                            q = source[j]
                            j += 1
                            while j < n and source[j] != q:
                                j += 2 if source[j] == "\\" else 1
                        j += 1
                    part_start = j
                    continue
                j += 1
            yield part_start, j, "`", source[part_start:j]
            i = j + 1
            continue
        i += 1


def split_partial_tags(content):
    """A piece of a template literal can start or end inside a tag, when a ${...} sits in
    an attribute: `<img class="${c}" alt="">Text`. Returns (tag tail, markup, tag head)."""
    head = tail = ""
    gt, lt = content.find(">"), content.find("<")
    if gt >= 0 and (lt < 0 or gt < lt):
        head, content = content[:gt + 1], content[gt + 1:]
    lt, gt = content.rfind("<"), content.rfind(">")
    if lt >= 0 and lt > gt:
        content, tail = content[:lt], content[lt:]
    return head, content, tail


def text_parts(content):
    """The translatable pieces of a JavaScript string: the whole string, or the text
    between tags when it holds HTML."""
    if TAG.search(content) or (TAG.search(content + ">") and "<" in content) or ">" in content:
        content = split_partial_tags(content)[1]
    if TAG.search(content):
        pieces = []
        for piece in TAG.split(content):
            if is_text(piece):
                pieces.append(piece.strip())
        for match in re.finditer(r'\b(?:%s)="([^"]*)"' % "|".join(ATTRIBUTES), content):
            if is_text(match.group(1)):
                pieces.append(match.group(1).strip())
        return pieces
    if looks_like_sentence(content) or after_interpolation(content):
        return [content.strip()]
    return []


def after_interpolation(content):
    """Text such as the " titles" in `${count} titles`: starts with a space after a value."""
    return content[:1] == " " and bool(re.fullmatch(r"[a-zà-ÿ][a-zà-ÿ ]*", content.strip()))


def translate_js_string(content, dictionary, quote=None):
    head, markup, tail = split_partial_tags(content)
    if (head or tail) and TAG.search(markup):
        return head + translate_js_string(markup, dictionary, quote) + tail
    if TAG.search(content):
        def text(match_text):
            core = match_text.strip()
            if core in dictionary:
                return match_text.replace(core, dictionary[core], 1)
            return match_text
        out, last = [], 0
        for tag in TAG.finditer(content):
            out.append(text(content[last:tag.start()]))
            tag_text = tag.group(0)
            for attr in ATTRIBUTES:
                tag_text = re.sub(r'(\b%s=")([^"]*)(")' % re.escape(attr),
                                  lambda m: m.group(1) + dictionary.get(m.group(2).strip(), m.group(2)) + m.group(3), tag_text)
            out.append(tag_text)
            last = tag.end()
        out.append(text(content[last:]))
        return "".join(out)
    core = content.strip()
    # A piece of a template literal next to a value, such as the "of " in `of ${total}`
    piece = quote == "`" and core in dictionary
    if core in dictionary and (piece or looks_like_sentence(content) or after_interpolation(content)):
        return content.replace(core, dictionary[core], 1)
    return content


# Strings the code compares or uses as keys must keep their value, or the logic breaks
LOGIC_USE = re.compile(r"""(?:===?|!==?|\bcase)\s*(['"`])(.*?)\1|(?:(?<=[{,])|(?<=[{,]\s)|(?<=^\s{4})|(?<=\n\s{2}))\s*(['"`])(.*?)\3\s*:(?!:)|(['"`])(.*?)\5\s*(?:===?|!==?)""")
LOGIC_STRINGS = set()


# Strings handed to string functions are matched against other text, not shown:
# html.replace(' checked', '') only works while ' checked' keeps its value
METHOD_ARGUMENT = re.compile(r"""\.(?:replace|replaceAll|includes|indexOf|lastIndexOf|startsWith|endsWith|split|match|search)\(\s*(['"`])(.*?)\1""")


def logic_strings(source):
    found = set()
    for match in LOGIC_USE.finditer(source):
        value = next(g for g in (match.group(2), match.group(4), match.group(6)) if g is not None)
        found.update({value, value.strip()})
    for match in METHOD_ARGUMENT.finditer(source):
        found.update({match.group(2), match.group(2).strip()})
    return found


SHARED_LOGIC = set()


def collect_logic_strings(app_dir):
    """The shared scripts load on every page, so what they compare is protected everywhere."""
    for path in Path(app_dir).glob("static/js/*.js"):
        SHARED_LOGIC.update(logic_strings(path.read_text(encoding="utf-8")))


def use_logic_strings_of(source):
    """A label is protected only in the files that compare it: 'Complete' is a filter value
    in the library page and a plain label in the stats page."""
    LOGIC_STRINGS.clear()
    LOGIC_STRINGS.update(SHARED_LOGIC | logic_strings(source))


def process_js(source, dictionary=None, found=None):
    out, last = [], 0
    for start, end, quote, content in js_strings(source):
        # Only the exact value the code compares is protected: " files" in `${n} files` is still text
        if content in LOGIC_STRINGS:
            continue
        if found is not None:
            found.extend(text_parts(content))
        if dictionary is not None:
            new = translate_js_string(content, dictionary, quote)
            if new != content:
                out.append(source[last:start])
                out.append(new)
                last = end
    out.append(source[last:])
    return "".join(out)


# --- HTML templates -----------------------------------------------------------------------------

class Template(HTMLParser):
    """Walks a template, collecting text nodes, attributes and script blocks with offsets."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        for line in source.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.texts, self.attrs, self.scripts = [], [], []
        self.in_raw = None
        self.feed(source)

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.position()
        raw = self.get_starttag_text() or ""
        for name, value in attrs:
            if name in ATTRIBUTES and value and is_text(value):
                # The value of this attribute, not the same text elsewhere in the tag (an id, a class)
                match = re.search(r"\b%s\s*=\s*([\"'])%s\1" % (re.escape(name), re.escape(value)), raw)
                if match:
                    at = match.start(1) + 1
                    self.attrs.append((start + at, start + at + len(value), value))
        if tag in ("script", "style"):
            self.in_raw = (tag, start + len(raw))

    def handle_endtag(self, tag):
        if self.in_raw and tag == self.in_raw[0]:
            if tag == "script":
                self.scripts.append((self.in_raw[1], self.position()))
            self.in_raw = None

    def handle_data(self, data):
        if self.in_raw or not is_text(data):
            return
        start = self.position()
        self.texts.append((start, start + len(data), data))


JINJA_BLOCK = re.compile(r"{%.*?%}", re.S)
JINJA_STRING = re.compile(r"""(['"])((?:(?!\1).)*)\1""")


def process_jinja(source, dictionary=None, found=None):
    """Label lists written in Jinja, such as {% set tiles = [('all', 'All files')] %}."""
    def block(match):
        def literal(m):
            text = m.group(2)
            if text in LOGIC_STRINGS or not looks_like_sentence(text):
                return m.group(0)
            if found is not None:
                found.append(text.strip())
            if dictionary is not None and text.strip() in dictionary:
                return m.group(1) + dictionary[text.strip()] + m.group(1)
            return m.group(0)
        return JINJA_STRING.sub(literal, match.group(0))
    return JINJA_BLOCK.sub(block, source)


def process_template(source, dictionary=None, found=None):
    source = process_jinja(source, dictionary, found)
    parsed = Template(source)
    edits = []
    for start, end, text in parsed.texts + parsed.attrs:
        core = text.strip()
        if found is not None:
            found.append(core)
        if dictionary is not None and core in dictionary:
            edits.append((start, end, text.replace(core, dictionary[core], 1)))
    for start, end in parsed.scripts:
        block = source[start:end]
        new = process_js(block, dictionary, found)
        if dictionary is not None and new != block:
            edits.append((start, end, new))
    out = source
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    return out


# Status values (CORRUPT, FAILED...) come from the server and are shown through humanize();
# the function gets a lookup so the code keeps comparing the original values
HUMANIZE = "function humanize(key) {"


def translate_statuses(source, statuses):
    if not statuses or HUMANIZE not in source:
        return source
    lookup = "const translated = %s; if (translated[key]) return translated[key];" % json.dumps(statuses, ensure_ascii=False)
    return source.replace(HUMANIZE, HUMANIZE + "\n        " + lookup)


def process(path, dictionary=None, found=None):
    source = path.read_text(encoding="utf-8")
    use_logic_strings_of(source)
    if path.suffix == ".js":
        return process_js(source, dictionary, found)
    return process_template(source, dictionary, found)


def load_dictionary(path):
    """A language file: exact English text -> translation, plus "@status" for status values."""
    dictionary = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = {k: dictionary.pop(k) for k in list(dictionary) if k.startswith("@")}
    dictionary = {k: v for k, v in dictionary.items() if v and v != k}
    # Translations go inside JavaScript strings as they are, so they must not carry quotes
    bad = [k for k, v in dictionary.items() if any(q in v for q in "'\"`") and not any(q in k for q in "'\"`")]
    if bad:
        sys.exit(f"{path}: translations with quotes: " + "; ".join(bad[:5]))
    return dictionary, meta


def extract(paths):
    """Every visible text in the given files, mapped to the first file it appears in."""
    texts = {}
    for path in paths:
        found = []
        process(path, None, found)
        for text in found:
            texts.setdefault(text, path.name)
    return texts


def translate_file(path, dictionary, statuses=None):
    """Translates one file in place and returns the texts the dictionary does not know."""
    found = []
    translated = translate_statuses(process(path, dictionary, found), statuses or {})
    path.write_text(translated, encoding="utf-8")
    return {t for t in found if t not in dictionary}


def main():
    # python3 translate.py <app dir> <out.json>: lists the texts of a GameDock or Ownfoil
    # install, the starting point for a new language file
    app_dir, out = sys.argv[1:3]
    collect_logic_strings(app_dir)
    texts = extract(files(app_dir))
    Path(out).write_text(json.dumps(texts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(texts)} texts")


if __name__ == "__main__":
    main()
