package seekpatch;

import java.nio.ByteBuffer;

/**
 * Compile-time stand-in.  The flat_field patch writes the real class into the app: each method
 * calls the app's own seekIPsetFeature / seekIPgetFeature (see src/seekpatch/patches/flat_field.py).
 */
public final class SeekIP {
    private SeekIP() {
    }

    /** libseekip's seekip_setfeature(handle, feature, value, length): 0 = done. */
    public static int setFeature(long handle, int feature, ByteBuffer value, int length) {
        throw new UnsupportedOperationException();
    }

    /** libseekip's seekip_getfeature(handle, feature, out, length): 0 = done. */
    public static int getFeature(long handle, int feature, ByteBuffer out, int length) {
        throw new UnsupportedOperationException();
    }
}
