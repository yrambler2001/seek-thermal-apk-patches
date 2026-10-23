# `resume_fix` — no crash after a dialog

**Stock:** coming back from Android's permission dialog — the app shows it for the microphone —
kills the app: `FATAL EXCEPTION: ThermalPlusRenderThread … draw start: glError 0x506`.
**Patched:** the live view comes back.

When the app pauses it stops the live view's GL thread, and that thread drops its window surface —
sets the field to `null` — without destroying the EGL surface behind it.  Going home destroys the
view's window anyway, so nobody notices.  A translucent activity on top (Android's permission
dialog is one) pauses the app but leaves the window alive, still connected to the old EGL surface,
and on resume the new GL thread cannot connect to it:

```
BufferQueueProducer: connect: already connected (cur=1 req=1)
libEGL: eglCreateWindowSurface: native_window_api_connect ... failed (already connected to another API?)
libEGL: eglCreateWindowSurfaceTmpl:706 error 3003 (EGL_BAD_ALLOC)
Grafika: draw start: glError 0x506
```

`0x506` is `GL_INVALID_FRAMEBUFFER_OPERATION`: drawing with no surface.  The patch calls
`seekpatch.Egl.releaseWindow()` right before the drop.  On the GL thread, it makes nothing current and
destroys the surface that was, which disconnects it from the window.

The code is the same since 1.9.1, the release with names kept: `RenderManager`'s pause runnable
calls `suspendRenderer()`, deletes the textures and sets `previewWindow` to `null`.

Versions: 1.9.1 – 2.3.4.  Source: [`helpers/java/seekpatch/Egl.java`](../helpers/java/seekpatch/Egl.java).
