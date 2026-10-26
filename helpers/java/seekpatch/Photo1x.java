package seekpatch;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.media.MediaScannerConnection;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/**
 * seek-thermal-apk-patches photo_1x: with every photo, the thermal frame at the sensor's resolution as a PNG.
 *
 * <p>The photo method hands its frame bitmap (sensor-sized, colorized, no overlays) to
 * {@link #capture} before scaling it up; once the photo file is written, {@link #saved} stores the
 * frame next to it, in the same folder, under the photo's name with "_thermal" turned into "_1x"
 * (img_thermal_123.png -> img_1x_123.png).  Seek's own gallery lists only files whose path matches
 * "%Seek Thermal/%_thermal%", so it does not show the copy twice.  The pixels are turned upright by
 * the photo's EXIF orientation, which PNG viewers do not read.
 *
 * <p>{@link #enabled} is the <i>Also save a 1x PNG</i> setting (seekpatch.PhotoSettings, off by
 * default); without a settings screen it stays on.
 */
public final class Photo1x {
    private static final String TAG = "seek-thermal-apk-patches";

    public static volatile boolean enabled = true;

    private static Bitmap frame;
    private static Context context;

    private Photo1x() {
    }

    public static synchronized void capture(Context c, Bitmap bitmap) {
        context = c != null ? c.getApplicationContext() : null;
        frame = enabled ? bitmap : null;
    }

    public static void saved(File photo, int exifOrientation) {
        Bitmap bitmap;
        Context c;
        synchronized (Photo1x.class) {
            bitmap = frame;
            c = context;
            frame = null;
        }
        File dir = photo != null ? photo.getParentFile() : null;
        if (bitmap == null || bitmap.isRecycled() || dir == null) {
            return;
        }
        File out = new File(dir, name(photo.getName()));
        try {
            Bitmap upright = upright(bitmap, exifOrientation);
            OutputStream os = new FileOutputStream(out);
            try {
                if (!upright.compress(Bitmap.CompressFormat.PNG, 100, os)) {
                    throw new IOException("PNG encoder failed");
                }
            } finally {
                os.close();
            }
            if (c != null) {
                MediaScannerConnection.scanFile(c, new String[] {out.getPath()}, new String[] {"image/png"}, null);
            }
        } catch (IOException | RuntimeException e) {
            Log.w(TAG, "photo_1x: " + out + ": " + e);
        }
    }

    /** The copy's name: the photo's, "_thermal" -> "_1x" (img_tp_thermal_123.png -> img_tp_1x_123.png), as PNG. */
    static String name(String photo) {
        int dot = photo.lastIndexOf('.');
        String base = dot > 0 ? photo.substring(0, dot) : photo;
        return (base.contains("_thermal") ? base.replace("_thermal", "_1x") : base + "_1x") + ".png";
    }

    /** EXIF 6 / 3 / 8 = rotate 90 / 180 / 270 degrees clockwise to view (the app writes no mirrored values). */
    static Bitmap upright(Bitmap bitmap, int exifOrientation) {
        int degrees = exifOrientation == 6 ? 90 : exifOrientation == 3 ? 180 : exifOrientation == 8 ? 270 : 0;
        if (degrees == 0) {
            return bitmap;
        }
        Matrix m = new Matrix();
        m.postRotate(degrees);
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), m, false);
    }
}
