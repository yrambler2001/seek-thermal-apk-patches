"""hidden_settings: Settings always shows the app's hidden switches.

The app hides five switches in Settings until About -> "Image Processing Software" is tapped five times
(five more taps hide them again):

    Save Uncompressed      lossless_comp_key          allowed by lossless_comp_allowed_key
    Set Simulation Mode    sim_mode_key               allowed by sim_mode_allowed_key
    Show Frame Rate        video_export_frame_rate    allowed by export_frame_rate_allowed_key
    Disable Registration   disable_registration_key   allowed by allow_reg_optout_key
    Use Staging Server     use_staging_server_key     allowed by staging_registration_allowed_key

The settings screen removes each switch whose "allowed" preference is false, read by a static
(Context)Z method around getBoolean(key, false); nothing else reads them.  The patch has each of those
readers return true.  With png_photos, which forces Save Uncompressed on from Android 11, that switch's
reader returns true only before Android 11, so it is not shown where it would do nothing.

Versions: the five switches are in 2.0 - 2.3.4; 1.9.5 has four (no Show Frame Rate), 1.9.3 - 1.9.4
only Disable Registration.  The patch changes the readers it finds and refuses when there is none.
"""
from __future__ import annotations

import re

from ..smali import GAP, REG, PatchError, SmaliTree, methods
from .base import Options, ensure_unpatched, mark

NAME = "hidden_settings"
SUMMARY = "Settings always shows the app's hidden switches (Show Frame Rate, Save Uncompressed, ...)"
VERSIONS = "1.9.3 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
GET_BOOLEAN = "Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z"
READER = "(Landroid/content/Context;)Z"
SWITCHES = {  # allowed-key: the switch it shows
    "lossless_comp_allowed_key": "Save Uncompressed",
    "sim_mode_allowed_key": "Set Simulation Mode",
    "export_frame_rate_allowed_key": "Show Frame Rate",
    "allow_reg_optout_key": "Disable Registration",
    "staging_registration_allowed_key": "Use Staging Server",
}
LOSSLESS = "lossless_comp_allowed_key"
ANDROID_11 = 30


def _reader(tree: SmaliTree, key: str) -> tuple[str, str] | None:
    """The reader of one allowed-key made to return true; (path, method name), None when the app has
    no such key."""
    if not tree.containing(f'"{key}"'):
        return None
    read = re.compile(r'const-string (' + REG + r'), "' + re.escape(key) + r'"\n(?:.*\n)*?[ \t]*invoke-interface \{'
                      + REG + r", \1, " + REG + r"\}, " + re.escape(GET_BOOLEAN) + GAP + r"move-result (" + REG + r")\n")
    sites = [(p, m, h) for p in tree.containing(f'"{key}"', GET_BOOLEAN) for m in methods(tree.get(p))
             if m.descriptor.endswith(READER) and "static" in m.header.split() for h in [read.search(m.body)] if h]
    if len(sites) != 1:
        raise PatchError(f"{NAME}: expected one static {READER} reader of {key}, found {len(sites)}")
    path, m, h = sites[0]
    reg = h.group(2)
    indent = re.match(r"[ \t]*", m.body[m.body.rfind("\n", 0, h.end() - 1) + 1:]).group(0)
    if key == LOSSLESS and tree.containing(mark("png_photos")):
        hook = (f"\n{indent}{MARK}: shown before Android 11 only: from 11 png_photos forces it on\n"
                f"{indent}sget {reg}, Landroid/os/Build$VERSION;->SDK_INT:I\n\n"
                f"{indent}add-int/lit8 {reg}, {reg}, -{ANDROID_11:#x}\n\n"
                f"{indent}ushr-int/lit8 {reg}, {reg}, 0x1f\n")
    else:
        hook = f"\n{indent}{MARK}: always shown\n{indent}const/4 {reg}, 0x1\n"
    body = m.body[:h.end()] + hook + m.body[h.end():]
    tree.replace_method_body(path, m, body)
    return tree.rel(path), m.name


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    report = []
    for key, switch in SWITCHES.items():
        found = _reader(tree, key)
        if found:
            note = " (before Android 11: png_photos forces it on from 11)" if key == LOSSLESS and tree.containing(
                mark("png_photos")) else ""
            report.append(f"{found[0]} {found[1]}(): {key} is true -- {switch} shown{note}")
    if not report:
        raise PatchError(f"{NAME}: none of the hidden switches' allowed-keys ({', '.join(SWITCHES)}) is in the app")
    return report
