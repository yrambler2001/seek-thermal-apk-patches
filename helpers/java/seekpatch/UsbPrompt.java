package seekpatch;

import android.app.PendingIntent;
import android.content.Intent;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.os.SystemClock;
import android.util.Log;

import java.util.HashMap;
import java.util.Map;

/**
 * seek-patch usb_prompt: the camera library asks Android for a camera once at a time.
 *
 * <p>The library searches for cameras when the camera screen is created and again each time it
 * resumes, and each search asks for permission for every camera it does not have open.  On a
 * fresh start the second search comes before the first answer, so Android queues a second
 * dialog: it shows after the first is answered and does nothing.  {@link #requestPermission}
 * (in place of {@code UsbManager.requestPermission}) skips a request while one for the same
 * camera is waiting for its answer; {@link #heard} (at the top of the library's
 * {@code onReceive}) takes it off the list when the answer comes, or the camera is unplugged.
 * A camera the app already has permission for is always passed on: Android answers that at once,
 * with no dialog.
 */
public final class UsbPrompt {
    private static final String TAG = "seek-patch";
    /** After this long a request counts as lost and is made again (Android answers every dialog, even dismissed). */
    private static final long WAIT_MS = 60000;

    private static final Map<String, Long> waiting = new HashMap<>();

    private UsbPrompt() {
    }

    public static void requestPermission(UsbManager manager, UsbDevice device, PendingIntent answer) {
        if (device != null && !manager.hasPermission(device)) {
            String name = device.getDeviceName();
            long now = SystemClock.elapsedRealtime();
            synchronized (waiting) {
                Long asked = waiting.get(name);
                if (asked != null && now - asked < WAIT_MS) {
                    Log.i(TAG, "usb_prompt: " + name + " already asked for, waiting for the answer");
                    return;
                }
                waiting.put(name, now);
            }
        }
        manager.requestPermission(device, answer);
    }

    /** The library's receiver: a permission answer, or the camera unplugged. */
    public static void heard(Intent intent) {
        String action = intent != null ? intent.getAction() : null;
        if (action == null
                || !(action.endsWith(".USB_PERMISSION") || UsbManager.ACTION_USB_DEVICE_DETACHED.equals(action))) {
            return;
        }
        UsbDevice device = intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
        synchronized (waiting) {
            if (device != null) {
                waiting.remove(device.getDeviceName());
            } else {
                waiting.clear();
            }
        }
    }
}
