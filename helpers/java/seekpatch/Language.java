package seekpatch;

import android.app.Activity;
import android.content.Context;
import android.preference.ListPreference;
import android.preference.Preference;
import android.preference.PreferenceFragment;
import android.preference.PreferenceScreen;
import android.util.AttributeSet;
import android.util.Log;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * seek-thermal-apk-patches language: a Language list at the top of the app's Settings screen.
 *
 * <p>It offers the phone's language and every language the app has text in (Strings.languages, read
 * from the app when it was patched), each named in itself; {@link Lang#choose} applies the choice.
 * The title also says "(Language)" in English, so the list can be found again in a language one
 * cannot read.  The list is of the app's own class, like the screen's other lists.
 */
public final class Language {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String SPACER = "spacer_above";
    /** A list of the app's own on that screen: its class is the one ours copies. */
    private static final String TEMPLATE = "emissivity_and_background";

    private Language() {
    }

    /** The Settings screen, after addPreferencesFromResource. */
    public static void screen(PreferenceFragment f) {
        try {
            final Activity a = f.getActivity();
            PreferenceScreen s = f.getPreferenceScreen();
            if (a == null || s == null) {
                return;
            }
            List<String> languages = new ArrayList<>(Lang.languages());
            languages.add("en");
            final List<String> names = new ArrayList<>();
            for (String language : languages) {
                names.add(name(language));
            }
            List<Integer> order = new ArrayList<>();
            for (int i = 0; i < languages.size(); i++) {
                order.add(i);
            }
            Collections.sort(order, new Comparator<Integer>() {
                @Override
                public int compare(Integer x, Integer y) {
                    return names.get(x).compareToIgnoreCase(names.get(y));
                }
            });
            String[] entries = new String[languages.size() + 1];
            String[] values = new String[languages.size() + 1];
            entries[0] = Lang.f("System default (%s)", name(Lang.match(Lang.phone(a))));
            values[0] = "";
            for (int i = 0; i < order.size(); i++) {
                entries[i + 1] = names.get(order.get(i));
                values[i + 1] = Lang.tag(languages.get(order.get(i)));
            }
            String current = Lang.current(a);
            String value = current.isEmpty() ? "" : Lang.tag(Lang.match(new Locale[] {Locale.forLanguageTag(current)}));
            if (!Arrays.asList(values).contains(value)) {
                value = "";  // chosen in a version of the app that had that language
            }
            String title = Lang.t("Language");
            if (!Lang.language().equals("en")) {
                title += " (Language)";
            }
            ListPreference l = list(a, f.findPreference(TEMPLATE));
            l.setKey("seekpatch_language");
            l.setPersistent(false);  // the choice is kept by Lang
            l.setTitle(title);
            l.setDialogTitle(title);
            l.setEntries(entries);
            l.setEntryValues(values);
            l.setValue(value);
            l.setSummary("%s");  // the chosen entry
            l.setOnPreferenceChangeListener(new Preference.OnPreferenceChangeListener() {
                @Override
                public boolean onPreferenceChange(Preference p, Object chosen) {
                    String tag = String.valueOf(chosen);
                    if (!tag.equals(((ListPreference) p).getValue())) {
                        Lang.choose(a, tag);
                    }
                    return true;
                }
            });
            Preference spacer = f.findPreference(SPACER);
            int at = spacer != null ? spacer.getOrder() + 1 : 0;  // first, below the app's spacer
            for (int i = 0; i < s.getPreferenceCount(); i++) {
                Preference p = s.getPreference(i);
                if (p.getOrder() >= at) {
                    p.setOrder(p.getOrder() + 1);
                }
            }
            l.setOrder(at);
            s.addPreference(l);
        } catch (Throwable t) {
            Log.w(TAG, "language: no list", t);
        }
    }

    /** A language's name in itself: "Deutsch", "Português (Portugal)"; the app's Chinese is simplified, "简体中文"
     * (Android names zh-Hans "中文 (简体中文)"). */
    static String name(String language) {
        if (language.equals("zh")) {
            return "简体中文";
        }
        Locale l = Locale.forLanguageTag(language);
        String n = l.getDisplayName(l);
        return n.isEmpty() ? language : n.substring(0, 1).toUpperCase(l) + n.substring(1);
    }

    private static ListPreference list(Context c, Preference template) {
        if (template instanceof ListPreference) {
            try {
                return (ListPreference) template.getClass().getConstructor(Context.class, AttributeSet.class)
                        .newInstance(c, null);
            } catch (Throwable t) {
                Log.w(TAG, "language: " + template.getClass().getName() + " not usable", t);
            }
        }
        return new ListPreference(c);
    }
}
