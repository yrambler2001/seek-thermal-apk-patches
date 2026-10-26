package seekpatch;

import android.os.Build;
import android.os.Process;
import android.view.Surface;

/**
 * seek-thermal-apk-patches steady_fps: keep the live view at the camera's own frame rate.
 *
 * <p>Three things made a ~32 fps camera look like 28 - 30 fps with stutter:
 * <ul>
 * <li>The screen.  Nothing tells the system how fast the live view runs, so it guesses from the
 *     frames: about 30 a second, so 30 Hz, and every second or so a frame is dropped and the next
 *     one shown twice as long.  {@link #surface} asks for the screen's top rate; the system gives
 *     what it allows (an app that has a camera open gets at most 60 Hz).
 * <li>The camera's USB thread.  The library sets it to Java's top priority, but it is a HandlerThread,
 *     which resets itself to normal priority when it starts.  Behind the phone camera's own threads it
 *     waited up to 22 ms for a CPU, the next frame request went out too late and the camera skipped a
 *     frame.  {@link #usbThread} and {@link #frameLoop} (the thread that queues each request) run at
 *     the priority Android gives audio threads; {@link #glThread} at the one of its UI render thread.
 * <li>Uneven processing.  Each frame took 7 - 23 ms from the camera to the screen, so frames that
 *     arrive every 31 ms reached the screen 20 - 40 ms apart.  {@link #arrived} notes when each frame
 *     came in, and {@link #present} gives every frame the same delay from there: just more than the
 *     slowest recent frames needed, plus what the system needs to put a finished frame on the screen.
 * </ul>
 */
public final class Steady {
    /** The screen rate the live view asks for; the system picks the nearest rate it may use. */
    private static final float SCREEN_RATE = 120f;
    /** Nice values: the USB request path like an audio thread, the GL thread like Android's RenderThread. */
    private static final int USB_PRIORITY = -19;
    private static final int GL_PRIORITY = -10;

    private static final long MS = 1000000L;
    /** A frame is drawn at least this long after it arrived (the library's processing alone takes longer). */
    private static final long MIN_DRAW_DELAY = 4 * MS;
    /** Between a finished frame and the screen: one 60 Hz refresh plus the system's composition, and the GPU. */
    private static final long LEAD = 20 * MS;
    private static final long MIN_DELAY = 30 * MS;
    private static final long MAX_DELAY = 80 * MS;
    private static final long STALE = 200 * MS;

    private static final long[] ARRIVED = new long[8];
    private static int arrivedNext;
    private static final long[] DRAWN = new long[32];
    private static int drawnNext;
    private static int drawnCount;

    private Steady() {
    }

    private static void priority(int nice) {
        try {
            Process.setThreadPriority(nice);
        } catch (RuntimeException e) {
            // keep the thread's priority
        }
    }

    /** The camera library's USB thread (onLooperPrepared): it asks the camera for each frame. */
    public static void usbThread() {
        priority(USB_PRIORITY);
    }

    /** The library's frame loop (top of run()): it queues the next frame request. */
    public static void frameLoop() {
        priority(USB_PRIORITY);
    }

    /** The live view's GL thread (onLooperPrepared). */
    public static void glThread() {
        priority(GL_PRIORITY);
    }

    /** The live view's window, before the GL thread makes its EGL surface. */
    public static void surface(Surface surface) {
        if (Build.VERSION.SDK_INT < 30 || surface == null) {
            return;
        }
        try {
            surface.setFrameRate(SCREEN_RATE, Surface.FRAME_RATE_COMPATIBILITY_DEFAULT);
        } catch (RuntimeException e) {
            // the system picks the rate
        }
    }

    /** The camera library has the whole of a frame (on its USB thread). */
    public static void arrived() {
        long now = System.nanoTime();
        synchronized (ARRIVED) {
            ARRIVED[arrivedNext++ & 7] = now;
        }
    }

    /** The presentation time for the frame the GL thread draws now: its arrival plus a steady delay. */
    public static long present(long now) {
        long frame = 0;
        synchronized (ARRIVED) {
            for (long t : ARRIVED) {
                if (t != 0 && now - t >= MIN_DRAW_DELAY && t > frame) {
                    frame = t;
                }
            }
        }
        if (frame == 0 || now - frame > STALE) {
            return now;
        }
        DRAWN[drawnNext++ & 31] = now - frame;
        if (drawnCount < 32) {
            drawnCount++;
        }
        long when = frame + delay();
        return when > now ? when : now;
    }

    /** The third slowest draw of the last 32 frames plus LEAD: a lone slow frame does not move it. */
    private static long delay() {
        long[] d = new long[drawnCount];
        System.arraycopy(DRAWN, 0, d, 0, drawnCount);
        java.util.Arrays.sort(d);
        long slow = d[Math.max(0, drawnCount - 3)];
        return Math.max(MIN_DELAY, Math.min(MAX_DELAY, slow + LEAD));
    }
}
