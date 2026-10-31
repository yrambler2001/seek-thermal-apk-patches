package seekpatch;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.opengl.GLES20;
import android.util.Log;

/**
 * seek-thermal-apk-patches rotation: the thermal picture turned by 90, 180 or 270 degrees and / or mirrored
 * (horizontally, vertically or both), in the live view, in videos and in photos, while what the app draws over
 * it -- the markers with their temperatures, the temperature bar, the frame-rate box -- stays where it is and
 * upright.  Each marker moves with its point of the picture.
 *
 * <p>Coordinates here are the frame's: the 4:3 thermal texture, and the overlay and photo canvas laid over it,
 * centred and normalised to -0.5 .. 0.5 on both axes, x along the sensor's long side.  The app shows the frame
 * turned 90 degrees clockwise on its portrait screen; "clockwise", "horizontally" (left and right swap) and
 * "vertically" (top and bottom swap) are as the user sees them, the mirroring after the turn.  A picture turned
 * by 90 or 270 degrees is shrunk to fit the frame (to 3/4) and the rest is black.
 * <pre>
 *     uniform()          before each draw of the live view and the video: the shader's thermalTurn
 *     markerX / markerY  the marker method's x, y: where that point of the picture is now
 *     photo / drawn      around the photo's drawBitmap of the frame: the photo canvas turned the same way
 *     bitmap             Photo1x's copy, turned the same way (at its own size: no black)
 * </pre>
 * {@link #set} is called by RotationSettings, with the settings.
 */
public final class Rotation {
    private static final String TAG = "seek-thermal-apk-patches";
    /** The frame's width to height as shown: the app stretches every sensor's picture to 4:3. */
    private static final float ASPECT = 4f / 3f;
    private static final int GL_CURRENT_PROGRAM = 0x8b8d;
    private static final float[] IDENTITY = {1, 0, 0, 1};

    private static volatile int degrees;
    private static volatile boolean horizontal;
    private static volatile boolean vertical;
    /** Picture -> frame, row-major {a, b, c, d}: f = (a x + b y, c x + d y). */
    private static volatile float[] toFrame = IDENTITY;
    /** The shader's thermalTurn: frame -> picture minus the identity, column-major.  All zero, the uniform's
     * initial value, leaves the picture as it is. */
    private static volatile float[] uniform = new float[4];

    private static Canvas turnedCanvas;  // the photo canvas between photo() and drawn()
    private static int turnedCount;

    private Rotation() {
    }

    /** RotationSettings: turned clockwise by degrees (0, 90, 180 or 270), then mirrored: left and right swapped
     * (mirrorX), top and bottom swapped (mirrorY). */
    public static synchronized void set(int clockwise, boolean mirrorX, boolean mirrorY) {
        int d = (clockwise % 360 + 360) % 360 / 90 * 90;
        // In the frame's own units F = (ASPECT x, y), y down, a turn on the screen is the same turn of F (the
        // screen shows F turned by 90 degrees clockwise): the screen's left to right is F's -y, its top to bottom
        // F's x.  Picture -> frame: F = k M R F', R the clockwise turn, M = diag(my, mx) the mirroring (-1 where
        // it swaps), k = 3/4 when turned sideways.
        int cos = d == 0 ? 1 : d == 180 ? -1 : 0;
        int sin = d == 90 ? 1 : d == 270 ? -1 : 0;
        float k = d % 180 == 0 ? 1f : 1f / ASPECT;
        float my = mirrorY ? -1f : 1f;
        float mx = mirrorX ? -1f : 1f;
        toFrame = d == 0 && !mirrorX && !mirrorY ? IDENTITY
                : new float[] {k * my * cos, -k * my * sin / ASPECT, k * mx * sin * ASPECT, k * mx * cos};
        // frame -> picture, the inverse: (1 / k) {my cos, mx sin / ASPECT, -ASPECT my sin, mx cos}
        float a = my * cos / k;
        float b = mx * sin / ASPECT / k;
        float c = -ASPECT * my * sin / k;
        float e = mx * cos / k;
        uniform = new float[] {a - 1, c, b, e - 1};
        degrees = d;
        horizontal = mirrorX;
        vertical = mirrorY;
    }

    /** The shader program in use (right before glDrawArrays): thermalTurn, if it has it.  Looked up at every call,
     * as SharpScale does: the video encoder may draw from another thread. */
    public static void uniform() {
        int[] program = new int[1];
        GLES20.glGetIntegerv(GL_CURRENT_PROGRAM, program, 0);
        if (program[0] == 0) {
            return;
        }
        int at = GLES20.glGetUniformLocation(program[0], "thermalTurn");
        if (at >= 0) {
            GLES20.glUniformMatrix2fv(at, 1, false, uniform, 0);
        }
    }

    /** The marker method's x: the app put the marker at (x, y) of the canvas for the picture as it was. */
    public static float markerX(Canvas c, float x, float y) {
        float[] t = toFrame;
        float w = c.getWidth();
        float h = c.getHeight();
        if (t == IDENTITY || w <= 0 || h <= 0) {
            return x;
        }
        return (t[0] * (x / w - 0.5f) + t[1] * (y / h - 0.5f) + 0.5f) * w;
    }

    /** The marker method's y, from the same (x, y) as {@link #markerX}. */
    public static float markerY(Canvas c, float x, float y) {
        float[] t = toFrame;
        float w = c.getWidth();
        float h = c.getHeight();
        if (t == IDENTITY || w <= 0 || h <= 0) {
            return y;
        }
        return (t[2] * (x / w - 0.5f) + t[3] * (y / h - 0.5f) + 0.5f) * h;
    }

    /**
     * Right before the photo's drawBitmap of the frame bitmap b (from src, or all of it, into dst): the canvas
     * cleared to black and turned as the live view is.  Where the app draws only a band of the frame (src, in
     * 16:9), the turn is the whole frame's, as on screen: src and dst are widened to all of the frame and the
     * canvas crops it.  {@link #drawn} undoes the turn after the draw.
     */
    public static void photo(Canvas c, Bitmap b, Rect src, Rect dst) {
        float[] t = toFrame;
        if (t == IDENTITY || c == null || b == null || dst == null || dst.isEmpty()) {
            return;
        }
        try {
            float left = dst.left;
            float top = dst.top;
            float right = dst.right;
            float bottom = dst.bottom;
            if (src != null && !src.isEmpty()) {
                float sx = dst.width() / (float) src.width();
                float sy = dst.height() / (float) src.height();
                left = dst.left - src.left * sx;
                top = dst.top - src.top * sy;
                right = left + b.getWidth() * sx;
                bottom = top + b.getHeight() * sy;
                src.set(0, 0, b.getWidth(), b.getHeight());
                dst.set(Math.round(left), Math.round(top), Math.round(right), Math.round(bottom));
            }
            float w = right - left;
            float h = bottom - top;
            float cx = (left + right) / 2;
            float cy = (top + bottom) / 2;
            // p' = centre + S toFrame S^-1 (p - centre), S = diag(w, h)
            float a = t[0];
            float bb = t[1] * w / h;
            float cc = t[2] * h / w;
            float d = t[3];
            Matrix turn = new Matrix();
            turn.setValues(new float[] {a, bb, cx - a * cx - bb * cy, cc, d, cy - cc * cx - d * cy, 0, 0, 1});
            synchronized (Rotation.class) {
                turnedCount = c.save();
                turnedCanvas = c;
            }
            c.drawColor(Color.BLACK);
            c.concat(turn);
        } catch (RuntimeException e) {
            Log.w(TAG, "rotation: photo not turned", e);
        }
    }

    /** Right after the photo's drawBitmap: the canvas as it was before {@link #photo}. */
    public static void drawn(Canvas c) {
        synchronized (Rotation.class) {
            if (c != null && c == turnedCanvas) {
                c.restoreToCount(turnedCount);
                turnedCanvas = null;
            }
        }
    }

    /** Photo1x's frame (sensor-sized, before it is turned upright), turned and mirrored as the picture is. */
    public static Bitmap bitmap(Bitmap b) {
        int d = degrees;
        boolean mx = horizontal;
        boolean my = vertical;
        if (b == null || d == 0 && !mx && !my) {
            return b;
        }
        Matrix turn = new Matrix();
        turn.setRotate(d);
        turn.postScale(my ? -1 : 1, mx ? -1 : 1);  // the bitmap's x is the screen's top to bottom
        return Bitmap.createBitmap(b, 0, 0, b.getWidth(), b.getHeight(), turn, false);
    }
}
