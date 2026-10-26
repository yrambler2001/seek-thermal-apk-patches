package seekpatch;

import android.content.SharedPreferences;
import android.preference.PreferenceFragment;
import android.util.Log;

/**
 * seek-thermal-apk-patches flat_field: its setting, <i>Flat field frames</i>, how many frames one tap of the Flat
 * field button learns from ({@link Flat#updates}).  The map moves 1/8 of the way per frame, so N
 * frames learn 1 - (7/8)^N of the gradient: a short run is quicker and forgives a moving hand, a
 * long one is complete.  A second tap goes on from where the first stopped.
 */
public final class FlatSettings {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String KEY = "flat_field_frames";
    private static final int[] CHOICES = {5, 10, 15, 20, 30, 40, 60};
    private static final int DEFAULT = 40;

    private static int loaded = -1;

    private FlatSettings() {
    }

    /** Settings: the value (main thread); used from the next tap. */
    public static void load(SharedPreferences p) {
        Flat.updates = frames(p);
        if (Flat.updates != loaded) {
            loaded = Flat.updates;
            Log.i(TAG, "flat_field: " + loaded + " frames a tap");
        }
    }

    /** Settings: the list, appended. */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        String[] entries = new String[CHOICES.length];
        String[] values = new String[CHOICES.length];
        for (int i = 0; i < CHOICES.length; i++) {
            int n = CHOICES[i];
            double learned = 100 * (1 - Math.pow(7 / 8.0, n));
            String percent = learned < 99 ? String.valueOf(Math.round(learned))
                    : learned < 99.95 ? String.valueOf(Math.round(learned * 10) / 10.0) : "all";
            entries[i] = n + " frames: learns " + percent + (percent.equals("all") ? "" : " %") + " of the gradient"
                    + (n == DEFAULT ? " (default)" : "");
            values[i] = String.valueOf(n);
        }
        Settings.addList(f.getPreferenceScreen(), p, KEY, "Flat field frames", entries, values,
                String.valueOf(frames(p)), null)
                .setDialogTitle("Flat field: frames to learn from per tap");
    }

    private static int frames(SharedPreferences p) {
        try {
            int n = Integer.parseInt(p.getString(KEY, String.valueOf(DEFAULT)));
            return n >= 1 && n <= 1000 ? n : DEFAULT;
        } catch (RuntimeException e) {
            return DEFAULT;
        }
    }
}
