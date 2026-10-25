"""no_analytics: Google Analytics never starts.

Every release bundles the Google Analytics SDK v3 (com.google.analytics.tracking.android), and up
to 2.3.1 the app reports screen views and events through it while *Settings -> Send Usage Data* is
on, as it is by default.  The SDK's thread waits 5 s, then binds to the analytics service of Google
Play services.  Play services no longer has one, so after two tries the SDK falls back to its own
hit store, whose dispatcher is Apache's DefaultHttpClient.  2.1.6 - 2.3.1 target API 28 - 34
without declaring org.apache.http.legacy, so on Android 9 and later that class is missing and the
app dies about 15 s after it starts:

    FATAL EXCEPTION: Service Reconnect
    java.lang.NoClassDefFoundError: Failed resolution of: Lorg/apache/http/impl/client/DefaultHttpClient;
        at com.google.analytics.tracking.android.PersistentAnalyticsStore.<init>

(Turning the switch off in time also stops it, but turning it off sends one last event first.)

The thread is found by its name ("GAThread") and its set-up failure log; its run() sets up the
service proxy -- the Play services connection, and through it the store and the HTTP dispatcher,
which nothing else creates -- then takes the app's work off a queue until closed, skipping it once
the SDK is disabled.  The patch replaces run(): the SDK's own disabled flag is set, as when its
set-up fails, and the queue is drained without running anything.  The app's calls into the SDK are
unchanged and go nowhere; the Send Usage Data switch stays and no longer does anything.
http_legacy declares the library instead, for the app's own uses of it.
"""
from __future__ import annotations

import re

from ..smali import GAP, REG, PatchError, SmaliTree, class_descriptor, methods
from .base import Options, ensure_unpatched, mark

NAME = "no_analytics"
SUMMARY = "Google Analytics never starts: nothing is sent (2.1.6 - 2.3.1 no longer crash 15 s after launch)"
VERSIONS = "1.9.1 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
FAILED = '"Google Analytics will not start up."'  # run()'s log when its set-up throws

# the work loop: until closed, take the next Runnable and run it unless disabled
LOOP = re.compile(
    r"iget-boolean (" + REG + r"), p0, (L[\w/$]+;)->([\w$]+):Z" + GAP + r"if-nez \1, :\w+" + GAP + r":try_start_\w+" + GAP
    + r"iget-object (" + REG + r"), p0, \2->([\w$]+):Ljava/util/concurrent/LinkedBlockingQueue;" + GAP
    + r"invoke-virtual \{\4\}, Ljava/util/concurrent/LinkedBlockingQueue;->take\(\)Ljava/lang/Object;" + GAP
    + r"move-result-object (" + REG + r")" + GAP + r"check-cast \6, Ljava/lang/Runnable;" + GAP
    + r"iget-boolean (" + REG + r"), p0, \2->([\w$]+):Z" + GAP + r"if-nez \7, :\w+" + GAP
    + r"invoke-interface \{\6\}, Ljava/lang/Runnable;->run\(\)V")

BODY = """    .locals 1

    {mark}: Google Analytics never starts -- disabled, as when its set-up fails, before it connects to anything
    const/4 v0, 0x1

    iput-boolean v0, p0, {cls}->{disabled}:Z

    {mark}: what the app queues is taken and dropped
    :seekpatch_next
    iget-boolean v0, p0, {cls}->{closed}:Z

    if-nez v0, :seekpatch_closed

    :seekpatch_try_start
    iget-object v0, p0, {cls}->{queue}:Ljava/util/concurrent/LinkedBlockingQueue;

    invoke-virtual {{v0}}, Ljava/util/concurrent/LinkedBlockingQueue;->take()Ljava/lang/Object;
    :seekpatch_try_end
    .catch Ljava/lang/InterruptedException; {{:seekpatch_try_start .. :seekpatch_try_end}} :seekpatch_next

    goto :seekpatch_next

    :seekpatch_closed
    return-void
"""


def apply(tree: SmaliTree, opts: Options) -> list[str]:
    ensure_unpatched(tree, NAME)
    threads = [p for p in tree.containing(FAILED, '"GAThread"')
               if re.search(r"^\.super Ljava/lang/Thread;$", tree.get(p), re.M)]
    if len(threads) != 1:
        raise PatchError(f"{NAME}: expected one Google Analytics thread (named GAThread, logging {FAILED}), "
                         f"found {len(threads)}")
    path = threads[0]
    text = tree.get(path)
    cls = class_descriptor(text)
    if not re.search(r'const-string (' + REG + r'), "GAThread"' + GAP + r"invoke-direct \{p0, \1\}, Ljava/lang/Thread;-><init>"
                     r"\(Ljava/lang/String;\)V", text):
        raise PatchError(f"{NAME}: {cls} does not name its thread GAThread")
    runs = [m for m in methods(text) if m.descriptor == "run()V" and FAILED in m.body]
    if len(runs) != 1:
        raise PatchError(f"{NAME}: expected one run() in {cls} that logs {FAILED}, found {len(runs)}")
    run = runs[0]
    loops = [lp for lp in LOOP.finditer(run.body) if lp.group(2) == cls]
    if len(loops) != 1:
        raise PatchError(f"{NAME}: expected one work loop (closed flag, queue take, disabled flag) in {cls} run(), "
                         f"found {len(loops)}")
    closed, queue, disabled = loops[0].group(3), loops[0].group(5), loops[0].group(8)
    # the service proxy: made from (Context, this) in run(), and nowhere else
    proxies = {c for r, c in re.findall(r"new-instance (" + REG + r"), (L[\w/$]+;)$", run.body, re.M)
               if re.search(r"invoke-direct \{" + r + ", " + REG + r", p0\}, " + re.escape(c)
                            + r"-><init>\(Landroid/content/Context;L[\w/$]+;\)V", run.body)}
    if len(proxies) != 1:
        raise PatchError(f"{NAME}: expected run() in {cls} to create one service proxy from (Context, this), "
                         f"found {len(proxies)}")
    proxy = proxies.pop()
    makers = [p for p in tree.containing(proxy)
              for _ in re.finditer(r"new-instance " + REG + ", " + re.escape(proxy) + "$", tree.get(p), re.M)]
    if len(makers) != 1:
        raise PatchError(f"{NAME}: {proxy} is created in {len(makers)} places, not only in {cls} run()")
    tree.replace_method_body(path, run, BODY.format(mark=MARK, cls=cls, closed=closed, queue=queue, disabled=disabled))
    return [f"{tree.rel(path)} run(): disabled before it starts ({disabled}), queue drained -- no {proxy}: "
            "no Google Play services connection, no hit store, nothing sent"]
