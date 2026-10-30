"""The patches' own text in other languages: one JSON file per language (de.json, ...), each mapping
the English text the Java helpers pass to seekpatch.Lang (Lang.t / Lang.f, see helpers/java) to its
translation.  Patterns for Lang.f keep their format specifiers (%s, %d, %1$s, %%).

strings_smali() writes seekpatch.Strings: the languages the app itself has (read from its
resources.arsc, or from res/ when resources were decoded) and, for each of them, the translations, so
Lang shows the patches' text in the language of the app's own.  add_helpers() adds it together with
seekpatch.Lang.
"""
from __future__ import annotations

import json
import os
import re
from importlib import resources

from .. import axml

SEPARATOR = "\x1f"
"""Between the strings of one language in seekpatch.Strings (no text holds it)."""
SHARE = 4
"""A locale counts as one of the app's languages when it has at least 1/SHARE as many strings as the
default configuration: Seek's own translations have 60 - 100 %, the libraries' locales (1.9.3 carries
appcompat's) about 10 %."""


def translations() -> dict[str, dict[str, str]]:
    """{language: {English: translation}} for every JSON file here."""
    out = {}
    for p in sorted(resources.files(__name__).iterdir(), key=lambda p: p.name):
        if p.name.endswith(".json"):
            out[p.name[:-len(".json")]] = json.loads(p.read_text(encoding="utf-8"))
    return out


def app_languages(root: str) -> list[str]:
    """The languages of the decoded app's own text, as BCP 47 tags (e.g. ["de", ..., "pt-PT", ...]);
    English, the default, is not listed."""
    counts = _decoded_counts(root)
    if counts is None:
        try:
            with open(os.path.join(root, "resources.arsc"), "rb") as f:
                counts = axml.string_locales(f.read())
        except (OSError, axml.AxmlError):
            return []
    return languages(counts)


def languages(counts: dict[str, int]) -> list[str]:
    """The app's languages besides English from its strings per locale (axml.string_locales)."""
    base = counts.get("", 0)
    return sorted(tag for tag, n in counts.items()
                  if tag and tag.split("-")[0] != "en" and n * SHARE >= base > 0)


def _decoded_counts(root: str) -> dict[str, int] | None:
    """Strings per locale from res/values*/strings.xml (resources decoded: --side-by-side); None without res/."""
    res = os.path.join(root, "res")
    if not os.path.isdir(res):
        return None
    counts: dict[str, int] = {}
    for d in os.listdir(res):
        m = re.fullmatch(r"values(?:-([a-z]{2,3})(?:-r([A-Z]{2}))?)?(-.+)?", d)
        if not m or (m.group(1) is None and m.group(3)) or m.group(1) in _NOT_LANGUAGES:
            continue  # values-w600dp, values-night, ...
        try:
            with open(os.path.join(res, d, "strings.xml"), encoding="utf-8") as f:
                n = len(re.findall(r"<string\s", f.read()))
        except OSError:
            continue
        tag = (m.group(1) or "") + ("-" + m.group(2) if m.group(2) else "")
        counts[tag] = counts.get(tag, 0) + n
    return counts


_NOT_LANGUAGES = {"car", "ldltr", "ldrtl", "land", "port", "long", "notlong", "night", "notnight", "round",
                  "desk", "watch", "tv", "vr", "hdr", "mdpi", "hdpi", "ldpi"}
"""Qualifiers of two or three lowercase letters (or the shape of one) that are not languages."""


def strings_smali(root: str) -> str:
    """seekpatch.Strings for the decoded app at root."""
    languages = app_languages(root)
    table = translations()
    english = sorted({text for strings in table.values() for text in strings})
    fields = [_field("languages", ",".join(languages)), _field("english", SEPARATOR.join(english))]
    for lang in sorted({tag.split("-")[0] for tag in languages} & set(table)):
        fields.append(_field(lang, SEPARATOR.join(table[lang].get(text, "") for text in english)))
    return (".class public final Lseekpatch/Strings;\n"
            ".super Ljava/lang/Object;\n"
            '.source "seek-thermal-apk-patches"\n\n'
            "# seek-thermal-apk-patches: the languages of the app's own text, and the patches' text in them\n"
            "# (src/seekpatch/strings), for seekpatch.Lang\n"
            + "\n".join(fields))


def _field(name: str, value: str) -> str:
    return f'.field public static {name}:Ljava/lang/String; = "{_literal(value)}"\n'


def _literal(s: str) -> str:
    """A smali string literal's body: ASCII, everything else as \\uXXXX (UTF-16)."""
    out = []
    for ch in s:
        if ch == "\\" or ch == '"':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif " " <= ch <= "~":
            out.append(ch)
        else:
            units = ch.encode("utf-16-be")
            out.extend(f"\\u{units[i]:02x}{units[i + 1]:02x}" for i in range(0, len(units), 2))
    return "".join(out)
