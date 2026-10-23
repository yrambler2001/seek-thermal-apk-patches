package seekpatch;

/**
 * Compile-time stand-in.  The video_quality patch writes the real class into the app, with the
 * values from the command line (see src/seekpatch/patches/video_quality.py).
 */
public final class VideoConfig {
    /** "video/hevc" or "video/avc": the codec tried first. */
    public static String mime;
    /** Constant QP for P frames (I frames get qp - 2). */
    public static int qp;
    /** The photo's long side; videos are scaled up to it. */
    public static int longSide;
    /** Ceiling for the constant-QP encoder, bit/s. */
    public static int maxBitrate;
    /** Bitrate for a 960x1280 frame when the encoder has no quality control, bit/s. */
    public static int bitrate;

    private VideoConfig() {
    }
}
