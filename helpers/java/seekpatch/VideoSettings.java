package seekpatch;

import android.content.SharedPreferences;
import android.media.MediaCodecInfo.CodecCapabilities;
import android.media.MediaCodecInfo.EncoderCapabilities;
import android.media.MediaFormat;
import android.preference.ListPreference;
import android.preference.PreferenceFragment;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

/**
 * seek-thermal-apk-patches video_quality: its settings.  <i>Video codec</i>, H.265 or H.264, starts from the
 * patch's H.265 and sets {@link VideoConfig#mime}.  <i>Video quality</i> is either the
 * encoder's constant quantizer, starting from QP 18 ({@link VideoConfig#qp}), or a bitrate
 * ({@link VideoConfig#target}, VBR).  seekpatch.Video reads them when a recording starts.
 *
 * <p>The QP sizes shown are the measured HEVC ladder on a still scene (docs/video-quality.md);
 * H.264 needs about 20 % more.  A QP needs an encoder that takes QP bounds (Android 12+) or has a
 * constant-quality mode; where the encoder that will record has neither, the list has only the
 * bitrates, and its default is the one seekpatch.Video records at then (VideoConfig.bitrate,
 * 12 Mbit/s).  The bitrates go up to the encoder's highest.  A phone without an H.265
 * encoder records H.264 whatever the codec setting, and the list says so.
 */
public final class VideoSettings {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final String QP = "video_qp";  // a QP ("18") or a bitrate ("m8": 8 Mbit/s)
    private static final String CODEC = "video_codec";
    private static final String MBPS = "m";
    private static final String HEVC = MediaFormat.MIMETYPE_VIDEO_HEVC;
    private static final String AVC = MediaFormat.MIMETYPE_VIDEO_AVC;
    private static final int[] CHOICES = {14, 16, 18, 20, 22, 24, 26, 28};
    private static final int[] MB_PER_MIN = {115, 91, 68, 53, 40, 31, 23, 16};
    private static final int[] BITRATES = {2, 4, 6, 8, 12, 16, 20, 30, 40};  // Mbit/s
    /** QP 18 and H.265: the fields' values before any setting is loaded. */
    private static final int DEFAULT = VideoConfig.qp;
    private static final String DEFAULT_MIME = AVC.equals(VideoConfig.mime) ? AVC : HEVC;

    private static int loadedQp = -1;
    private static int loadedTarget = -1;
    private static String loadedMime;

    private VideoSettings() {
    }

    /** Settings: the values (main thread); used from the next recording. */
    public static void load(SharedPreferences p) {
        VideoConfig.qp = qp(p);
        VideoConfig.target = target(p);
        VideoConfig.mime = mime(p);
        if (VideoConfig.qp != loadedQp || VideoConfig.target != loadedTarget || !VideoConfig.mime.equals(loadedMime)) {
            loadedQp = VideoConfig.qp;
            loadedTarget = VideoConfig.target;
            loadedMime = VideoConfig.mime;
            Log.i(TAG, "video_quality: " + (HEVC.equals(loadedMime) ? "H.265" : "H.264") + " "
                    + (loadedTarget > 0 ? loadedTarget / 1000000 + " Mbit/s" : "QP " + loadedQp)
                    + " from the next recording");
        }
    }

    /** Settings: the lists, appended. */
    public static void screen(PreferenceFragment f, final SharedPreferences p) {
        final ListPreference[] quality = new ListPreference[1];
        boolean hevc = HEVC.equals(encoder(HEVC).mime);
        String h265 = hevc ? Lang.t("H.265 (HEVC): smaller files") : Lang.t("H.265 (HEVC): not on this phone, records H.264");
        String h264 = Lang.t("H.264 (AVC): plays everywhere, about 20 % bigger");
        Settings.addList(f.getPreferenceScreen(), p, CODEC, Lang.t("Video codec"),
                new String[] {mark(h265, HEVC), mark(h264, AVC)}, new String[] {"hevc", "avc"},
                AVC.equals(mime(p)) ? "avc" : "hevc", new Runnable() {
                    @Override
                    public void run() {
                        if (quality[0] != null) {
                            entries(quality[0], p);  // the sizes and bitrates go with the encoder
                        }
                    }
                });
        quality[0] = Settings.addList(f.getPreferenceScreen(), p, QP, Lang.t("Video quality"), new String[0], new String[0],
                value(p), null);
        quality[0].setDialogTitle(Lang.t("QP: steady quality, Mbit/s: steady size"));
        entries(quality[0], p);
    }

    private static String mark(String entry, String mime) {
        return mime.equals(DEFAULT_MIME) ? Lang.f("%s (default)", entry) : entry;
    }

    /** The quality list's entries, for the encoder that will record: its QPs, then its bitrates. */
    private static void entries(ListPreference l, SharedPreferences p) {
        Video.Candidate c = encoder(mime(p));
        boolean avc = !HEVC.equals(c.mime);
        int max = Integer.MAX_VALUE;
        boolean takesQp = true;
        int fallback = VideoConfig.bitrate;
        if (c.info != null) {
            CodecCapabilities caps = c.info.getCapabilitiesForType(c.mime);
            max = caps.getVideoCapabilities().getBitrateRange().getUpper();
            takesQp = Video.takesQp(caps)
                    || caps.getEncoderCapabilities().isBitrateModeSupported(EncoderCapabilities.BITRATE_MODE_CQ);
            int[] size = Video.photoSize(480, 640);
            fallback = Math.min(max, Video.fallbackBitrate(size[0], size[1]));
        }
        List<String> entries = new ArrayList<>();
        List<String> values = new ArrayList<>();
        int fallbackMbps = (int) Math.round(fallback / 1e6);
        String value = value(p);
        if (takesQp) {
            boolean listed = false;
            for (int i = 0; i < CHOICES.length; i++) {
                if (!listed && DEFAULT < CHOICES[i]) {
                    addQp(entries, values, DEFAULT, 0, avc);  // a start QP the list does not have
                    listed = true;
                }
                listed |= CHOICES[i] == DEFAULT;
                addQp(entries, values, CHOICES[i], MB_PER_MIN[i], avc);
            }
            if (!listed) {
                addQp(entries, values, DEFAULT, 0, avc);
            }
        } else if (target(p) == 0) {
            value = MBPS + fallbackMbps;  // a QP records at the fallback bitrate: shown as that
        }
        boolean fallbackListed = false;
        for (int mbps : BITRATES) {
            if (!takesQp && !fallbackListed && fallbackMbps <= mbps) {
                if (fallbackMbps < mbps) {
                    addMbps(entries, values, fallbackMbps, true);  // an encoder that stops below 12
                }
                fallbackListed = true;
            }
            if (mbps * 1000000L <= max) {
                addMbps(entries, values, mbps, !takesQp && mbps == fallbackMbps);
            }
        }
        l.setEntries(entries.toArray(new String[0]));
        l.setEntryValues(values.toArray(new String[0]));
        l.setValue(value);
        l.setSummary(null);
        l.setSummary("%s");  // shown again with the new entry
    }

    private static void addMbps(List<String> entries, List<String> values, int mbps, boolean byDefault) {
        String label = Lang.f("%1$d Mbit/s: about %2$d MB a minute", mbps, Math.round(mbps * 7.5));
        entries.add(byDefault ? Lang.f("%s (default)", label) : label);
        values.add(MBPS + mbps);
    }

    private static void addQp(List<String> entries, List<String> values, int qp, int mb, boolean avc) {
        String label = mb > 0 ? Lang.f("QP %1$d: about %2$d MB a minute", qp, Math.round(avc ? mb * 1.2f : mb))
                : Lang.f("QP %d", qp);
        if (qp == CHOICES[0]) {
            label = Lang.f("%s, best", label);
        } else if (qp == CHOICES[CHOICES.length - 1]) {
            label = Lang.f("%s, smallest", label);
        }
        if (qp == DEFAULT) {
            label = Lang.f("%s (default)", label);
        }
        entries.add(label);
        values.add(String.valueOf(qp));
    }

    /** The encoder seekpatch.Video would take for this codec (no info: none at all). */
    private static Video.Candidate encoder(String mime) {
        try {
            int[] size = Video.photoSize(480, 640);  // the app's video size, scaled as seekpatch.Video does
            List<Video.Candidate> all = Video.candidates(mime, size[0], size[1]);
            if (!all.isEmpty()) {
                return all.get(0);
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "video_quality: encoders not listed", e);
        }
        return new Video.Candidate(null, AVC);
    }

    private static String value(SharedPreferences p) {
        int target = target(p);
        return target > 0 ? MBPS + target / 1000000 : String.valueOf(qp(p));
    }

    private static int qp(SharedPreferences p) {
        try {
            int qp = Integer.parseInt(p.getString(QP, String.valueOf(DEFAULT)));
            return qp >= 10 && qp <= 40 ? qp : DEFAULT;
        } catch (RuntimeException e) {
            return DEFAULT;
        }
    }

    /** A chosen bitrate, bit/s; 0: a QP. */
    private static int target(SharedPreferences p) {
        try {
            String v = p.getString(QP, "");
            if (v.startsWith(MBPS)) {
                int mbps = Integer.parseInt(v.substring(MBPS.length()));
                return mbps >= 1 && mbps <= 100 ? mbps * 1000000 : 0;
            }
        } catch (RuntimeException e) {
            // a QP, or nothing
        }
        return 0;
    }

    private static String mime(SharedPreferences p) {
        try {
            String v = p.getString(CODEC, null);
            return "avc".equals(v) ? AVC : "hevc".equals(v) ? HEVC : DEFAULT_MIME;
        } catch (RuntimeException e) {
            return DEFAULT_MIME;
        }
    }
}
