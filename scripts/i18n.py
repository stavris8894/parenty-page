#!/usr/bin/env python3
"""Builds the translated home pages (el/, de/, …) from index.html and i18n/<lang>.json.

index.html (English) is the only page to edit. Then:
  python3 scripts/i18n.py extract   # writes i18n/strings.json: every text to translate
  python3 scripts/i18n.py build     # writes <lang>/index.html for every i18n/<lang>.json

A translation file maps each English string to its translation. `build` fails and lists the
strings a language is missing, so a changed sentence can't silently stay in English.

What counts as text: the content of elements (inline markup like <span>, <strong> or <br> stays
part of the sentence; icons are left out), translatable attributes, the <title>, meta
descriptions, JSON-LD names/descriptions/answers, and the strings in the page script listed in
SCRIPT_STRINGS.
"""
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "index.html"
I18N = ROOT / "i18n"
SITE = "https://parenty.uk/"

# Language code -> (name in that language, Open Graph locale, text direction)
LANGUAGES = {
    "en": ("English", "en_GB", "ltr"),
    "el": ("Ελληνικά", "el_GR", "ltr"),
    "de": ("Deutsch", "de_DE", "ltr"),
    "es": ("Español", "es_ES", "ltr"),
    "fr": ("Français", "fr_FR", "ltr"),
    "it": ("Italiano", "it_IT", "ltr"),
    "pt": ("Português", "pt_BR", "ltr"),
    "tr": ("Türkçe", "tr_TR", "ltr"),
    "ar": ("العربية", "ar_AR", "rtl"),
}

TRANSLATABLE_ATTRS = ("alt", "aria-label", "title", "placeholder")
TRANSLATABLE_META = ("description", "og:title", "og:description", "og:image:alt",
                     "twitter:title", "twitter:description", "twitter:image:alt")
JSON_LD_KEYS = ("name", "description", "text")
JSON_LD_SKIP_TYPES = ("Person", "Organization")  # names of people and the company stay as they are
# Strings the page script writes into the page (button labels).
SCRIPT_STRINGS = ("Turn sound on", "Turn sound off", "Switch to light theme", "Switch to dark theme")
# Elements whose content is never text to translate.
OPAQUE = {"svg", "script", "style", "video", "picture", "img", "source", "use", "path"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "use", "path", "circle", "rect"}
# Inline elements that stay inside a sentence instead of splitting it.
INLINE = {"span", "strong", "em", "b", "i", "br", "a", "small", "abbr", "code"}


class Node:
    def __init__(self, tag, attrs, start, parent):
        self.tag, self.attrs, self.start, self.parent = tag, dict(attrs), start, parent
        self.inner_start = None
        self.inner_end = None
        self.children = []


class TreeBuilder(HTMLParser):
    """Element tree with source offsets, enough to cut out each element's inner HTML."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0]
        for line in source.splitlines(keepends=True):
            self.line_offsets.append(self.line_offsets[-1] + len(line))
        self.root = Node("#root", [], 0, None)
        self.root.inner_start = 0
        self.current = self.root

    def source_offset(self):
        line, col = self.getpos()
        return self.line_offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.source_offset()
        node = Node(tag, attrs, start, self.current)
        node.inner_start = start + len(self.get_starttag_text())
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node
        else:
            node.inner_end = node.inner_start

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.current.tag == tag and tag not in VOID:
            self.current.inner_end = self.current.inner_start
            self.current = self.current.parent

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is self.root:
            return
        end = self.source_offset()
        while self.current is not node:
            self.current.inner_end = end
            self.current = self.current.parent
        node.inner_end = end
        self.current = node.parent


def has_direct_text(node, source):
    """True when some text sits directly in the element, outside its child elements."""
    cursor = node.inner_start
    for child in node.children:
        if source[cursor:child.start].strip():
            return True
        cursor = source.find(">", child.inner_end) + 1 if child.tag not in VOID else child.inner_start
    return bool(source[cursor:node.inner_end].strip())


def is_text_container(node, source):
    """True when the element holds a sentence: its own text plus, at most, inline markup and icons."""
    def inline_ok(n):
        return n.tag in INLINE and all(c.tag in INLINE and inline_ok(c) for c in n.children)
    return (node.tag not in OPAQUE | {"#root", "html", "head", "body"}
            and has_direct_text(node, source)
            and all(c.tag in OPAQUE or inline_ok(c) for c in node.children))


def text_units(source):
    """(start, end) spans of every sentence in the page body and <title>."""
    tree = TreeBuilder(source)
    tree.feed(source)
    spans = []

    def walk(node, inside_body):
        if node.tag in OPAQUE or node.attrs.get("translate") == "no":
            return
        if node.tag in ("title",) or (inside_body and is_text_container(node, source)):
            # Split around icons (svg/img/video) so only the words are replaced
            cursor = node.inner_start
            for child in node.children + [None]:
                if child is not None and child.tag not in OPAQUE:
                    continue
                end = child.start if child is not None else node.inner_end
                piece = source[cursor:end]
                stripped = piece.strip()
                if re.search(r"[A-Za-z]", re.sub(r"<[^>]+>", "", stripped)):
                    lead = len(piece) - len(piece.lstrip())
                    spans.append((cursor + lead, cursor + lead + len(stripped)))
                if child is not None:
                    cursor = child.inner_end
                    # skip past the child's closing tag
                    close = source.find(">", cursor) + 1 if child.tag not in VOID else child.inner_start
                    cursor = close
            return
        for child in node.children:
            walk(child, inside_body or node.tag == "body")

    walk(tree.root, False)
    return spans


def attr_units(source):
    """(start, end) spans of translatable attribute values and meta contents."""
    spans = []
    for m in re.finditer(r'\s(%s)="([^"]*)"' % "|".join(TRANSLATABLE_ATTRS), source):
        if re.search(r"[A-Za-z]", m.group(2)):
            spans.append((m.start(2), m.end(2)))
    for m in re.finditer(r'<meta\s+(?:name|property)="([^"]+)"\s+content="([^"]*)"', source):
        if m.group(1) in TRANSLATABLE_META:
            spans.append((m.start(2), m.end(2)))
    return spans


def json_ld_strings(source):
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', source, re.S):
        def walk(value, parent_type=None):
            if isinstance(value, dict):
                t = value.get("@type", parent_type)
                for k, v in value.items():
                    if k in JSON_LD_KEYS and isinstance(v, str) and t not in JSON_LD_SKIP_TYPES:
                        out.append(v)
                    else:
                        walk(v, t)
            elif isinstance(value, list):
                for v in value:
                    walk(v, parent_type)
        walk(json.loads(m.group(1)))
    return out


def catalog(source):
    strings = []
    for start, end in sorted(text_units(source) + attr_units(source)):
        strings.append(source[start:end])
    strings += json_ld_strings(source) + list(SCRIPT_STRINGS)
    seen, unique = set(), []
    for s in strings:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def extract():
    source = SOURCE.read_text()
    strings = catalog(source)
    I18N.mkdir(exist_ok=True)
    (I18N / "strings.json").write_text(json.dumps(strings, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(strings)} strings -> i18n/strings.json")


def relative_url(url):
    """A link or asset URL as seen from a page one folder down (el/index.html)."""
    if re.match(r"^(#|[a-z]+:|/|data:)", url):
        return url
    return "../" + (url[2:] if url.startswith("./") else url)


def localize(source, lang, translations):
    name, locale, direction = LANGUAGES[lang]

    # 1. Text and attributes, replaced from the end so earlier offsets stay valid
    attr_spans = set(attr_units(source))
    for start, end in sorted(set(text_units(source)) | attr_spans, reverse=True):
        text = translations[source[start:end]]
        if (start, end) in attr_spans:
            text = text.replace('"', "&quot;")
        source = source[:start] + text + source[end:]

    # 2. JSON-LD
    def translate_json(m):
        data = json.loads(m.group(1))

        def walk(value, parent_type=None):
            if isinstance(value, dict):
                t = value.get("@type", parent_type)
                for k, v in value.items():
                    if k in JSON_LD_KEYS and isinstance(v, str) and t not in JSON_LD_SKIP_TYPES:
                        value[k] = translations[v]
                    else:
                        walk(v, t)
                if "inLanguage" in value:
                    value["inLanguage"] = lang
            elif isinstance(value, list):
                for v in value:
                    walk(v, parent_type)
        walk(data)
        body = json.dumps(data, ensure_ascii=False, indent=2)
        return '<script type="application/ld+json">\n' + body + "\n    </script>"
    source = re.sub(r'<script type="application/ld\+json">(.*?)</script>', translate_json, source, flags=re.S)

    # 3. Script strings
    for s in SCRIPT_STRINGS:
        source = source.replace(f'"{s}"', json.dumps(translations[s], ensure_ascii=False))
    # The theme button decides which way to switch from its label
    source = source.replace('.getAttribute("aria-label").includes("light")',
                            '.getAttribute("aria-label") === ' + json.dumps(translations["Switch to light theme"], ensure_ascii=False))

    # 4. Language, direction, URLs
    source = source.replace('<html lang="en">', f'<html lang="{lang}" dir="{direction}">', 1)
    page_url = f"{SITE}{lang}/"
    source = source.replace('<link rel="canonical" href="https://parenty.uk/" />', f'<link rel="canonical" href="{page_url}" />')
    source = source.replace('<meta property="og:url" content="https://parenty.uk/" />', f'<meta property="og:url" content="{page_url}" />')
    source = re.sub(r'<meta property="og:locale" content="[^"]*" />', f'<meta property="og:locale" content="{locale}" />', source)
    # The English page lists every other locale; here English takes this page's place
    source = source.replace(f'<meta property="og:locale:alternate" content="{locale}" />',
                            f'<meta property="og:locale:alternate" content="{LANGUAGES["en"][1]}" />')
    source = re.sub(r'(\s(?:href|src|srcset|poster)=")([^"]+)(")', lambda m: m.group(1) + relative_url(m.group(2)) + m.group(3), source)
    # The language switcher marks the current page
    source = source.replace(' aria-current="page"', "")
    source = re.sub(rf'(<a hreflang="{lang}"[^>]*?)>', r'\1 aria-current="page">', source, count=1)
    return source


def build():
    source = SOURCE.read_text()
    strings = catalog(source)
    failed = False
    for path in sorted(I18N.glob("*.json")):
        lang = path.stem
        if lang not in LANGUAGES or lang == "en":
            continue
        translations = json.loads(path.read_text())
        missing = [s for s in strings if s not in translations]
        if missing:
            failed = True
            print(f"{lang}: {len(missing)} missing translation(s):")
            for s in missing:
                print("   ", json.dumps(s, ensure_ascii=False))
            continue
        out = ROOT / lang / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(localize(source, lang, translations))
        unused = len(set(translations) - set(strings))
        print(f"{lang}: wrote {out.relative_to(ROOT)}" + (f" ({unused} unused entries)" if unused else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    {"extract": extract, "build": build}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
