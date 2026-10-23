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
 * seek-patch photo_1x: with every photo, the thermal frame at the sensor's resolution as a PNG.
 *
 * <p>The photo method hands its frame bitmap (sensor-sized, colorized, no overlays) to
 * {@link #capture} before scaling it up; once the photo file is written, {@link #saved} stores the
 * frame next to it, in a sibling folder named after the photo's with " 1x" appended (so Seek's
 * own gallery, which lists every file under the photo folder, does not show it twice), under the
 * photo's name.  The pixels are turned upright by the photo's EXIF orientation, which PNG viewers
 * do not read.
 */
public final class Photo1x {
    private static final String TAG = "seek-patch";

    private static Bitmap frame;
    private static Context context;

    private Photo1x() {
    }

    public static synchronized void capture(Context c, Bitmap bitmap) {
        context = c != null ? c.getApplicationContext() : null;
        frame = bitmap;
    }

    public static void saved(File photo, int exifOrientation) {
        Bitmap bitmap;
        Context c;
        synchronized (Photo1x.class) {
            bitmap = frame;
            c = context;
            frame = null;
        }
        File folder = photo != null ? photo.getParentFile() : null;
        if (bitmap == null || bitmap.isRecycled() || folder == null) {
            return;
        }
        File dir = new File(folder.getParentFile(), folder.getName() + " 1x");
        String name = photo.getName();
        int dot = name.lastIndexOf('.');
        File out = new File(dir, (dot > 0 ? name.substring(0, dot) : name) + ".png");
        try {
            if (!dir.isDirectory() && !dir.mkdirs()) {
                throw new IOException("cannot create " + dir);
            }
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
