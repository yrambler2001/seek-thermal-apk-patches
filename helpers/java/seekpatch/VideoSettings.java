package seekpatch;

import android.content.SharedPreferences;
import android.preference.PreferenceFragment;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

/**
 * seek-patch video_quality: its setting, <i>Video quality</i>, the encoder's constant quantizer.  It
 * starts from the patch's --video-qp (the field's initial value) and sets {@link VideoConfig#qp},
 * which seekpatch.Video reads when a recording starts.  The sizes shown are the measured HEVC ladder
 * on a still scene (docs/video-quality.md); H.264 needs about 20 % more.
 */
public final class VideoSettings {
    private static final String TAG = "seek-patch";
    private static final String QP = "video_qp";
    private static final int[] CHOICES = {14, 16, 18, 20, 22, 24, 26, 28};
    private static final int[] MB_PER_MIN = {115, 91, 68, 53, 40, 31, 23, 16};
    /** --video-qp: the field's value before any setting is loaded. */
    private static final int DEFAULT = VideoConfig.qp;

    private static int loaded = -1;

    private VideoSettings() {
    }

    /** Settings: the value (main thread); used from the next recording. */
    public static void load(SharedPreferences p) {
        VideoConfig.qp = qp(p);
        if (VideoConfig.qp != loaded) {
            loaded = VideoConfig.qp;
            Log.i(TAG, "video_quality: QP " + loaded + " from the next recording");
        }
    }

    /** Settings: the list, appended. */
    public static void screen(PreferenceFragment f, SharedPreferences p) {
        List<String> entries = new ArrayList<>();
        List<String> values = new ArrayList<>();
        boolean listed = false;
        for (int i = 0; i < CHOICES.length; i++) {
            if (!listed && DEFAULT < CHOICES[i]) {
                add(entries, values, DEFAULT, 0);  // a --video-qp the list does not have
                listed = true;
            }
            listed |= CHOICES[i] == DEFAULT;
            add(entries, values, CHOICES[i], MB_PER_MIN[i]);
        }
        if (!listed) {
            add(entries, values, DEFAULT, 0);
        }
        Settings.addList(f.getPreferenceScreen(), p, QP, "Video quality", entries.toArray(new String[0]),
                values.toArray(new String[0]), String.valueOf(qp(p)), null)
                .setDialogTitle("Video quality: lower QP is better and bigger (sizes on a still scene)");
    }

    private static void add(List<String> entries, List<String> values, int qp, int mb) {
        boolean avc = "video/avc".equals(VideoConfig.mime);
        String label = "QP " + qp;
        if (mb > 0) {
            label += ": about " + Math.round(avc ? mb * 1.2f : mb) + " MB a minute";
        }
        if (qp == CHOICES[0]) {
            label += ", best";
        } else if (qp == CHOICES[CHOICES.length - 1]) {
            label += ", smallest";
        }
        if (qp == DEFAULT) {
            label += " (default)";
        }
        entries.add(label);
        values.add(String.valueOf(qp));
    }

    private static int qp(SharedPreferences p) {
        try {
            int qp = Integer.parseInt(p.getString(QP, String.valueOf(DEFAULT)));
            return qp >= 10 && qp <= 40 ? qp : DEFAULT;
        } catch (RuntimeException e) {
            return DEFAULT;
        }
    }
}
