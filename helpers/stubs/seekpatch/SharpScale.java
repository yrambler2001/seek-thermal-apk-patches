package seekpatch;

/**
 * Compile-time stand-in.  The sharp_scaling patch writes the real class into the app, with the
 * starting values, Sharp 2, as the fields' initial values (see src/seekpatch/patches/sharp_scaling.py).
 */
public final class SharpScale {
    /** The shader's blend width, 1/sharpness of a texel; 1 or less: the stock bilinear sample. */
    public static float sharpness;
    /** The photo's nearest upscale factor before the filtered draw; 1: the stock draw; 0: drawn unfiltered. */
    public static int photoFactor;

    private SharpScale() {
    }
}
