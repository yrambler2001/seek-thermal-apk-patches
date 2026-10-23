package seekpatch;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaCodec;
import android.media.MediaCodecInfo.CodecProfileLevel;
import android.media.MediaCrypto;
import android.media.MediaFormat;
import android.media.MediaRecorder;
import android.util.Log;
import android.view.Surface;

/**
 * seek-patch video_quality: the sound of video recordings.
 *
 * <p>The app records mono 44.1 kHz from the camcorder microphone and encodes AAC-LC at 64 kbit/s.
 * {@link #minBufferSize} (called in place of {@code AudioRecord.getMinBufferSize}) picks 48 kHz
 * stereo, else 48 kHz mono, else the app's own format -- the first one the phone can open; the app's
 * {@code AudioRecord} is then created with {@link #rate} / {@link #channelMask}, and
 * {@link #configure} (in place of {@code MediaCodec.configure}) sets the AAC encoder to match, at
 * 256 kbit/s stereo or 160 kbit/s mono.
 */
public final class Audio {
    private static final String TAG = "seek-patch";
    private static final int STEREO_BITRATE = 256000;
    private static final int MONO_BITRATE = 160000;

    private static int rate = 44100;
    private static int mask = AudioFormat.CHANNEL_IN_MONO;

    private Audio() {
    }

    public static synchronized int minBufferSize(int stockRate, int stockMask, int encoding) {
        int[][] formats = {
            {48000, AudioFormat.CHANNEL_IN_STEREO},
            {48000, AudioFormat.CHANNEL_IN_MONO},
        };
        for (int[] f : formats) {
            int n = AudioRecord.getMinBufferSize(f[0], f[1], encoding);
            if (n > 0 && opens(f[0], f[1], encoding, n * 6)) {  // the app records with 6x the minimum
                rate = f[0];
                mask = f[1];
                Log.i(TAG, "audio: " + rate + " Hz, " + channels() + " ch");
                return n;
            }
        }
        rate = stockRate;
        mask = stockMask;
        Log.w(TAG, "audio: 48 kHz unavailable, recording the app's own " + rate + " Hz");
        return AudioRecord.getMinBufferSize(stockRate, stockMask, encoding);
    }

    private static boolean opens(int rate, int mask, int encoding, int size) {
        AudioRecord probe = null;
        try {
            probe = new AudioRecord(MediaRecorder.AudioSource.CAMCORDER, rate, mask, encoding, size);
            return probe.getState() == AudioRecord.STATE_INITIALIZED;
        } catch (RuntimeException e) {
            return false;
        } finally {
            if (probe != null) {
                probe.release();
            }
        }
    }

    public static synchronized int rate() {
        return rate;
    }

    public static synchronized int channelMask() {
        return mask;
    }

    private static int channels() {
        return mask == AudioFormat.CHANNEL_IN_STEREO ? 2 : 1;
    }

    public static void configure(MediaCodec codec, MediaFormat format, Surface surface, MediaCrypto crypto, int flags) {
        int channels;
        synchronized (Audio.class) {
            format.setInteger(MediaFormat.KEY_SAMPLE_RATE, rate);
            channels = channels();
        }
        format.setInteger(MediaFormat.KEY_CHANNEL_COUNT, channels);
        format.setInteger(MediaFormat.KEY_AAC_PROFILE, CodecProfileLevel.AACObjectLC);
        format.setInteger(MediaFormat.KEY_BIT_RATE, channels == 2 ? STEREO_BITRATE : MONO_BITRATE);
        codec.configure(format, surface, crypto, flags);
        Log.i(TAG, "audio: " + format);
    }
}
