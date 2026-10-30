package seekpatch;

import android.app.Activity;
import android.app.Application;
import android.app.LocaleManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.content.res.Resources;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.LocaleList;
import android.util.Log;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * seek-thermal-apk-patches' text in the language of the app's own, and the language chosen in Settings.
 *
 * <p>Helpers write their text in English and pass it through {@link #t}, or {@link #f} for a pattern
 * with values.  The translations are in {@link Strings}, which the patcher writes from
 * src/seekpatch/strings together with the languages the app itself has.  The language is the app's:
 * the one chosen in Settings (the language patch, {@link Language}), else the first of the phone's
 * languages that the app has, as Android picks the app's resources, else English.
 *
 * <p>The choice: from Android 13 it is the app's language in the system (LocaleManager), which keeps
 * it and recreates the app's screens.  Before 13 it is kept in the seekpatch preferences:
 * {@link #wrap}, called from every activity's attachBaseContext, gives each screen its resources in
 * that language, and a screen made before the choice changed is recreated when it comes back.
 */
public final class Lang {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String PREFS = "seekpatch";
    private static final String KEY = "language";
    private static final String SEPARATOR = "\u001f";
    /** The region each language is applied with: the app checks the default locale for "ru_" and "fr_". */
    private static final String[][] REGIONS = {{"de", "DE"}, {"es", "ES"}, {"fr", "FR"}, {"it", "IT"}, {"ja", "JP"},
        {"ko", "KR"}, {"nl", "NL"}, {"pt", "BR"}, {"ru", "RU"}, {"zh", "CN"}};

    private static volatile Context app;    // set by wrap: the language patch is applied
    private static volatile String chosen;  // before Android 13: the chosen tag, "" none; null: read it again
    private static int generation;          // main thread: choices so far
    private static boolean defaultChanged;  // main thread: the default locale is the chosen one
    private static final Map<Activity, Integer> MADE = new WeakHashMap<>();  // main thread: generation at creation
    private static String tableLanguage;    // guarded by Lang.class
    private static Map<String, String> table;

    private Lang() {
    }

    /** text (English) in the app's language. */
    public static String t(String text) {
        String language = language();
        if (language.equals("en")) {
            return text;
        }
        String s = translations(language).get(text);
        return s != null ? s : text;
    }

    /** pattern (English, String.format) in the app's language, with args. */
    public static String f(String pattern, Object... args) {
        return String.format(Locale.US, t(pattern), args);
    }

    /** The language of the app's text: one of the app's languages (as in Strings.languages, e.g. "pt-PT"), or "en". */
    public static String language() {
        String c = Build.VERSION.SDK_INT < 33 ? chosen() : "";
        return match(c.isEmpty() ? defaults() : new Locale[] {Locale.forLanguageTag(c)});
    }

    /** The first of these locales that the app has text in, as Android picks resources; "en" when none. */
    static String match(Locale[] locales) {
        List<String> have = languages();
        for (Locale l : locales) {
            String lang = l.getLanguage();
            if (lang.equals("en")) {
                return "en";
            }
            if (lang.equals("zh") && (l.getScript().equals("Hant") || (l.getScript().isEmpty()
                    && Arrays.asList("TW", "HK", "MO").contains(l.getCountry())))) {
                continue;  // the app's Chinese is simplified: Android does not give it to traditional
            }
            String regional = lang + "-" + l.getCountry();
            if (have.contains(regional)) {
                return regional;
            }
            if (have.contains(lang)) {
                return lang;
            }
        }
        return "en";
    }

    /** The app's own languages besides English, e.g. [de, es, ..., pt, pt-PT, ru, zh]. */
    static List<String> languages() {
        String s = Strings.languages;
        return s == null || s.isEmpty() ? Arrays.<String>asList() : Arrays.asList(s.split(","));
    }

    /** The tag a language of the app's is applied with: "ru" -> "ru-RU", "pt-PT" as it is. */
    static String tag(String language) {
        if (language.contains("-")) {
            return language;
        }
        for (String[] r : REGIONS) {
            if (r[0].equals(language)) {
                return language + "-" + r[1];
            }
        }
        return language;
    }

    /** The process' locales: the phone's, and from Android 13 also the app's own language. */
    private static Locale[] defaults() {
        if (Build.VERSION.SDK_INT >= 24) {
            return locales(LocaleList.getDefault());
        }
        return new Locale[] {Locale.getDefault()};
    }

    /** The phone's own locales, whatever the app's language (from Android 13 the system resources take the app's
     * language too: c, when given, asks LocaleManager). */
    static Locale[] phone(Context c) {
        if (Build.VERSION.SDK_INT >= 33 && c != null) {
            return locales(c.getSystemService(LocaleManager.class).getSystemLocales());
        }
        Configuration system = Resources.getSystem().getConfiguration();
        return Build.VERSION.SDK_INT >= 24 ? locales(system.getLocales()) : new Locale[] {system.locale};
    }

    private static Locale[] locales(LocaleList list) {
        Locale[] out = new Locale[list.size()];
        for (int i = 0; i < out.length; i++) {
            out[i] = list.get(i);
        }
        return out;
    }

    private static synchronized Map<String, String> translations(String language) {
        String base = language.split("-")[0];
        if (!base.equals(tableLanguage)) {
            Map<String, String> m = new HashMap<>();
            try {
                Object values = Strings.class.getField(base).get(null);
                if (values instanceof String && Strings.english != null) {
                    String[] en = Strings.english.split(SEPARATOR, -1);
                    String[] tr = ((String) values).split(SEPARATOR, -1);
                    for (int i = 0; i < en.length && i < tr.length; i++) {
                        if (!tr[i].isEmpty()) {
                            m.put(en[i], tr[i]);
                        }
                    }
                }
            } catch (NoSuchFieldException e) {
                // no translation into it: English
            } catch (Throwable t) {
                Log.w(TAG, "language: no " + base + " text", t);
            }
            table = m;
            tableLanguage = base;
        }
        return table;
    }

    // -- the choice (the language patch) ------------------------------------------------------------

    /** The chosen language's tag, "" for the phone's. */
    static String current(Context c) {
        if (Build.VERSION.SDK_INT >= 33) {
            LocaleList l = c.getSystemService(LocaleManager.class).getApplicationLocales();
            return l.isEmpty() ? "" : l.get(0).toLanguageTag();
        }
        return prefs(c).getString(KEY, "");
    }

    /** Settings: show the app in this language ("" the phone's). */
    static void choose(Activity a, String tag) {
        Log.i(TAG, "language: " + (tag.isEmpty() ? "the phone's" : tag));
        if (Build.VERSION.SDK_INT >= 33) {
            a.getSystemService(LocaleManager.class).setApplicationLocales(
                    tag.isEmpty() ? LocaleList.getEmptyLocaleList() : LocaleList.forLanguageTags(tag));
            return;  // Android recreates the screens
        }
        prefs(a).edit().putString(KEY, tag).commit();  // read again in the next attachBaseContext
        chosen = tag;
        generation++;
        defaultLocale(tag);
        a.recreate();  // and every other screen when it comes back
    }

    /** Before Android 13: the chosen tag, "" none or not known. */
    private static String chosen() {
        String c = chosen;
        if (c == null) {
            Context a = app;
            if (a == null) {
                return "";
            }
            c = prefs(a).getString(KEY, "");
            chosen = c;
        }
        return c;
    }

    /** Every activity's attachBaseContext (the language patch): before Android 13, base in the chosen language. */
    public static Context wrap(Context base) {
        try {
            if (app == null) {
                Context a = base.getApplicationContext();
                app = a != null ? a : base;
                if (Build.VERSION.SDK_INT < 33 && a instanceof Application) {
                    watch((Application) a);
                }
            }
            if (Build.VERSION.SDK_INT >= 33) {
                return base;
            }
            chosen = null;
            String c = chosen();
            defaultLocale(c);
            if (c.isEmpty()) {
                return base;
            }
            Configuration o = new Configuration();
            o.fontScale = 0;  // undefined, as everything else but the locale: the rest follows the phone
            o.setLocale(Locale.forLanguageTag(c));
            return base.createConfigurationContext(o);
        } catch (Throwable t) {
            Log.w(TAG, "language: not applied", t);
            return base;
        }
    }

    /** The default locale (number formats, and the app's own checks for "ru_" and "fr_"): the chosen one.  Android
     * sets it back to the phone's at every configuration change; after a choice of the phone's language it is
     * set back here, the phone's locales with the one the app has text in first, as Android orders them. */
    private static void defaultLocale(String tag) {
        if (!tag.isEmpty()) {
            Locale.setDefault(Locale.forLanguageTag(tag));
            defaultChanged = true;
        } else if (defaultChanged) {
            defaultChanged = false;
            Locale[] phone = phone(null);  // before Android 13 only
            String language = match(phone);
            for (int i = 0; i < phone.length; i++) {
                if (match(new Locale[] {phone[i]}).equals(language)) {
                    Locale first = phone[i];
                    System.arraycopy(phone, 0, phone, 1, i);
                    phone[0] = first;
                    break;
                }
            }
            if (Build.VERSION.SDK_INT >= 24) {
                LocaleList.setDefault(new LocaleList(phone));
            } else {
                Locale.setDefault(phone[0]);
            }
        }
    }

    /** Before Android 13: a screen made before the latest choice is recreated when it comes back. */
    private static void watch(Application a) {
        a.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override
            public void onActivityCreated(Activity activity, Bundle state) {
                MADE.put(activity, generation);
            }

            @Override
            public void onActivityResumed(final Activity activity) {
                defaultLocale(chosen());
                Integer made = MADE.get(activity);
                if (made != null && made < generation) {
                    MADE.remove(activity);
                    new Handler(Looper.getMainLooper()).post(new Runnable() {
                        @Override
                        public void run() {
                            if (!activity.isFinishing()) {
                                activity.recreate();
                            }
                        }
                    });
                }
            }

            @Override
            public void onActivityStarted(Activity activity) {
            }

            @Override
            public void onActivityPaused(Activity activity) {
            }

            @Override
            public void onActivityStopped(Activity activity) {
            }

            @Override
            public void onActivitySaveInstanceState(Activity activity, Bundle state) {
            }

            @Override
            public void onActivityDestroyed(Activity activity) {
            }
        });
    }

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
