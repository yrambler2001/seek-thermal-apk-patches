package seekpatch;

import android.content.SharedPreferences;
import android.preference.PreferenceFragment;
import android.util.Log;

/**
 * seek-thermal-apk-patches photo_1x: its setting, <i>Also save a 1x PNG</i>, off by default.  It sets
 * {@link Photo1x#enabled}, which is on where the app has no settings screen for it (then the patch
 * saves with every photo, as before there was a setting).
 */
public final class PhotoSettings {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String KEY = "photo_1x";

    private static int loaded = -1;

    private PhotoSettings() {
    }

    /** Settings: the value (main thread); used from the next photo. */
    public static void load(SharedPreferences p) {
        Photo1x.enabled = p.getBoolean(KEY, false);
        int now = Photo1x.enabled ? 1 : 0;
        if (now != loaded) {
            loaded = now;
            Log.i(TAG, "photo_1x: " + (Photo1x.enabled ? "a 1x PNG with every photo" : "off"));
        }
    }

    /** Settings: the switch, appended. */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        Settings.addSwitch(f.getPreferenceScreen(), p, KEY, Lang.t("Also save a 1x PNG"),
                Lang.t("With each photo, the frame at the sensor's resolution, next to it (img_1x_…)"),
                false, null);
    }
}
