package seekpatch;

/**
 * Compile-time stand-in.  add_helpers() writes the real class into the app with seekpatch.Lang (see
 * src/seekpatch/strings): the app's languages, and the patches' text in each of them.
 */
public final class Strings {
    /** The languages of the app's own text besides English, BCP 47, comma-separated: "de,es,...,pt-PT,ru,zh". */
    public static String languages;
    /** The patches' English strings, separated by U+001F. */
    public static String english;
    // and one field per language of the app's (de, es, ...): the translations, in the order of english

    private Strings() {
    }
}
