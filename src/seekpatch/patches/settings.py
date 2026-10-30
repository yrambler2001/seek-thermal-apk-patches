"""seek-thermal-apk-patches' settings in the app's Settings -> Image & Video screen, shared by the patches that have
any (smoothing_settings, flat_field, sharp_scaling, photo_1x, video_quality).

Two hooks, added once by whichever of those patches comes first, call the Java helper
seekpatch.Settings (helpers/java/seekpatch/Settings.java):

    the Image & Video fragment's onCreate, after addPreferencesFromResource
        -> Settings.screen(fragment): each patch's section appends its preferences
    the camera screen's onCreate, after setContentView
        -> Settings.attach(activity): the values are loaded before the first frame

The fragment is found by behaviour: the one PreferenceFragment that names the "Image smoothing"
preference ("use_smoothing", which it logs when it changes) and inflates its preferences in onCreate.
Resources are never read, so the hooks work with `apktool d -r` as well as with --side-by-side.
A patch adds its own section class (seekpatch.Filters, FlatSettings, Upscale, PhotoSettings,
VideoSettings); Settings finds them by name at run time.

seekpatch.Screens comes with Settings: from Settings.attach it makes the settings screens'
navigation bar dark (they have no theme, so Android 15+ draws them a light one) and puts a divider
and "Patched by yrambler2001 v<version>" below Send Feedback in the side menu.  The version is
seek-thermal-apk-patches', in a class written here (seekpatch.About).
"""
from __future__ import annotations

import re

from .. import __version__
from ..helpers import add_helpers
from ..smali import REG, PatchError, SmaliTree, class_descriptor, methods, smali_escape
from .base import mark
from .seek import camera_activity

FRAGMENT = "Landroid/preference/PreferenceFragment;"
ADD_PREFERENCES = "addPreferencesFromResource(I)V"
HELPER = "Lseekpatch/Settings;"
SCREEN = f"{HELPER}->screen({FRAGMENT})V"
ATTACH = f"{HELPER}->attach(Landroid/app/Activity;)V"
ABOUT = """.class public final Lseekpatch/About;
.super Ljava/lang/Object;
.source "seek-thermal-apk-patches"

{mark}: the version of seek-thermal-apk-patches that patched this app, shown in the side menu
.field public static version:Ljava/lang/String; = "{version}"
"""


def image_video_fragment(tree: SmaliTree, patch: str) -> tuple[str, int, str]:
    """(path, offset just past its addPreferencesFromResource call, indent) of the Image & Video fragment."""
    return inflating_fragment(tree, patch, "use_smoothing", "the Image & Video screen")


def inflating_fragment(tree: SmaliTree, patch: str, key: str, what: str) -> tuple[str, int, str]:
    """(path, offset just past its addPreferencesFromResource call, indent) of the one PreferenceFragment that
    names the preference key and inflates its preferences in onCreate."""
    hits = []
    for p in tree.containing(f'"{key}"', ADD_PREFERENCES):
        text = tree.get(p)
        if not re.search(r"^\.super " + re.escape(FRAGMENT) + "$", text, re.M):
            continue
        for m in methods(text):
            if m.descriptor == "onCreate(Landroid/os/Bundle;)V":
                calls = list(re.finditer(r"^([ \t]*)invoke-virtual \{p0, " + REG + r"\}, L[\w/$]+;->"
                                         + re.escape(ADD_PREFERENCES) + r"\n", text[m.start:m.end], re.M))
                hits += [(p, m.start + c.end(), c.group(1)) for c in calls]
    if len(hits) != 1:
        raise PatchError(f"{patch}: expected one PreferenceFragment that inflates its preferences in onCreate and "
                         f'names "{key}" ({what}), found {len(hits)}')
    return hits[0]


def installed(tree: SmaliTree) -> bool:
    return bool(tree.containing(SCREEN))


def install(tree: SmaliTree, patch: str) -> list[str]:
    """Add the two hooks and seekpatch.Settings, unless an earlier patch did.  Returns report lines."""
    if installed(tree):
        return []
    fragment_path, after_add, indent = image_video_fragment(tree, patch)
    activity_path, after_layout = camera_activity(tree, patch)
    text = tree.get(fragment_path)
    hook = (f"\n{indent}{mark(patch)}: seek-thermal-apk-patches' settings, after the screen's own\n"
            f"{indent}invoke-static/range {{p0 .. p0}}, {SCREEN}\n")
    tree.set(fragment_path, text[:after_add] + hook + text[after_add:])
    text = tree.get(activity_path)
    line_start = text.rfind("\n", 0, after_layout - 1) + 1
    indent = re.match(r"[ \t]*", text[line_start:]).group(0)
    hook = (f"\n{indent}{mark(patch)}: load seek-thermal-apk-patches' settings before the first frame\n"
            f"{indent}invoke-static/range {{p0 .. p0}}, {ATTACH}\n")
    tree.set(activity_path, text[:after_layout] + hook + text[after_layout:])
    add_helpers(tree, "Settings", "Screens")
    tree.add_class("Lseekpatch/About;", ABOUT.format(mark=mark(patch), version=smali_escape(__version__)))
    fragment = class_descriptor(tree.get(fragment_path))
    activity = class_descriptor(tree.get(activity_path))
    return [f"settings: {fragment.split('/')[-1][:-1]}.onCreate -> Settings.screen, "
            f"{activity.split('/')[-1][:-1]}.onCreate -> Settings.attach"]


def optional_settings(tree: SmaliTree, patch: str, section: str, what: str) -> list[str]:
    """For a patch whose settings are an extra: the hooks (unless there) and its section class, or
    nothing -- with the reason in the report -- where this release has no screen to put them on."""
    try:
        with tree.transaction():
            lines = install(tree, patch)
            add_helpers(tree, section)
    except PatchError as e:
        why = str(e)
        return [f"no settings: {why[len(patch) + 2:] if why.startswith(patch + ': ') else why}"]
    return lines + [f"settings: {what} (seekpatch.{section})"]
