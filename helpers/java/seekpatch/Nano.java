package seekpatch;

import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbRequest;
import android.os.Build;
import android.util.Log;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.nio.IntBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeoutException;

/**
 * seek-patch nano: the Seek Nano 300 works in the app.
 *
 * <p>The Nano 300 is a Compact Pro inside (USB 289d:0011, "PIR324 Thermal Camera") and the app takes it
 * for one, but two things keep the live view black:
 * <ul>
 * <li>its firmware sends no frames until it is unlocked: USB vendor request 55 with {252, 4}, which
 * Seek's Nano app sends (seekcamera_nano_unlock) to the cameras whose core part number is a Nano's;
 * <li>it sends each frame in pieces of 6840 bytes (10 rows), where a Compact Pro sends 13680, and the
 * app reads a frame in chunks of the piece size it expects: each chunk would get half its bytes.
 * </ul>
 * {@link #unlock} reads the core part number just before the app switches a 289d:0011 camera to run
 * and, for a Nano 300, unlocks it; {@link #chunk} then gives the app the Nano's piece size, and
 * {@link #orient} shows its picture right side up (its sensor sits the other way round from a
 * Compact's).  A Compact Pro is left as it was.  See docs/nano.md.
 */
public final class Nano {
    private static final String TAG = "seek-patch";
    private static final int VENDOR = 0x289d;  // Seek Thermal
    private static final int PRO = 0x0011;     // the 320x240 cameras: Compact Pro, Nano 300
    private static final int OUT = 0x41;       // vendor request to the interface, host to device
    private static final int IN = 0xc1;        // vendor request to the interface, device to host
    private static final int COMMAND = 86;     // sets up a read: {words, address, 0}
    private static final int READ = 88;        // reads the words set up
    private static final int PERIPHERAL = 55;  // the camera's peripheral request
    private static final int TIMEOUT_MS = 1000;
    private static final int RUN = 1;          // the operation mode that starts the frames
    // the core part number: 8 words at 1538, as Seek's SDK reads it
    private static final byte[] PART_NUMBER = {8, 0, 0x02, 0x06, 0, 0};
    // the unlock: two little-endian shorts, {address 252, 4}
    private static final byte[] UNLOCK = {(byte) 0xfc, 0, 4, 0};
    // the Nano 300's core part numbers, the list Seek's Nano app checks
    private static final String[] NANO_300 = {"CQ-ABAX", "LQ-ABAX", "CQ-DBAX"};
    private static final int PRO_CHUNK = 13680;  // the app's chunk for 289d:0011, 20 rows
    private static final int NANO_CHUNK = 6840;  // the Nano 300's piece, 10 rows

    private static final String IP = "com.tyriansystems.Seekware.SeekwareNativeLib";  // its natives keep their JNI names
    private static final int PIPELINE = 900;          // 0 / 1 the app's "Image smoothing"; 2 SeekVision (newer library)
    private static final int COLOR_MODE = 6;          // the app's coloring mode; SeekVision's is 11
    private static final int TEMPORAL_LIMIT = 30401;  // Seek's Nano app sets 3 before SeekVision
    private static final int SEEKVISION = 2;
    private static final int SEEKVISION_COLOR = 11;
    private static final int UNKNOWN = 0x7fffffff;    // a feature the library refuses, so a write goes nowhere

    private static final long PIECE_TIMEOUT_MS = 1000;  // a piece takes a few ms; Seek's SDK gives a frame 1250
    private static final long CANCEL_TIMEOUT_MS = 200;

    private static volatile boolean nano;
    // the frame thread
    private static boolean failed;      // a piece of this frame was lost
    private static UsbRequest pending;  // the piece queued last
    private static long seekVision;  // the image library handle in SeekVision, 0 none
    private static long refused;     // the handle whose library has no SeekVision (2.3.4's own)
    private static java.lang.reflect.Method setFeature;

    private Nano() {
    }

    /** Before the app sets the camera's operation mode (two bytes, little-endian): unlocks a Nano 300 before run. */
    public static void unlock(UsbDeviceConnection c, byte[] mode) {
        try {
            if (c == null || mode == null || mode.length != 2 || mode[0] != RUN || mode[1] != 0) {
                return;
            }
            byte[] d = c.getRawDescriptors();  // the device descriptor first: idVendor at 8, idProduct at 10
            if (d == null || d.length < 12 || (d[8] & 0xff | (d[9] & 0xff) << 8) != VENDOR
                    || (d[10] & 0xff | (d[11] & 0xff) << 8) != PRO) {
                return;
            }
            String part = partNumber(c);
            nano = false;
            for (String p : NANO_300) {
                nano |= p.equals(part);
            }
            if (!nano) {
                return;
            }
            byte[] data = UNLOCK.clone();
            int n = c.controlTransfer(OUT, PERIPHERAL, 0, 0, data, data.length, TIMEOUT_MS);
            Log.i(TAG, "nano: Nano 300 (" + part + "), unlock " + (n == data.length ? "sent" : "returned " + n)
                    + ", frames read in " + NANO_CHUNK + "-byte chunks");
        } catch (Throwable t) {
            Log.w(TAG, "nano: unlock failed", t);
        }
    }

    /**
     * Before each feature the app sets on the image library (handle, id, value, its length): which id to
     * send.  Seek's Nano app runs a Nano 300 in SeekVision (pipeline 2): the first time the app sets the
     * pipeline, a library that has SeekVision (Seek's newer one) is put in it the way the Nano app does,
     * the app's own pipeline writes go nowhere from then on, and its default coloring mode becomes
     * SeekVision's.  A library without it (2.3.4's) gets the app's writes unchanged.
     */
    public static int feature(long handle, int id, ByteBuffer value, int length) {
        if (!nano) {
            return id;
        }
        try {
            if (id == PIPELINE && handle != seekVision && handle != refused) {
                set(handle, TEMPORAL_LIMIT, 2, 3);
                int r = set(handle, PIPELINE, 4, SEEKVISION);
                if (r == 0) {
                    seekVision = handle;
                    Log.i(TAG, "nano: image library in SeekVision, as in Seek's Nano app");
                } else {
                    refused = handle;
                    Log.i(TAG, "nano: the image library has no SeekVision (" + r + "): the app's processing stays");
                }
            }
            if (handle == seekVision) {
                if (id == PIPELINE) {
                    return UNKNOWN;
                }
                if (id == COLOR_MODE && length == 4 && value.order(ByteOrder.LITTLE_ENDIAN).getInt(0) == 0) {
                    value.putInt(0, SEEKVISION_COLOR);
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "nano: feature " + id + " failed", t);
        }
        return id;
    }

    private static int set(long handle, int id, int length, int v) throws Exception {
        if (setFeature == null) {
            setFeature = Class.forName(IP).getDeclaredMethod("seekIPsetFeature", long.class, int.class, ByteBuffer.class,
                    int.class);
            setFeature.setAccessible(true);
        }
        ByteBuffer b = ByteBuffer.allocateDirect(4).order(ByteOrder.LITTLE_ENDIAN);
        b.putInt(0, v);
        return (Integer) setFeature.invoke(null, handle, id, b, length);
    }

    /** The app's request for the next frame (before it reads the frame's pieces): a new frame, nothing failed yet. */
    public static void frame(UsbDeviceConnection c) {
        failed = false;
    }

    /**
     * Instead of queueing one piece of a frame: once a piece of this frame was lost, the rest is not
     * asked for (the app fails the frame and asks for the next).
     */
    public static boolean queue(UsbRequest r, ByteBuffer buffer, int length) {
        if (nano) {
            if (failed) {
                return false;
            }
            pending = r;
        }
        return r.queue(buffer, length);
    }

    /**
     * Instead of waiting for the piece just queued: the app waits for ever, and a Nano 300 sometimes
     * stops in the middle of a frame (half of it sent) -- the live view would freeze.  For a Nano the wait
     * ends after a second: the piece is cancelled (and its cancelled request collected, so it is not
     * handed back later as data), the frame fails and the app asks for the next one.
     */
    public static UsbRequest requestWait(UsbDeviceConnection c) {
        if (!nano || Build.VERSION.SDK_INT < 26) {
            return c.requestWait();
        }
        try {
            return c.requestWait(PIECE_TIMEOUT_MS);
        } catch (TimeoutException e) {
            failed = true;
            UsbRequest r = pending;
            pending = null;
            if (r != null) {
                r.cancel();
                try {
                    c.requestWait(CANCEL_TIMEOUT_MS);
                } catch (TimeoutException ignored) {
                    // nothing to collect
                }
            }
            Log.w(TAG, "nano: a frame stopped half way (no piece for " + PIECE_TIMEOUT_MS + " ms), asking for the next");
            return null;
        }
    }

    /** The size the app reads a frame in: a Nano 300 sends 6840-byte pieces. */
    public static int chunk(int size) {
        return nano && size == PRO_CHUNK ? NANO_CHUNK : size;
    }

    /**
     * After the image library's process call (its arguments from the element counts on): the call turns
     * the color image by 180 degrees for the app, which shows a Compact's sensor right side up that
     * way, and the app turns the minimum's and maximum's positions to match.  A Nano 300's sensor sits
     * the other way round: the color image is turned back, and the positions so the app's turn undoes.
     */
    public static void orient(IntBuffer counts, ByteBuffer raw, ByteBuffer filtered, FloatBuffer thermography,
                              ByteBuffer color, ByteBuffer results) {
        if (!nano || counts == null || color == null) {
            return;
        }
        try {
            int n = counts.get(3);  // the color image's pixels, one int each
            IntBuffer px = color.duplicate().asIntBuffer();
            for (int i = 0, j = n - 1; i < j; i++, j--) {
                int p = px.get(i);
                px.put(i, px.get(j));
                px.put(j, p);
            }
            int w = Math.round((float) Math.sqrt(n * 4 / 3.0));  // 4:3, 320x240
            int h = w == 0 ? 0 : n / w;
            if (results != null && w * h == n) {  // min x, min y, max x, max y: the app shows width - x, height - y
                ByteBuffer r = results.duplicate().order(ByteOrder.LITTLE_ENDIAN);
                for (int k = 0; k < 4; k++) {
                    r.putInt(4 * k, (k % 2 == 0 ? w : h) - r.getInt(4 * k));
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "nano: orientation failed", t);
        }
    }

    private static String partNumber(UsbDeviceConnection c) {
        byte[] setup = PART_NUMBER.clone();
        if (c.controlTransfer(OUT, COMMAND, 0, 0, setup, setup.length, TIMEOUT_MS) != setup.length) {
            return "";
        }
        byte[] b = new byte[2 * PART_NUMBER[0]];
        int n = c.controlTransfer(IN, READ, 0, 0, b, b.length, TIMEOUT_MS);
        int end = 0;
        while (end < Math.max(n, 0) && b[end] != 0) {
            end++;
        }
        return new String(b, 0, end, StandardCharsets.US_ASCII).trim();
    }
}
