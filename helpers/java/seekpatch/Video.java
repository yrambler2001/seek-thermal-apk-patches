package seekpatch;

import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecInfo.CodecCapabilities;
import android.media.MediaCodecInfo.CodecProfileLevel;
import android.media.MediaCodecInfo.EncoderCapabilities;
import android.media.MediaCodecInfo.VideoCapabilities;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.os.Build;
import android.util.Log;
import android.util.Range;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * seek-thermal-apk-patches video_quality: the encoder for the app's video recordings.
 *
 * <p>Called in place of {@code MediaCodec.createEncoderByType(...)} + {@code configure(...)} with the
 * app's own format (H.264, 480x640, 1.5 Mbit/s) and returns a configured encoder.  In order of
 * preference: hardware before software, the configured codec (HEVC by default) before H.264, the
 * photo's size, and for rate control constant QP (encoders that take QP bounds, Android 12+), then
 * constant-quality mode, then VBR at 12 Mbit/s -- or, with a bitrate chosen in the settings, VBR at
 * that bitrate.  Each encoder is tried with the full setup, then plainer ones; if none configures, the
 * app's own format is used.
 */
public final class Video {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final int FULL = 3;   // rate control + profile + colour description
    private static final int RATE = 2;   // rate control + colour description (some encoders refuse the profile)
    private static final int PLAIN = 1;  // colour description, VBR at the chosen or the fallback bitrate
    private static final int MINIMAL = 0;

    private Video() {
    }

    public static MediaCodec encoder(MediaFormat stock) throws IOException {
        int[] size = photoSize(stock.getInteger(MediaFormat.KEY_WIDTH), stock.getInteger(MediaFormat.KEY_HEIGHT));
        for (Candidate c : candidates(VideoConfig.mime, size[0], size[1])) {
            for (int setup = FULL; setup >= MINIMAL; setup--) {
                MediaCodec codec = null;
                try {
                    MediaFormat format = format(c.info, c.mime, size[0], size[1], setup);
                    codec = MediaCodec.createByCodecName(c.info.getName());
                    codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
                    Log.i(TAG, "video: " + c.info.getName() + " " + format);
                    return codec;
                } catch (Exception e) {  // IllegalArgumentException, MediaCodec.CodecException, IOException
                    Log.w(TAG, "video: " + c.info.getName() + " refused setup " + setup + ": " + e);
                    if (codec != null) {
                        codec.release();
                    }
                }
            }
        }
        Log.w(TAG, "video: no encoder took the quality setup; recording with the app's own");
        MediaCodec codec = MediaCodec.createEncoderByType(stock.getString(MediaFormat.KEY_MIME));
        codec.configure(stock, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        return codec;
    }

    /** The app's size scaled up so its long side is the photo's (1280): 480x640 -> 960x1280. */
    static int[] photoSize(int w, int h) {
        int longSide = Math.max(w, h);
        if (VideoConfig.longSide <= longSide) {
            return new int[] {w, h};
        }
        double s = (double) VideoConfig.longSide / longSide;
        return new int[] {even(w * s), even(h * s)};
    }

    private static int even(double v) {
        return 2 * (int) Math.round(v / 2);
    }

    static final class Candidate {
        final MediaCodecInfo info;
        final String mime;

        Candidate(MediaCodecInfo info, String mime) {
            this.info = info;
            this.mime = mime;
        }
    }

    /** Encoders that take this size: every hardware one (the codec first, then H.264), then software. */
    static List<Candidate> candidates(String mime, int w, int h) {
        String[] mimes = mime.equals(MediaFormat.MIMETYPE_VIDEO_AVC)
                ? new String[] {MediaFormat.MIMETYPE_VIDEO_AVC}
                : new String[] {mime, MediaFormat.MIMETYPE_VIDEO_AVC};
        List<Candidate> hardware = new ArrayList<>();
        List<Candidate> software = new ArrayList<>();
        MediaCodecInfo[] infos = new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos();
        for (String m : mimes) {
            for (MediaCodecInfo info : infos) {
                if (!info.isEncoder() || (Build.VERSION.SDK_INT >= 29 && info.isAlias()) || !supports(info, m)) {
                    continue;
                }
                VideoCapabilities vc = info.getCapabilitiesForType(m).getVideoCapabilities();
                if (vc != null && vc.isSizeSupported(w, h)) {
                    (isHardware(info) ? hardware : software).add(new Candidate(info, m));
                }
            }
        }
        hardware.addAll(software);
        return hardware;
    }

    private static boolean supports(MediaCodecInfo info, String mime) {
        for (String t : info.getSupportedTypes()) {
            if (t.equalsIgnoreCase(mime)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isHardware(MediaCodecInfo info) {
        if (Build.VERSION.SDK_INT >= 29) {
            return info.isHardwareAccelerated();
        }
        String n = info.getName().toLowerCase(Locale.ROOT);
        return !(n.startsWith("omx.google.") || n.startsWith("c2.android.") || n.contains(".sw."));
    }

    static MediaFormat format(MediaCodecInfo info, String mime, int w, int h, int setup) {
        CodecCapabilities caps = info.getCapabilitiesForType(mime);
        Range<Integer> bitrates = caps.getVideoCapabilities().getBitrateRange();
        MediaFormat f = MediaFormat.createVideoFormat(mime, w, h);
        f.setInteger(MediaFormat.KEY_COLOR_FORMAT, CodecCapabilities.COLOR_FormatSurface);
        f.setInteger(MediaFormat.KEY_FRAME_RATE, 30);  // a rate-control hint: frames come per thermal frame
        f.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
        f.setInteger(MediaFormat.KEY_BIT_RATE, bitrates.clamp(VideoConfig.target > 0 ? VideoConfig.target
                : fallbackBitrate(w, h)));
        if (setup >= PLAIN) {
            if (Build.VERSION.SDK_INT >= 24) {  // so players turn YUV back into the photo's RGB
                f.setInteger(MediaFormat.KEY_COLOR_STANDARD, MediaFormat.COLOR_STANDARD_BT709);
                f.setInteger(MediaFormat.KEY_COLOR_RANGE, MediaFormat.COLOR_RANGE_LIMITED);
                f.setInteger(MediaFormat.KEY_COLOR_TRANSFER, MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
            }
            f.setInteger(MediaFormat.KEY_PRIORITY, 0);  // realtime
            if (caps.getEncoderCapabilities().isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_VBR)) {
                f.setInteger(MediaFormat.KEY_BITRATE_MODE, EncoderCapabilities.BITRATE_MODE_VBR);
            }
        }
        if (setup >= FULL) {
            profile(f, caps, mime);
        }
        if (setup >= RATE && VideoConfig.target <= 0) {  // a chosen bitrate is the VBR above
            EncoderCapabilities ec = caps.getEncoderCapabilities();
            if (takesQp(caps)) {
                int q = VideoConfig.qp;
                // QP bounds pin the quantizer; the bitrate is only a ceiling the encoder may use
                f.setInteger(MediaFormat.KEY_BIT_RATE, bitrates.clamp(VideoConfig.maxBitrate));
                f.setInteger(MediaFormat.KEY_VIDEO_QP_MIN, q - 2);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_MAX, q + 2);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_I_MIN, q - 2);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_I_MAX, q - 2);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_P_MIN, q);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_P_MAX, q);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_B_MIN, q + 2);
                f.setInteger(MediaFormat.KEY_VIDEO_QP_B_MAX, q + 2);
            } else if (ec.isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_CQ)) {
                Range<Integer> quality = ec.getQualityRange();
                f.setInteger(MediaFormat.KEY_BITRATE_MODE, EncoderCapabilities.BITRATE_MODE_CQ);
                f.setInteger(MediaFormat.KEY_QUALITY, quality.getLower()
                        + Math.round((quality.getUpper() - quality.getLower()) * (51 - VideoConfig.qp) / 51f));
            }
        }
        return f;
    }

    /** Constant QP: QP bounds (Android 12+). */
    static boolean takesQp(CodecCapabilities caps) {
        return Build.VERSION.SDK_INT >= 31 && caps.isFeatureSupported(CodecCapabilities.FEATURE_QpBounds);
    }

    /** VideoConfig.bitrate is for a photo-sized (960x1280) frame; other sizes scale by area. */
    static int fallbackBitrate(int w, int h) {
        return (int) Math.min(Integer.MAX_VALUE, (long) VideoConfig.bitrate * w * h / (960 * 1280));
    }

    /** HEVC Main / H.264 High, when the encoder lists it; the level is left to the encoder. */
    private static void profile(MediaFormat f, CodecCapabilities caps, String mime) {
        int want = mime.equals(MediaFormat.MIMETYPE_VIDEO_HEVC) ? CodecProfileLevel.HEVCProfileMain
                : mime.equals(MediaFormat.MIMETYPE_VIDEO_AVC) ? CodecProfileLevel.AVCProfileHigh : -1;
        for (CodecProfileLevel pl : caps.profileLevels) {
            if (pl.profile == want) {
                f.setInteger(MediaFormat.KEY_PROFILE, want);
                return;
            }
        }
    }
}
