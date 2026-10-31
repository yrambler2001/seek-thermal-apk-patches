package seekpatch;

import android.content.SharedPreferences;
import android.preference.PreferenceFragment;
import android.util.Log;

/**
 * seek-thermal-apk-patches rotation: its settings, <i>Image rotation</i> (off, 90° / 180° / 270° clockwise)
 * and <i>Mirroring</i> (off, horizontally, vertically, both), both off by default.  They turn the thermal
 * picture only ({@link Rotation}), mirrored after the turn; the markers, their temperatures and the
 * temperature bar stay upright.
 */
public final class RotationSettings {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String DEGREES = "rotation";
    private static final String MIRRORING = "mirroring";
    private static final String[] TURNS = {"0", "90", "180", "270"};
    private static final String[] MIRRORS = {"off", "horizontal", "vertical", "both"};

    private static String loaded;

    private RotationSettings() {
    }

    /** Settings: the values (main thread); the next frame and photo use them. */
    public static void load(SharedPreferences p) {
        int d = Integer.parseInt(TURNS[choice(p, DEGREES, TURNS)]);
        String m = MIRRORS[choice(p, MIRRORING, MIRRORS)];
        boolean x = "horizontal".equals(m) || "both".equals(m);
        boolean y = "vertical".equals(m) || "both".equals(m);
        Rotation.set(d, x, y);
        String now = d == 0 && !x && !y ? "off" : "turned " + d + "° clockwise, mirrored " + m;
        if (!now.equals(loaded)) {
            loaded = now;
            Log.i(TAG, "rotation: " + now);
        }
    }

    /** Settings: the two lists, appended. */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        String off = Lang.f("%s (default)", Lang.t("Off"));
        String[] turns = {off, Lang.f("%d° clockwise", 90), "180°", Lang.f("%d° clockwise", 270)};
        Settings.addList(f.getPreferenceScreen(), p, DEGREES, Lang.t("Image rotation"), turns, TURNS,
                TURNS[choice(p, DEGREES, TURNS)], null)
                .setDialogTitle(Lang.t("Image rotation: the thermal picture only"));
        String[] mirrors = {off, Lang.t("Mirror horizontally (left ↔ right)"), Lang.t("Mirror vertically (top ↔ bottom)"),
            Lang.t("Mirror horizontally and vertically")};
        Settings.addList(f.getPreferenceScreen(), p, MIRRORING, Lang.t("Mirroring"), mirrors, MIRRORS,
                MIRRORS[choice(p, MIRRORING, MIRRORS)], null)
                .setDialogTitle(Lang.t("Mirroring: the thermal picture only, after the rotation"));
    }

    /** The stored value's index among values; else 0 (off). */
    private static int choice(SharedPreferences p, String key, String[] values) {
        String v = p.getString(key, null);
        for (int i = 0; i < values.length; i++) {
            if (values[i].equals(v)) {
                return i;
            }
        }
        return 0;
    }
}
