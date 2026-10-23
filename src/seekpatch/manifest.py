"""--side-by-side: give the decoded (text) manifest a new package name and label, so the patched
app installs next to the store app instead of replacing it.

Only identities are renamed: the package attribute, content-provider authorities and custom
permissions that live under the old package.  Component class names are left alone (the code is
not renamed) -- relative ones (".MainActivity") are expanded first, since they would otherwise
resolve against the new package.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

COMPONENTS = ("application", "activity", "activity-alias", "service", "receiver", "provider")


class ManifestError(Exception):
    pass


_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")


def valid_package(name: str) -> bool:
    """An Android application id: two or more dot-separated Java-style segments."""
    return bool(_PACKAGE.fullmatch(name))


def package_of(xml: str) -> str:
    m = re.search(r'<manifest\b[^>]*?\spackage="([^"]+)"', xml, re.S)
    if not m:
        raise ManifestError("no package attribute on <manifest>")
    return m.group(1)


def _under(value: str, old: str) -> bool:
    return value == old or value.startswith(old + ".")


def rename(xml: str, new_package: str, label: str | None) -> tuple[str, list[str]]:
    old = package_of(xml)
    if not valid_package(new_package):
        raise ManifestError(f"not a valid package name: {new_package}")
    if new_package == old:
        raise ManifestError("the new package name equals the old one")
    notes = [f"package {old} -> {new_package}"]

    # relative component names -> fully qualified against the old package
    def expand(m: re.Match) -> str:
        tag = m.group(0)
        return re.sub(r'(\sandroid:name=")\.', lambda n: f"{n.group(1)}{old}.", tag)
    xml = re.sub(r"<(?:" + "|".join(COMPONENTS) + r")\b[^>]*>", expand, xml, flags=re.S)

    # provider authorities under the old package
    def authorities(m: re.Match) -> str:
        values = [new_package + v[len(old):] if _under(v, old) else v for v in m.group(2).split(";")]
        return m.group(1) + ";".join(values) + '"'
    xml, n = re.subn(r'(\sandroid:authorities=")([^"]*)"', authorities, xml)
    if n:
        notes.append(f"{n} provider authorit{'y' if n == 1 else 'ies'}")

    # custom permissions declared under the old package, and every reference to them
    declared = re.findall(r'<permission\b[^>]*?\sandroid:name="([^"]+)"', xml, re.S)
    for perm in (p for p in declared if _under(p, old)):
        xml = xml.replace(f'"{perm}"', f'"{new_package}{perm[len(old):]}"')
        notes.append(f"permission {perm}")

    xml = re.sub(r'(<manifest\b[^>]*?\spackage=")[^"]+"', lambda m: m.group(1) + new_package + '"', xml, count=1, flags=re.S)

    if label:
        lab = escape(label, {'"': "&quot;"})
        # the app label, and the launcher activity's own label if it sets one
        xml, n_app = re.subn(r'(<application\b[^>]*?\sandroid:label=")[^"]*"', lambda m: m.group(1) + lab + '"', xml,
                             count=1, flags=re.S)
        if not n_app:
            xml = re.sub(r"<application\b", f'<application android:label="{lab}"', xml, count=1)
        for act in re.finditer(r"<activity(?=[\s>])[^>]*[^/]>.*?</activity>", xml, re.S):
            block = act.group(0)
            if "android.intent.category.LAUNCHER" in block and re.search(r'^<activity[^>]*?\sandroid:label="', block, re.S):
                new_block = re.sub(r'^(<activity[^>]*?\sandroid:label=")[^"]*"', lambda m: m.group(1) + lab + '"', block,
                                   count=1, flags=re.S)
                xml = xml.replace(block, new_block, 1)
        notes.append(f'label "{label}"')
    return xml, notes
