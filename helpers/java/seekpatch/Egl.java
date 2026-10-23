package seekpatch;

import android.opengl.EGL14;
import android.opengl.EGLDisplay;
import android.opengl.EGLSurface;

/**
 * seek-patch resume_fix: let go of the live view's window when its GL thread stops.
 *
 * <p>When the app pauses, the GL thread drops its window surface without destroying it, so the EGL
 * surface stays connected to the view's window.  If the window survives the pause -- a permission
 * dialog or any other translucent activity on top -- the next GL thread cannot connect to it
 * (eglCreateWindowSurface: "already connected", EGL_BAD_ALLOC) and its first draw throws.
 * {@link #releaseWindow} runs on the GL thread right before that drop.
 */
public final class Egl {
    private Egl() {
    }

    public static void releaseWindow() {
        EGLDisplay display = EGL14.eglGetCurrentDisplay();
        if (display == null || display.equals(EGL14.EGL_NO_DISPLAY)) {
            return;
        }
        EGLSurface draw = EGL14.eglGetCurrentSurface(EGL14.EGL_DRAW);
        EGLSurface read = EGL14.eglGetCurrentSurface(EGL14.EGL_READ);
        EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT);
        if (draw != null && !draw.equals(EGL14.EGL_NO_SURFACE)) {
            EGL14.eglDestroySurface(display, draw);
        }
        if (read != null && !read.equals(EGL14.EGL_NO_SURFACE) && !read.equals(draw)) {
            EGL14.eglDestroySurface(display, read);
        }
    }
}
