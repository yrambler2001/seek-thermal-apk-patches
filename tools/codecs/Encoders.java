import android.media.MediaCodecInfo;
import android.media.MediaCodecInfo.CodecCapabilities;
import android.media.MediaCodecInfo.CodecProfileLevel;
import android.media.MediaCodecInfo.EncoderCapabilities;
import android.media.MediaCodecInfo.VideoCapabilities;
import android.media.MediaCodecList;

/** Run with app_process (tools/codecs.py list): the phone's video and AAC encoders, as video_quality sees them. */
public class Encoders {
    public static void main(String[] args) {
        int w = 960, h = 1280;
        for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
            if (!info.isEncoder()) continue;
            for (String type : info.getSupportedTypes()) {
                if (!type.startsWith("video/") && !type.equals("audio/mp4a-latm")) continue;
                CodecCapabilities caps = info.getCapabilitiesForType(type);
                EncoderCapabilities ec = caps.getEncoderCapabilities();
                StringBuilder s = new StringBuilder(info.getName()).append("  ").append(type)
                        .append(info.isHardwareAccelerated() ? "  hardware" : "  software");
                s.append("\n    rate control:");
                if (ec.isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_CQ)) s.append(" constant-quality");
                if (ec.isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_VBR)) s.append(" VBR");
                if (ec.isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_CBR)) s.append(" CBR");
                if (caps.isFeatureSupported(CodecCapabilities.FEATURE_QpBounds)) s.append(", QP bounds");
                VideoCapabilities vc = caps.getVideoCapabilities();
                if (vc != null) {
                    s.append("\n    sizes ").append(vc.getSupportedWidths()).append(" x ").append(vc.getSupportedHeights())
                            .append(", bitrate ").append(vc.getBitrateRange());
                    s.append("\n    ").append(w).append("x").append(h).append(": ");
                    if (vc.isSizeSupported(w, h)) {
                        s.append("rated ").append(vc.getAchievableFrameRatesFor(w, h)).append(" fps");
                    } else {
                        s.append("not supported");
                    }
                    s.append("\n    profiles:");
                    for (CodecProfileLevel pl : caps.profileLevels) s.append(' ').append(profile(type, pl.profile));
                } else if (caps.getAudioCapabilities() != null) {
                    s.append("\n    rates ").append(java.util.Arrays.toString(caps.getAudioCapabilities().getSupportedSampleRates()))
                            .append(", channels <= ").append(caps.getAudioCapabilities().getMaxInputChannelCount())
                            .append(", bitrate ").append(caps.getAudioCapabilities().getBitrateRange());
                }
                System.out.println(s);
            }
        }
    }

    /** Profile names for the codecs that have 4:4:4 variants; numbers for the rest. */
    static String profile(String type, int p) {
        if (type.equals("video/avc")) {
            switch (p) {
                case CodecProfileLevel.AVCProfileBaseline: return "Baseline";
                case CodecProfileLevel.AVCProfileConstrainedBaseline: return "ConstrainedBaseline";
                case CodecProfileLevel.AVCProfileMain: return "Main";
                case CodecProfileLevel.AVCProfileHigh: return "High";
                case CodecProfileLevel.AVCProfileConstrainedHigh: return "ConstrainedHigh";
                case CodecProfileLevel.AVCProfileHigh444: return "High444(4:4:4)";
                default: return "0x" + Integer.toHexString(p);
            }
        }
        if (type.equals("video/hevc")) {
            switch (p) {
                case CodecProfileLevel.HEVCProfileMain: return "Main";
                case CodecProfileLevel.HEVCProfileMain10: return "Main10";
                case CodecProfileLevel.HEVCProfileMain10HDR10: return "Main10HDR10";
                case CodecProfileLevel.HEVCProfileMain10HDR10Plus: return "Main10HDR10Plus";
                case CodecProfileLevel.HEVCProfileMainStill: return "MainStill";
                default: return "0x" + Integer.toHexString(p);
            }
        }
        if (type.equals("video/av01")) {
            switch (p) {
                case CodecProfileLevel.AV1ProfileMain8: return "Main8";
                case CodecProfileLevel.AV1ProfileMain10: return "Main10";
                case CodecProfileLevel.AV1ProfileMain10HDR10: return "Main10HDR10";
                case CodecProfileLevel.AV1ProfileMain10HDR10Plus: return "Main10HDR10Plus";
                default: return "0x" + Integer.toHexString(p);
            }
        }
        return "0x" + Integer.toHexString(p);
    }
}
