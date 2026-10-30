"""The patches' text in other languages (src/seekpatch/strings): every string the Java helpers show
is translated into every language, with the same format specifiers; and the app's own languages are
read from its resources."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from seekpatch import strings

HELPERS = Path(__file__).resolve().parent.parent / "helpers" / "java" / "seekpatch"
LITERAL = r'"(?:[^"\\]|\\.)*"'
SPECIFIER = re.compile(r"%(?:\d+\$)?[sd]|%%")


def _shown() -> dict[str, str]:
    """English text the helpers pass to Lang.t / Lang.f -> "t" or "f" (a literal, literals joined with +, or
    a static final String constant of the same file)."""
    found: dict[str, str] = {}
    for f in sorted(HELPERS.glob("*.java")):
        src = f.read_text(encoding="utf-8")
        constants = {m.group(1): json.loads(m.group(2))
                     for m in re.finditer(r"static final String (\w+) = (" + LITERAL + r");", src)}
        for m in re.finditer(r"Lang\.([tf])\(\s*((?:" + LITERAL + r"\s*\+\s*)*" + LITERAL + r"|[A-Z_]+)\s*[,)]", src):
            arg = m.group(2)
            text = constants[arg] if arg in constants else "".join(json.loads(x) for x in re.findall(LITERAL, arg))
            assert found.get(text, m.group(1)) == m.group(1), f"{text!r} is both a pattern and plain text"
            found[text] = m.group(1)
    return found


SHOWN = _shown()
TRANSLATIONS = strings.translations()


def test_the_helpers_text_is_found():
    assert len(SHOWN) > 70 and SHOWN["Flat field"] == "t" and SHOWN["%s (default)"] == "f"
    assert SHOWN["Patched by yrambler2001"] == "t"  # through a constant


def test_the_seek_languages_are_translated():
    # Seek's own languages; Portugal's Portuguese takes "pt"
    assert sorted(TRANSLATIONS) == ["de", "es", "fr", "it", "ja", "ko", "nl", "pt", "ru", "zh"]


@pytest.mark.parametrize("lang", sorted(TRANSLATIONS))
def test_every_string_is_translated(lang):
    table = TRANSLATIONS[lang]
    assert sorted(set(SHOWN) - set(table)) == [], "not translated"
    assert sorted(set(table) - set(SHOWN)) == [], "no helper shows it any more"
    for english, text in table.items():
        assert text.strip() and text == text.strip() and strings.SEPARATOR not in text, english
        if SHOWN[english] == "f":  # String.format: the same values, and no stray %
            assert sorted(SPECIFIER.findall(text)) == sorted(SPECIFIER.findall(english)), english
            assert re.sub(SPECIFIER, "", text).count("%") == 0, english
        else:
            assert not re.search(r"%(?:\d+\$)?[sd]", text), english


def test_no_text_bypasses_lang():
    """Text the helpers put on screen goes through Lang: no bare literal (but the "%s" summary format of a list)."""
    shown = re.compile(r"(?:\.set(?:Text|Title|Message|Summary|DialogTitle)\(|\.set(?:Positive|Negative|Neutral)Button\(|"
                       r"makeText\([^,]+,\s*|Floating\.button\([^,]+,\s*|Settings\.add(?:Switch|List)\((?:[^,]+,){3}\s*)"
                       r"(" + LITERAL + ")")
    bare = [(f.name, m.group(1)) for f in sorted(HELPERS.glob("*.java"))
            for m in shown.finditer(f.read_text(encoding="utf-8")) if m.group(1) != '"%s"']
    assert bare == []


def test_app_languages_from_resources_arsc(make_project):
    # the fixture app: German, Russian, some Portugal Portuguese; one library string in Ukrainian, en-US
    assert strings.app_languages(str(make_project("lambda"))) == ["de", "pt-PT", "ru"]


def test_app_languages_from_decoded_resources(tmp_path):
    def values(qualifier: str, n: int) -> None:
        d = tmp_path / "res" / ("values" + qualifier)
        d.mkdir(parents=True)
        items = "".join(f'    <string name="s{i}">x</string>\n' for i in range(n))
        (d / "strings.xml").write_text(f"<resources>\n{items}</resources>\n", encoding="utf-8")

    for qualifier, n in (("", 8), ("-de", 6), ("-de-v21", 1), ("-pt-rPT", 2), ("-uk", 1), ("-en-rUS", 8),
                         ("-w600dp", 8), ("-night", 8), ("-land", 8)):
        values(qualifier, n)
    assert strings.app_languages(str(tmp_path)) == ["de", "pt-PT"]


def test_no_resources_no_languages(tmp_path):
    assert strings.app_languages(str(tmp_path)) == []
    assert '.field public static languages:Ljava/lang/String; = ""' in strings.strings_smali(str(tmp_path))
