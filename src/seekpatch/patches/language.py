"""language: a Language list at the top of the app's Settings: the phone's language, or any other the
app has its own text in.

The app only follows the phone's language.  The patch adds the list (seekpatch.Language) after the
Settings screen's addPreferencesFromResource -- the one PreferenceFragment that inflates its
preferences in onCreate and names "image_and_video", the entry that opens Image & Video -- and the
choice is applied by seekpatch.Lang:

    Android 13+        the app's language in the system (LocaleManager.setApplicationLocales), which
                       keeps it and recreates the app's screens
    before Android 13  kept in the seekpatch preferences; every activity's attachBaseContext passes its
                       context through Lang.wrap, which overrides the locale and nothing else (the rest
                       of the configuration follows the phone, also after a rotation), and a screen
                       made before the choice changed is recreated when it comes back

attachBaseContext is added to (or hooked at the start of, where a class has one) every class whose
superclass is one of Android's activity classes, so that every activity of the app inherits it.

The languages offered are the app's own, counted in its resources.arsc when it is patched (see
src/seekpatch/strings): from 1.9.5 on German, Spanish, French, Italian, Japanese, Korean, Dutch,
Portuguese (and Portugal's), Russian and Chinese -- as far as the file has them: a split bundle has
the language splits its source chose (APKPure's 2.3.x have no Dutch).  The patches' own text follows the
app's language in every patch, with this one or without it (seekpatch.Lang, src/seekpatch/strings).

Versions: the Settings screen with its "image_and_video" entry is in 2.0 - 2.3.4; 1.9.x has another
settings screen, which the patch refuses.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import PatchError, SmaliTree, class_descriptor, code_start, methods
from .base import ensure_unpatched, mark
from .settings import inflating_fragment

NAME = "language"
SUMMARY = "a Language list at the top of Settings: the phone's language or any other the app has"
VERSIONS = "2.0 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
SCREEN = "Lseekpatch/Language;->screen(Landroid/preference/PreferenceFragment;)V"
WRAP = "Lseekpatch/Lang;->wrap(Landroid/content/Context;)Landroid/content/Context;"
ATTACH = "attachBaseContext(Landroid/content/Context;)V"
ACTIVITIES = ("Landroid/app/Activity;", "Landroid/app/ListActivity;", "Landroid/app/ExpandableListActivity;",
              "Landroid/app/TabActivity;", "Landroid/app/ActivityGroup;", "Landroid/app/AliasActivity;",
              "Landroid/app/LauncherActivity;", "Landroid/app/NativeActivity;",
              "Landroid/preference/PreferenceActivity;", "Landroid/accounts/AccountAuthenticatorActivity;")
"""Android's activity classes: an activity of the app extends one of them, directly or through its own
or a library's classes."""
NEW_METHOD = """
.method protected attachBaseContext(Landroid/content/Context;)V
    .locals 0

    {mark}: the activity's resources in the language chosen in Settings
    invoke-static {{p1}}, {wrap}

    move-result-object p1

    invoke-super {{p0, p1}}, {base}->attachBaseContext(Landroid/content/Context;)V

    return-void
.end method
"""


def _wrap(tree: SmaliTree, path: str, base: str) -> str:
    """attachBaseContext of one class: Lang.wrap at the start of its own, or a new one; returns its name."""
    text = tree.get(path)
    own = [m for m in methods(text) if m.descriptor == ATTACH]
    if len(own) > 1:
        raise PatchError(f"{NAME}: {tree.rel(path)} has {len(own)} attachBaseContext methods")
    if own:
        m = own[0]
        start = code_start(m.body)
        indent = re.match(r"[ \t]*", m.body[start:]).group(0)
        hook = (f"{indent}{MARK}: the activity's resources in the language chosen in Settings\n"
                f"{indent}invoke-static/range {{p1 .. p1}}, {WRAP}\n\n"
                f"{indent}move-result-object p1\n\n")
        tree.replace_method_body(path, m, m.body[:start] + hook + m.body[start:])
    else:
        tree.set(path, text.rstrip("\n") + "\n" + NEW_METHOD.format(mark=MARK, wrap=WRAP, base=base))
    return class_descriptor(text)


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    path, after_add, indent = inflating_fragment(tree, NAME, "image_and_video", "the Settings screen")
    text = tree.get(path)
    hook = f"\n{indent}{MARK}: the Language list, at the top\n{indent}invoke-static/range {{p0 .. p0}}, {SCREEN}\n"
    tree.set(path, text[:after_add] + hook + text[after_add:])
    wrapped = []
    for base in ACTIVITIES:
        for p in sorted(tree.containing(f"\n.super {base}\n")):
            wrapped.append(_wrap(tree, p, base))
    if not wrapped:
        raise PatchError(f"{NAME}: no class extends one of Android's activity classes")
    add_helpers(tree, "Language", "Lang")
    fragment = class_descriptor(tree.get(path))
    names = ", ".join(sorted(d.split("/")[-1][:-1] for d in wrapped))
    return [f"{fragment.split('/')[-1][:-1]}.onCreate -> Language.screen: the Language list at the top of Settings",
            f"attachBaseContext -> Lang.wrap in {len(wrapped)} activity base classes ({names})"]
