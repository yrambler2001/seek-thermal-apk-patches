package seekpatch;

import android.os.Build;
import android.preference.Preference;
import android.preference.PreferenceFragment;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.util.Log;

import java.util.Arrays;
import java.util.List;

/**
 * seek-thermal-apk-patches hidden_settings: what each of the app's developer switches in Settings does, in a
 * line under its title, and the titles the app has in English only (Save Uncompressed, Set Simulation Mode,
 * Disable Registration, Use Staging Server) in the app's language.
 *
 * <p>What two of them do depends on the app's version; the patch writes what it found in the app into
 * {@link #facts}, comma separated: "registration" while the app still registers cameras (up to 2.2.3), "tiff"
 * when Store All Thermal Data saves a TIFF with each photo (from 2.1.1).  Store All Thermal Data has no line
 * without it.
 */
public final class Hidden {
    private static final String TAG = "seek-thermal-apk-patches";
    /** CustomFontListPreference's summary color (as Settings'): the app's switch colors its title only. */
    private static final int SUMMARY_COLOR = 0xffcccccc;
    private static final int ANDROID_11 = 30;
    private static final String SAVE_UNCOMPRESSED = "Save Uncompressed";
    private static final String SIMULATION = "Set Simulation Mode";
    private static final String NO_REGISTRATION = "Disable Registration";
    private static final String STAGING = "Use Staging Server";
    private static final String NOTHING = "Does nothing in this version of the app: it no longer registers cameras";

    /** Written by the patch into this class' smali: what this version of the app does. */
    static String facts;

    private Hidden() {
    }

    /** The Settings screen, after addPreferencesFromResource. */
    public static void screen(PreferenceFragment f) {
        try {
            List<String> app = Arrays.asList(String.valueOf(facts).split(","));
            boolean registration = app.contains("registration");
            describe(f, "lossless_comp_key", SAVE_UNCOMPRESSED, Lang.t(SAVE_UNCOMPRESSED),
                    Build.VERSION.SDK_INT >= ANDROID_11 ? Lang.t("Photos as PNG, lossless, instead of JPEG")
                            : Lang.t("Photos as PNG, lossless, instead of JPEG. Needs Android 11: on older Android "
                                    + "the app cannot save them"));
            describe(f, "sim_mode_key", SIMULATION, Lang.t(SIMULATION),
                    Lang.t("A simulated camera: the camera screen works with no camera attached"));
            describe(f, "video_export_frame_rate", null, null,
                    Lang.t("The camera's frame rate in a corner of the image, e.g. 27.9 Hz"));
            describe(f, "disable_registration_key", NO_REGISTRATION, Lang.t(NO_REGISTRATION), registration
                    ? Lang.t("Seek's test switch for the camera registration (register.thermal.com)") : Lang.t(NOTHING));
            describe(f, "use_staging_server_key", STAGING, Lang.t(STAGING), registration
                    ? Lang.t("Registers the camera on Seek's test server, register-staging.thermal.com")
                    : Lang.t(NOTHING));
            if (app.contains("tiff")) {
                describe(f, "store_all_thermal_data", null, null, Lang.t(
                        "With each photo, a TIFF file with every pixel's temperature (Span & Level and Full Frame modes)"));
            }
        } catch (Throwable t) {
            Log.w(TAG, "hidden_settings: no descriptions", t);
        }
    }

    /** The switch under key, where the screen has it: its summary, and its title in the app's language where the
     * app has only the English one (english, null: the app's title stays). */
    private static void describe(PreferenceFragment f, String key, String english, String title, String summary) {
        Preference p = f.findPreference(key);
        if (p == null) {
            return;
        }
        if (english != null && p.getTitle() != null && english.contentEquals(p.getTitle())) {
            p.setTitle(title);
        }
        SpannableString s = new SpannableString(summary);
        s.setSpan(new ForegroundColorSpan(SUMMARY_COLOR), 0, s.length(), Spanned.SPAN_INCLUSIVE_INCLUSIVE);
        p.setSummary(s);
    }
}
