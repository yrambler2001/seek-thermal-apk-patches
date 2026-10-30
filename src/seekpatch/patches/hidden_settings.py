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

Each switch also gets a line under its title on what it does (seekpatch.Hidden, after the Settings
screen's addPreferencesFromResource -- the PreferenceFragment that inflates in onCreate and names
"image_and_video"), and the four titles the app has in English only are shown in the app's language.  What
two of them do depends on the version, found in the app and written into Hidden.facts:

    registration   the app registers cameras ("https://register.thermal.com"): Disable Registration and Use
                   Staging Server act on it (up to 2.2.3); without it they do nothing (2.3.0 on)
    tiff           Store All Thermal Data saves a TIFF with each photo ("_thermo_", 2.1.1 on); without it
                   that switch gets no line

Versions: the five switches are in 2.0 - 2.3.4; 1.9.5 has four (no Show Frame Rate), 1.9.3 - 1.9.4
only Disable Registration.  The patch changes the readers it finds and refuses when there is none.
1.9.x has another settings screen: no lines there.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import GAP, REG, PatchError, SmaliTree, class_descriptor, methods
from .base import ensure_unpatched, mark
from .settings import inflating_fragment

NAME = "hidden_settings"
SUMMARY = "Settings always shows the app's hidden switches (Show Frame Rate, Save Uncompressed, ...), each saying what it does"
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
SCREEN = "Lseekpatch/Hidden;->screen(Landroid/preference/PreferenceFragment;)V"
FACTS = ".field static facts:Ljava/lang/String;\n"
FOUND = {  # Hidden.facts: what the app does, found by a string of its own
    "registration": '"https://register.thermal.com"',  # the camera registration's server, up to 2.2.3
    "tiff": '"_thermo_"',  # the name of Store All Thermal Data's TIFF, 2.1.1 on
}


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


def _descriptions(tree: SmaliTree) -> str:
    """Hidden.screen after the Settings screen's own preferences, with what the app does; a report line."""
    try:
        path, after_add, indent = inflating_fragment(tree, NAME, "image_and_video", "the Settings screen")
    except PatchError:
        return "no descriptions: the switches are not on a Settings screen of 2.0's (1.9.x)"
    facts = [fact for fact, needle in FOUND.items() if tree.containing(needle)]  # before our own text comes in
    text = tree.get(path)
    hook = (f"\n{indent}{MARK}: what each switch does, under its title\n"
            f"{indent}invoke-static/range {{p0 .. p0}}, {SCREEN}\n")
    tree.set(path, text[:after_add] + hook + text[after_add:])
    add_helpers(tree, "Hidden")
    hidden = tree.path_of("Lseekpatch/Hidden;")
    text = tree.get(hidden)
    if text.count(FACTS) != 1:
        raise PatchError(f"{NAME}: seekpatch.Hidden has no field facts to write")
    tree.set(hidden, text.replace(FACTS, FACTS[:-1] + f' = "{",".join(facts)}"\n'))
    fragment = class_descriptor(tree.get(path)).split("/")[-1][:-1]
    registration = "registers cameras" if "registration" in facts else "no camera registration"
    tiff = "TIFF with each photo" if "tiff" in facts else "no TIFF"
    return f"{fragment}.onCreate -> Hidden.screen: what each switch does, under its title ({registration}, {tiff})"


def apply(tree: SmaliTree) -> list[str]:
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
    report.append(_descriptions(tree))
    return report
