package seekpatch;

/**
 * Compile-time stand-in.  settings.py writes the real class into the app, with the version of
 * seek-patch that patched it (see src/seekpatch/patches/settings.py).
 */
public final class About {
    /** seek-patch's version, e.g. "0.4.0". */
    public static String version;

    private About() {
    }
}
