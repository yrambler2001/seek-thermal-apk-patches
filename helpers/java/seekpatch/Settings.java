package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.preference.ListPreference;
import android.preference.Preference;
import android.preference.PreferenceFragment;
import android.preference.PreferenceGroup;
import android.preference.SwitchPreference;
import android.util.AttributeSet;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.widget.ListView;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/**
 * seek-patch: the patches' settings, in the app's own <i>Settings → Image &amp; Video</i> screen.
 *
 * <p>Two hooks call in: {@link #attach} from the camera screen's onCreate, which loads the values
 * before the first frame and follows every later change, and {@link #screen} right after the
 * Image &amp; Video fragment has inflated its preferences.  The values live in the "seekpatch"
 * preferences file, not the app's own.
 *
 * <p>Each patch with settings adds a section class, looked up here by name, so a patch that was
 * not applied is simply absent:
 * <pre>
 *     seekpatch.Filters        smoothing_settings: Seek's filters, Smart smoothing
 *     seekpatch.FlatSettings   flat_field: frames per tap of the Flat field button
 *     seekpatch.Upscale        sharp_scaling: smooth, sharp or blocky upscaling
 *     seekpatch.PhotoSettings  photo_1x: whether to save the 1x PNG
 *     seekpatch.VideoSettings  video_quality: the video's quantizer
 * </pre>
 * with {@code public static void load(SharedPreferences)} (values to the patch's runtime state, on
 * the main thread) and {@code public static void screen(PreferenceFragment, SharedPreferences)}
 * (its preferences, appended to the screen in that order).  The preferences are the app's own
 * classes, so they look like the rest of the screen, and are not persisted by the framework: they
 * store into the seekpatch file themselves.
 */
public final class Settings {
    static final String TAG = "seek-patch";
    public static final String PREFS = "seekpatch";
    /** The app's "Image smoothing" switch: the class our switches copy (and smoothing_settings hides it). */
    public static final String OLD_SWITCH = "use_smoothing";
    private static final String[] SECTIONS = {"seekpatch.Filters", "seekpatch.FlatSettings", "seekpatch.Upscale",
        "seekpatch.PhotoSettings", "seekpatch.VideoSettings"};

    private static SharedPreferences prefs;
    private static Method[] loads;
    private static Method[] screens;
    private static Constructor<?> switchType;  // main thread, set for each screen
    private static Constructor<?> listType;
    private static final SharedPreferences.OnSharedPreferenceChangeListener LISTENER =
            new SharedPreferences.OnSharedPreferenceChangeListener() {
                @Override
                public void onSharedPreferenceChanged(SharedPreferences p, String key) {
                    load(p);
                }
            };

    private Settings() {
    }

    /** Camera screen, after setContentView: load the values (and follow them from now on). */
    public static void attach(Activity a) {
        try {
            prefs(a);
        } catch (Throwable t) {
            Log.w(TAG, "settings: not loaded", t);
        }
    }

    /** The Image &amp; Video fragment, after addPreferencesFromResource: add every section's preferences. */
    public static void screen(PreferenceFragment f) {
        try {
            SharedPreferences p = prefs(f.getActivity());
            Preference old = f.findPreference(OLD_SWITCH);
            Class<?> type = old instanceof SwitchPreference ? old.getClass() : SwitchPreference.class;
            switchType = constructor(type, SwitchPreference.class);
            listType = constructor(listClass(type), ListPreference.class);
            for (int i = 0; i < SECTIONS.length; i++) {
                if (screens[i] != null) {
                    try {
                        screens[i].invoke(null, f, p);
                    } catch (Throwable t) {
                        Log.w(TAG, "settings: " + SECTIONS[i] + " failed", t);
                    }
                }
            }
            final PreferenceFragment fragment = f;
            new Handler(Looper.getMainLooper()).post(new Runnable() {
                @Override
                public void run() {
                    padEnd(fragment);  // its view exists by now
                }
            });
        } catch (Throwable t) {
            Log.w(TAG, "settings: none on this screen", t);
        }
    }

    /** The screen's list runs on under the navigation bar, and with our items the last one ends there: pad
     * the list's end by the bar, so that it scrolls clear. */
    private static void padEnd(PreferenceFragment f) {
        try {
            View root = f.getView();
            View list = root != null ? root.findViewById(android.R.id.list) : null;
            WindowInsets insets = list != null ? list.getRootWindowInsets() : null;
            int bar = insets != null ? insets.getSystemWindowInsetBottom() : 0;
            if (list instanceof ListView && bar > 0) {
                ListView l = (ListView) list;
                l.setClipToPadding(false);
                l.setPadding(l.getPaddingLeft(), l.getPaddingTop(), l.getPaddingRight(), l.getPaddingBottom() + bar);
            }
        } catch (Throwable t) {
            Log.w(TAG, "settings: list not padded", t);
        }
    }

    static synchronized SharedPreferences prefs(Context c) {
        if (prefs == null) {
            loads = new Method[SECTIONS.length];
            screens = new Method[SECTIONS.length];
            for (int i = 0; i < SECTIONS.length; i++) {
                try {
                    Class<?> cls = Class.forName(SECTIONS[i]);
                    loads[i] = cls.getMethod("load", SharedPreferences.class);
                    screens[i] = cls.getMethod("screen", PreferenceFragment.class, SharedPreferences.class);
                } catch (ClassNotFoundException e) {
                    // that patch is not applied
                } catch (Throwable t) {
                    Log.w(TAG, "settings: " + SECTIONS[i] + " unusable", t);
                }
            }
            prefs = c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            prefs.registerOnSharedPreferenceChangeListener(LISTENER);  // held by LISTENER's static field
            load(prefs);
        }
        return prefs;
    }

    private static void load(SharedPreferences p) {
        for (int i = 0; i < SECTIONS.length; i++) {
            if (loads[i] != null) {
                try {
                    loads[i].invoke(null, p);
                } catch (Throwable t) {
                    Log.w(TAG, "settings: " + SECTIONS[i] + " not loaded", t);
                }
            }
        }
    }

    /** Is a class of seek-patch's in the app (that is: was its patch applied)? */
    public static boolean present(String name) {
        try {
            Class.forName(name, false, Settings.class.getClassLoader());
            return true;
        } catch (ClassNotFoundException e) {
            return false;
        }
    }

    /** A switch of the app's own class, appended to the group; it stores into p under key. */
    public static SwitchPreference addSwitch(PreferenceGroup g, final SharedPreferences p, final String key, String title,
                                             String summary, boolean byDefault, final Runnable then) {
        SwitchPreference s = (SwitchPreference) create(g.getContext(), switchType, SwitchPreference.class);
        prepare(s, key, title);
        if (summary != null) {
            s.setSummary(summary);
        }
        s.setChecked(p.getBoolean(key, byDefault));
        s.setOnPreferenceChangeListener(new Preference.OnPreferenceChangeListener() {
            @Override
            public boolean onPreferenceChange(Preference preference, Object value) {
                p.edit().putBoolean(key, Boolean.TRUE.equals(value)).apply();
                if (then != null) {
                    then.run();
                }
                return true;
            }
        });
        g.addPreference(s);
        return s;
    }

    /** A list of the app's own class (a dialog of single choices), appended; it stores the chosen value
     * into p under key, as text.  The summary shows the chosen entry (entries may hold a "%"). */
    public static ListPreference addList(PreferenceGroup g, final SharedPreferences p, final String key, String title,
                                         String[] entries, String[] values, String value, final Runnable then) {
        ListPreference l = (ListPreference) create(g.getContext(), listType, ListPreference.class);
        prepare(l, key, title);
        l.setDialogTitle(title);
        l.setEntries(entries);
        l.setEntryValues(values);
        l.setValue(value);
        l.setSummary("%s");  // ListPreference formats its summary with the chosen entry
        l.setOnPreferenceChangeListener(new Preference.OnPreferenceChangeListener() {
            @Override
            public boolean onPreferenceChange(Preference preference, Object chosen) {
                p.edit().putString(key, String.valueOf(chosen)).apply();
                if (then != null) {
                    then.run();
                }
                return true;
            }
        });
        g.addPreference(l);
        return l;
    }

    private static void prepare(Preference pref, String key, String title) {
        pref.setKey(PREFS + "_" + key);
        pref.setPersistent(false);  // kept in the seekpatch file, by the change listener
        pref.setTitle(title);
    }

    private static Preference create(Context c, Constructor<?> type, Class<? extends Preference> fallback) {
        if (type != null) {
            try {
                return (Preference) type.newInstance(c, null);
            } catch (Throwable t) {
                Log.w(TAG, "settings: " + type.getName() + " not usable", t);
            }
        }
        try {
            return fallback.getConstructor(Context.class).newInstance(c);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static Constructor<?> constructor(Class<?> type, Class<?> base) {
        try {
            if (type != null && base.isAssignableFrom(type)) {
                return type.getConstructor(Context.class, AttributeSet.class);
            }
        } catch (NoSuchMethodException ignored) {
            // the plain framework class then
        }
        return null;
    }

    /** The app's list class beside its switch class (CustomFontSwitchPreference -> CustomFontListPreference). */
    private static Class<?> listClass(Class<?> switchClass) {
        String name = switchClass.getName();
        if (name.endsWith("SwitchPreference") && !name.startsWith("android.")) {
            try {
                return Class.forName(name.substring(0, name.length() - "SwitchPreference".length()) + "ListPreference",
                        false, switchClass.getClassLoader());
            } catch (ClassNotFoundException ignored) {
                // none: the framework's
            }
        }
        return ListPreference.class;
    }
}
