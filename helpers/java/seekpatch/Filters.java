package seekpatch;

import android.content.SharedPreferences;
import android.preference.Preference;
import android.preference.PreferenceFragment;
import android.preference.PreferenceScreen;
import android.util.Log;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * seek-thermal-apk-patches smoothing_settings: a switch for each of Seek's own image filters, and for Smart
 * smoothing, in place of the app's "Image smoothing" switch.
 *
 * <p>Before every frame the app sends library feature 900 with the "Image smoothing" switch, and the
 * library turns it into a preset of first-filter stages: on = sbnuc (pattern correction) + alpf
 * (temporal smoothing) + gradient, off = alpf + peak limiting + gradient + aslpf (3x3 spatial
 * smoothing).  {@link #frame} runs right after that call.  It makes the "on" preset the base,
 * whatever the hidden old switch says (900 = 1 again when the app sent 0), then changes the stage
 * bits whose switch is away from its default: 102 = 0 (no alpf), 100 = 1 (aslpf), 106 = 0 (no
 * sbnuc).  With every switch at its default nothing is sent and the picture is stock "on".
 *
 * <p>Smart smoothing's switches (shown when the smart_smoothing patch is in the app) are the keys
 * seekpatch.Smooth keeps in the same preferences file, so its top-left button follows them.
 */
public final class Filters {
    private static final String TAG = "seek-thermal-apk-patches";
    // keys in the seekpatch preferences
    private static final String TEMPORAL = "temporal_smoothing";
    private static final String SPATIAL = "spatial_smoothing";
    private static final String PATTERN = "pattern_correction";
    private static final String SMART = "smart_smoothing";      // seekpatch.Smooth's
    private static final String STRIPES = "smart_stripes";      // seekpatch.Smooth's
    private static final String EDGE = "smart_left_edge";       // seekpatch.Smooth's
    // libseekip features
    private static final int PRESET = 900;  // featureEnhancedProcessing: 1 = the "Image smoothing on" preset
    private static final int ASLPF = 100;   // first-filter bit 0x100: 3x3 spatial smoothing
    private static final int ALPF = 102;    // bit 0x004: temporal smoothing
    private static final int SBNUC = 106;   // bit 0x002: scene-based pattern (non-uniformity) correction
    private static final int MASK = 132;    // the whole first-filter mask (read back for the log)
    // the switches that differ from the stock preset
    private static final int NO_TEMPORAL = 1;
    private static final int WITH_SPATIAL = 2;
    private static final int NO_PATTERN = 4;
    private static final int SMART_ON = 8;  // only logged: Smart smoothing's hook clears alpf itself

    private static volatile int changes;
    private static volatile boolean smartOn;

    // camera thread
    private static final ByteBuffer OFF = value(0);
    private static final ByteBuffer ON = value(1);
    private static final ByteBuffer OUT = ByteBuffer.allocateDirect(4).order(ByteOrder.LITTLE_ENDIAN);
    private static int loggedChanges = -1;
    private static long loggedHandle;
    private static boolean loggedSent;
    private static boolean warned;

    private Filters() {
    }

    /** Settings: the values (main thread). */
    public static void load(SharedPreferences p) {
        changes = (p.getBoolean(TEMPORAL, true) ? 0 : NO_TEMPORAL)
                | (p.getBoolean(SPATIAL, false) ? WITH_SPATIAL : 0)
                | (p.getBoolean(PATTERN, true) ? 0 : NO_PATTERN);
        smartOn = p.getBoolean(SMART, false) && Settings.present("seekpatch.Smooth");
    }

    /** Settings: the switches, in place of the app's "Image smoothing" (the last item of the screen).  None is
     * ever greyed out: the app's switch class draws a disabled "on" much like "off". */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        PreferenceScreen s = f.getPreferenceScreen();
        Preference old = f.findPreference(Settings.OLD_SWITCH);
        if (old != null) {
            s.removePreference(old);  // replaced by the switches below
        }
        boolean smart = Settings.present("seekpatch.Smooth");
        Settings.addSwitch(s, p, TEMPORAL, Lang.t("Default temporal smoothing"), smart
                ? Lang.t("Seek's filter: averages each pixel over recent frames; Smart smoothing replaces it while on")
                : Lang.t("Seek's filter: averages each pixel over recent frames"), true, null);
        Settings.addSwitch(s, p, SPATIAL, Lang.t("Default spatial smoothing (3×3)"),
                Lang.t("Seek's filter: blurs each pixel with its neighbours"), false, null);
        Settings.addSwitch(s, p, PATTERN, Lang.t("Default pattern correction"),
                Lang.t("Seek's filter: learns and removes the sensor's fixed pattern"), true, null);
        if (!smart) {
            return;
        }
        Settings.addSwitch(s, p, SMART, Lang.t("Smart smoothing"), Lang.t("Follows the camera's motion; replaces temporal smoothing"),
                false, null);
        Settings.addSwitch(s, p, STRIPES, Lang.t("Stripe correction"), Lang.t("Part of Smart smoothing: removes column stripes"),
                true, null);
        Settings.addSwitch(s, p, EDGE, Lang.t("Left-edge levelling"),
                Lang.t("Part of Smart smoothing: levels the bright strip at the left edge"),
                true, null);
    }

    /** Camera thread, right after the app's feature 900; sentOn: the value it sent (its hidden switch). */
    public static void frame(long handle, boolean sentOn) {
        int c = changes;
        int logged = c | (smartOn ? SMART_ON : 0);
        if (sentOn && c == 0 && logged == loggedChanges && loggedSent && handle == loggedHandle) {
            return;  // the stock preset, already logged for this connection
        }
        try {
            if (!sentOn) {
                set(handle, PRESET, ON);  // the base is always the "on" preset
            }
            if ((c & NO_TEMPORAL) != 0) {
                set(handle, ALPF, OFF);
            }
            if ((c & WITH_SPATIAL) != 0) {
                set(handle, ASLPF, ON);
            }
            if ((c & NO_PATTERN) != 0) {
                set(handle, SBNUC, OFF);
            }
            if (logged != loggedChanges || handle != loggedHandle || sentOn != loggedSent) {
                loggedChanges = logged;
                loggedHandle = handle;
                loggedSent = sentOn;
                Log.i(TAG, "smoothing_settings: first-filter mask " + mask(handle) + ": temporal "
                        + ((c & NO_TEMPORAL) != 0 ? "off" : "on") + ", spatial " + ((c & WITH_SPATIAL) != 0 ? "on" : "off")
                        + ", pattern correction " + ((c & NO_PATTERN) != 0 ? "off" : "on")
                        + (smartOn ? "; Smart smoothing on: its hook runs the first filter without alpf (0x4)" : "")
                        + (sentOn ? "" : "; the app sent \"Image smoothing\" off, the on preset was sent again"));
            }
            warned = false;
        } catch (Throwable t) {
            if (!warned) {
                warned = true;
                Log.w(TAG, "smoothing_settings: features not set", t);
            }
        }
    }

    private static String mask(long handle) {
        OUT.putInt(0, 0);
        int rc = SeekIP.getFeature(handle, MASK, OUT, 4);
        return rc == 0 ? "0x" + Integer.toHexString(OUT.getInt(0)) : "? (getFeature " + rc + ")";
    }

    private static void set(long handle, int feature, ByteBuffer value) {
        int rc = SeekIP.setFeature(handle, feature, value, 4);
        if (rc != 0) {
            throw new IllegalStateException("setFeature " + feature + ": " + rc);
        }
    }

    private static ByteBuffer value(int v) {
        ByteBuffer b = ByteBuffer.allocateDirect(4).order(ByteOrder.LITTLE_ENDIAN);
        b.putInt(0, v);
        return b;
    }
}
