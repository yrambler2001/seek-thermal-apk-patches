package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.hardware.usb.UsbDeviceConnection;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;

/**
 * seek-patch shutter: a button that stops the camera's automatic shutter, and starts it again.
 *
 * <p>The camera closes its shutter by itself to recalibrate, every few seconds (the Compact: about every
 * 5 s, more often just after connecting): a click, a frozen frame (0.44 s) and a small jump in the
 * picture and the readings.
 * Off, none of that happens, but nothing corrects the sensor's drift either: the picture slowly gets
 * noisier and the readings wander as the camera warms.  On again, the camera shutters right away, its
 * next one being overdue.
 *
 * <p>The commands are the firmware's shutter request (USB vendor request 55, {255, 253} suspend and
 * {255, 252} resume: they set and clear a flag in the camera's RAM that its automatic shutter checks),
 * sent on the thread that asks for each frame, just before it does ({@link #transfer}): never in the
 * middle of the app's own requests.  A camera that is unplugged forgets the flag; when the button is
 * off, a reconnected camera is suspended again.  "Off" lasts until the app is closed; a camera the app
 * left suspended (the app was closed, the camera not unplugged) is resumed when it connects again.
 * See docs/shutter.md.
 */
public final class Shutter {
    private static final String TAG = "seek-patch";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final int OUT = 0x41;      // vendor request to the interface, host to device
    private static final int REQUEST = 55;    // the camera's shutter request
    private static final int TIMEOUT_MS = 1000;
    private static final String PREFS = "seekpatch";
    private static final String KEY = "shutter_suspended";  // a camera may still be suspended
    private static final int NONE = 0;
    private static final int STOP = 1;
    private static final int START = 2;
    // the shutter request's payload: two little-endian shorts, {address 255 (the shutter), action}
    private static final byte[] SUSPEND = {(byte) 0xff, 0, (byte) 0xfd, 0};
    private static final byte[] RESUME = {(byte) 0xff, 0, (byte) 0xfc, 0};

    private static volatile boolean off;
    private static volatile int request;  // main thread -> USB thread
    private static volatile boolean connected;
    private static WeakReference<TextView> button = new WeakReference<>(null);
    private static volatile SharedPreferences prefs;

    // USB thread
    private static UsbDeviceConnection last;

    private Shutter() {
    }

    /** After the activity's setContentView: the button floats below the top bar, left side, after calibration's. */
    public static void attach(Activity a) {
        try {
            prefs = a.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            TextView b = Floating.button(a, "Stops the camera's automatic shutter: no clicks or frozen frames, but the picture "
                            + "slowly drifts; tap again to start it (it shutters right away)",
                    new View.OnClickListener() {
                        @Override
                        public void onClick(View v) {
                            tap((TextView) v);
                        }
                    });
            if (Floating.place(a, b, false, 20)) {
                button = new WeakReference<>(b);
                show(b);
            }
        } catch (Throwable t) {
            Log.w(TAG, "shutter: no button", t);
        }
    }

    private static void tap(TextView b) {
        if (!connected) {
            Toast.makeText(b.getContext(), "No camera", Toast.LENGTH_SHORT).show();
        } else {
            request = off ? START : STOP;
        }
    }

    private static void show(TextView b) {
        b.setText(off ? "Shutter off" : "Shutter auto");
        Floating.style(b, off);
    }

    /** USB thread, before each frame request: sends a tap's command; turns a reconnected camera's shutter off again. */
    public static void transfer(UsbDeviceConnection c) {
        if (c == null) {
            return;
        }
        connected = true;
        if (c != last) {  // a new connection
            last = c;
            if (off) {  // unplugged, the camera forgot
                request = STOP;
            } else if (request == NONE && suspended()) {  // left suspended by an earlier run of the app
                request = START;
            }
        }
        int r = request;
        if (r == NONE) {
            return;
        }
        request = NONE;
        try {
            if (r == STOP) {
                remember(true);  // before: the command may arrive although the transfer reports a failure
                if (send(c, SUSPEND)) {
                    off = true;
                    Log.i(TAG, "shutter: automatic shutter off");
                    refresh(null);
                } else {
                    off = false;
                    refresh("The camera did not take the command: its shutter stays on");
                }
            } else {
                if (send(c, RESUME)) {
                    off = false;
                    remember(false);
                    Log.i(TAG, "shutter: automatic shutter on");
                    refresh(null);
                } else {
                    refresh("The camera did not take the command");
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "shutter: command failed", t);
            refresh("The camera did not take the command");
        }
    }

    private static boolean suspended() {
        SharedPreferences p = prefs;
        return p != null && p.getBoolean(KEY, false);
    }

    private static void remember(boolean suspended) {
        SharedPreferences p = prefs;
        if (p != null) {
            p.edit().putBoolean(KEY, suspended).apply();
        }
    }

    private static boolean send(UsbDeviceConnection c, byte[] payload) {
        byte[] data = payload.clone();
        int n = c.controlTransfer(OUT, REQUEST, 0, 0, data, data.length, TIMEOUT_MS);
        if (n != data.length) {
            Log.w(TAG, "shutter: request " + REQUEST + " {" + (data[0] & 0xff) + ", " + (data[2] & 0xff) + "} returned " + n);
        }
        return n == data.length;
    }

    private static void refresh(final String message) {
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                TextView b = button.get();
                if (b != null) {
                    show(b);
                    if (message != null) {
                        Toast.makeText(b.getContext(), message, Toast.LENGTH_LONG).show();
                    }
                }
            }
        });
    }
}
