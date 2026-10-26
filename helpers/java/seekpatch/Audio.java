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

import java.nio.ByteBuffer;
import java.util.Arrays;

/**
 * seek-thermal-apk-patches video_quality: the sound of video recordings.
 *
 * <p>The app records mono 44.1 kHz from the camcorder microphone and encodes AAC-LC at 64 kbit/s.
 * {@link #minBufferSize} (called in place of {@code AudioRecord.getMinBufferSize}) picks 48 kHz
 * stereo, else 48 kHz mono, else the app's own format -- the first one the phone can open; the app's
 * {@code AudioRecord} is then created with {@link #rate} / {@link #channelMask}, and
 * {@link #configure} (in place of {@code MediaCodec.configure}) sets the AAC encoder to match, at
 * 256 kbit/s stereo or 160 kbit/s mono.
 *
 * <p>The sound's timestamps.  The app stamps each block it reads from the microphone with the time
 * the read <i>started</i>, and some AAC encoders (Android 7's software one) give each 1024-sample
 * frame the stamp of the block it starts in: with 20 ms blocks the frames come out 20 ms apart, and
 * every 15th 40 ms, where they are 21.3 ms long -- the sound stutters three times a second.  The
 * encoder also hands out its configuration (2 bytes) as a buffer, which the app writes into the
 * file as a sound frame.  {@link #queue} (in place of {@code queueInputBuffer}) stamps each block
 * with the time of its first sample, counted in samples from the first block, and starts the count
 * again where the microphone dropped samples; {@link #dequeue} (in place of
 * {@code dequeueOutputBuffer}) stamps each frame with the time of its first sample from that count,
 * and keeps the configuration out of the file.
 *
 * <p>The sound itself.  The app reads each block into a direct buffer and copies it to the encoder
 * from the buffer's backing array, from index 0 -- but Android keeps a direct buffer's bytes a few
 * bytes into that array (4 on a Redmi 4X): each block started with a silent sample and lost its last,
 * a click every block, 50 a second.  {@link #samples} (in place of that {@code array()}) gives the
 * block's bytes from its first.
 */
public final class Audio {
    private static final String TAG = "seek-thermal-apk-patches";
    private static final int STEREO_BITRATE = 256000;
    private static final int MONO_BITRATE = 160000;

    private static int rate = 44100;
    private static int mask = AudioFormat.CHANNEL_IN_MONO;
    private static int bufferBytes;  // the AudioRecord's buffer: 6x the minimum, as the app makes it

    // the sample clock of the recording in progress (its encoder): the microphone's thread queues,
    // the app's writer thread dequeues
    private static MediaCodec clockOf;
    private static long samples;     // queued so far
    private static long frames;      // AAC frames handed out so far
    private static long[] runStart = new long[8];  // first sample of each unbroken run ...
    private static long[] runTime = new long[8];   // ... and its time, µs (nanoTime clock)
    private static int runs;
    private static final int FRAME = 1024;  // samples in an AAC-LC frame
    private static byte[] block = new byte[0];  // the microphone's thread

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
                bufferBytes = n * 6;
                Log.i(TAG, "audio: " + rate + " Hz, " + channels() + " ch");
                return n;
            }
        }
        rate = stockRate;
        mask = stockMask;
        int n = AudioRecord.getMinBufferSize(stockRate, stockMask, encoding);
        bufferBytes = n * 6;
        Log.w(TAG, "audio: 48 kHz unavailable, recording the app's own " + rate + " Hz");
        return n;
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

    /** The microphone's thread, in place of the read buffer's array(): its bytes from the first one. */
    public static byte[] samples(ByteBuffer b) {
        int at = b.arrayOffset();
        if (at == 0) {
            return b.array();
        }
        if (block.length != b.capacity()) {
            block = new byte[b.capacity()];
        }
        System.arraycopy(b.array(), at, block, 0, b.capacity());
        return block;
    }

    /** The microphone's thread, in place of the encoder's queueInputBuffer: the block stamped by its samples. */
    public static void queue(MediaCodec codec, int index, int offset, int size, long stockUs, int flags) {
        long now = System.nanoTime() / 1000;
        long us;
        synchronized (Audio.class) {
            int frameBytes = 2 * channels();  // 16-bit PCM, as the app records
            long n = size / frameBytes;
            long duration = n * 1000000L / rate;
            if (clockOf != codec) {
                clockOf = codec;
                samples = 0;
                frames = 0;
                runs = 0;
            }
            long start = now - duration;  // the read returned with the block's last sample
            long kept = (long) (bufferBytes / frameBytes) * 1000000L / rate;
            if (runs == 0) {
                long lead = silence(codec, start, frameBytes);
                runStart[0] = 0;
                runTime[0] = start - lead * 1000000L / rate;
                runs = 1;
                samples = lead;
            } else if (start - timeOf(samples) > kept + 50000) {
                // a block ends at most a buffer (all the microphone keeps) before its read returns: a count
                // that puts it earlier means samples were dropped, and a new run starts with this block
                Log.w(TAG, "audio: the microphone dropped " + (start - timeOf(samples)) / 1000
                        + " ms; the sound goes on from now");
                if (runs == runStart.length) {
                    runStart = Arrays.copyOf(runStart, runs * 2);
                    runTime = Arrays.copyOf(runTime, runs * 2);
                }
                runStart[runs] = samples;
                runTime[runs] = start;
                runs++;
            }
            us = timeOf(samples);
            samples += n;
        }
        codec.queueInputBuffer(index, offset, size, us, flags);
    }

    /** The writer's thread, in place of the encoder's dequeueOutputBuffer: each frame stamped by its first sample. */
    public static int dequeue(MediaCodec codec, MediaCodec.BufferInfo info, long timeoutUs) {
        int index = codec.dequeueOutputBuffer(info, timeoutUs);
        if (index < 0) {
            return index;
        }
        if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) {
            codec.releaseOutputBuffer(index, false);  // the muxer has it from the output format
            return MediaCodec.INFO_TRY_AGAIN_LATER;
        }
        synchronized (Audio.class) {
            if (clockOf == codec && runs > 0) {
                info.presentationTimeUs = timeOf(frames * FRAME);
                if (info.size > 0) {
                    frames++;
                }
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                    clockOf = null;  // the recording's last frame: let go of its encoder
                }
            }
        }
        return index;
    }

    /**
     * A frame of silence queued before the first block, a frame earlier; returns its samples.  Android 7's
     * muxer stretches a track's first frame over the time before it (it writes no edit list): better a
     * silent frame than the first of the sound.  (The app's own first frame was the configuration.)
     */
    private static long silence(MediaCodec codec, long start, int frameBytes) {
        try {
            int index = codec.dequeueInputBuffer(10000);
            if (index < 0) {
                return 0;
            }
            ByteBuffer b = codec.getInputBuffer(index);
            int n = Math.min(FRAME, b.capacity() / frameBytes);
            b.clear();
            b.put(new byte[n * frameBytes]);
            codec.queueInputBuffer(index, 0, n * frameBytes, start - n * 1000000L / rate, 0);
            return n;
        } catch (RuntimeException e) {
            Log.w(TAG, "audio: no silent lead-in", e);
            return 0;
        }
    }

    /** The time of a sample, from the run it is in. */
    private static long timeOf(long sample) {
        int r = runs - 1;
        while (r > 0 && runStart[r] > sample) {
            r--;
        }
        return runTime[r] + (sample - runStart[r]) * 1000000L / rate;
    }
}
