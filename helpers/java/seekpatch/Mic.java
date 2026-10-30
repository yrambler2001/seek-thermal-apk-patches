package seekpatch;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.SystemClock;
import android.provider.Settings;
import android.widget.Toast;

import java.lang.ref.WeakReference;

/**
 * seek-thermal-apk-patches mic_prompt: ask for the microphone when a video starts, never block anything else.
 *
 * <p>On Android 11+ the app checks the microphone before every photo, video and gallery action;
 * without it, it requests the permission and drops the tap, and once Android stops showing the
 * dialog (after two denials) none of the three can start.  The patch routes that check through
 * {@link #gate} and the request through {@link #request}:
 *
 * <ul>
 *   <li>photos, the gallery and stopping a recording go ahead;
 *   <li>starting a video without the microphone shows Android's dialog; once it is answered
 *       ({@link #onResult}, from the activity's onRequestPermissionsResult) the video starts --
 *       with sound if allowed -- as soon as the camera runs again ({@link #frame}, called after every
 *       thermal frame: the dialog pauses the app, which stops the camera);
 *   <li>when Android will not show its dialog any more, a dialog of our own offers the app's
 *       settings page or recording without sound.
 * </ul>
 */
public final class Mic {
    private static final String PERMISSION = Manifest.permission.RECORD_AUDIO;
    private static final int ACTION_VIDEO = 1;
    /** Request code with which {@link #frame} has the activity start the video (the app's requests use 0). */
    static final int RESUME = 0x5ee;
    // the app-side file keeps the name it had before 1.0, so what it remembers survives an update
    private static final String PREFS = "seek-patch";
    private static final String DENIED_FOR_GOOD = "mic_denied_for_good";
    private static final long START_WITHIN_MS = 10000;

    private static boolean pending;
    private static boolean withoutSound;
    private static volatile boolean startPending;
    private static volatile long startBefore;
    private static WeakReference<Activity> activity = new WeakReference<>(null);

    private Mic() {
    }

    /**
     * In place of the app's checkSelfPermission(RECORD_AUDIO).  Returns PERMISSION_GRANTED to let
     * the action run; PERMISSION_DENIED makes the app call {@link #request} and return.
     */
    public static int gate(Activity a, int action, boolean recording) {
        activity = new WeakReference<>(a);
        if (a.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED) {
            withoutSound = false;
            SharedPreferences p = prefs(a);
            if (p.contains(DENIED_FOR_GOOD)) {
                p.edit().remove(DENIED_FOR_GOOD).apply();
            }
            return PackageManager.PERMISSION_GRANTED;
        }
        if (action != ACTION_VIDEO || recording) {
            return PackageManager.PERMISSION_GRANTED;  // photo, gallery, stop: no microphone needed
        }
        if (withoutSound) {
            withoutSound = false;
            return PackageManager.PERMISSION_GRANTED;
        }
        pending = true;
        return PackageManager.PERMISSION_DENIED;
    }

    /** In place of the app's requestPermissions(...) after {@link #gate} said no. */
    public static void request(Activity a, String[] permissions, int requestCode) {
        if (pending && prefs(a).getBoolean(DENIED_FOR_GOOD, false) && !a.shouldShowRequestPermissionRationale(PERMISSION)) {
            pending = false;
            offerSettings(a);  // Android would close its dialog unseen
            return;
        }
        a.requestPermissions(permissions, requestCode);
    }

    /** From onRequestPermissionsResult; true = start the video now. */
    public static boolean onResult(Activity a, int requestCode, String[] permissions, int[] results) {
        if (requestCode == RESUME) {
            return true;
        }
        if (!pending) {
            return false;
        }
        pending = false;
        int i = indexOf(permissions, PERMISSION);
        if (i < 0 || i >= results.length) {
            return false;  // the dialog was dismissed
        }
        if (results[i] == PackageManager.PERMISSION_GRANTED) {
            startOnNextFrame();
        } else if (a.shouldShowRequestPermissionRationale(PERMISSION)) {
            Toast.makeText(a, Lang.t("Recording without sound: the microphone is not allowed"), Toast.LENGTH_LONG).show();
            withoutSound = true;
            startOnNextFrame();
        } else {
            prefs(a).edit().putBoolean(DENIED_FOR_GOOD, true).apply();
            offerSettings(a);
        }
        return false;
    }

    /** Called by the GL thread after every thermal frame. */
    public static void frame() {
        if (!startPending) {
            return;
        }
        startPending = false;
        final Activity a = activity.get();
        if (a == null || SystemClock.uptimeMillis() > startBefore) {
            return;
        }
        a.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (a.isFinishing()) {
                    return;
                }
                if (!a.hasWindowFocus()) {
                    startPending = true;  // a dialog is still closing: try on a later frame
                    return;
                }
                a.onRequestPermissionsResult(RESUME, new String[] {PERMISSION}, new int[] {PackageManager.PERMISSION_GRANTED});
            }
        });
    }

    private static void startOnNextFrame() {
        startBefore = SystemClock.uptimeMillis() + START_WITHIN_MS;
        startPending = true;
    }

    private static void offerSettings(final Activity a) {
        new AlertDialog.Builder(a)
                .setTitle(Lang.t("Microphone is off"))
                .setMessage(Lang.t("Android will not ask again for this app. To record sound, allow the microphone in the app's settings."))
                .setPositiveButton(Lang.t("Open settings"), new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        a.startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.fromParts("package", a.getPackageName(), null)));
                    }
                })
                .setNegativeButton(Lang.t("Record without sound"), new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        withoutSound = true;
                        startOnNextFrame();
                    }
                })
                .show();
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static int indexOf(String[] values, String value) {
        for (int i = 0; values != null && i < values.length; i++) {
            if (value.equals(values[i])) {
                return i;
            }
        }
        return -1;
    }
}
