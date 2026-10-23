import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo.CodecCapabilities;
import android.media.MediaCodecInfo.CodecProfileLevel;
import android.media.MediaFormat;
import android.media.MediaMuxer;

import java.io.FileInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * Run with app_process (tools/codecs.py ladder): encode raw yuv420p frames with one encoder at a
 * constant QP, set up the way seekpatch.Video does (QP bounds, keyframe every second), into an MP4.
 *
 *   Ladder IN.yuv WIDTH HEIGHT FRAMES FPS CODEC MIME QP OUT.mp4
 */
public class Ladder {
    public static void main(String[] a) throws IOException {
        String in = a[0], codecName = a[5], mime = a[6], out = a[8];
        int w = Integer.parseInt(a[1]), h = Integer.parseInt(a[2]), frames = Integer.parseInt(a[3]);
        double fps = Double.parseDouble(a[4]);
        int qp = Integer.parseInt(a[7]);
        MediaFormat f = MediaFormat.createVideoFormat(mime, w, h);
        f.setInteger(MediaFormat.KEY_COLOR_FORMAT, CodecCapabilities.COLOR_FormatYUV420Flexible);
        f.setInteger(MediaFormat.KEY_FRAME_RATE, 30);
        f.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
        f.setInteger(MediaFormat.KEY_BIT_RATE, 40000000);
        f.setInteger(MediaFormat.KEY_BITRATE_MODE, 1);  // VBR
        f.setInteger(MediaFormat.KEY_PROFILE, mime.equals(MediaFormat.MIMETYPE_VIDEO_HEVC)
                ? CodecProfileLevel.HEVCProfileMain : CodecProfileLevel.AVCProfileHigh);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_MIN, qp - 2);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_MAX, qp + 2);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_I_MIN, qp - 2);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_I_MAX, qp - 2);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_P_MIN, qp);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_P_MAX, qp);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_B_MIN, qp + 2);
        f.setInteger(MediaFormat.KEY_VIDEO_QP_B_MAX, qp + 2);
        MediaCodec codec = MediaCodec.createByCodecName(codecName);
        codec.configure(f, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        codec.start();
        MediaMuxer mux = new MediaMuxer(out, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        byte[] frame = new byte[w * h * 3 / 2];
        int track = -1, sent = 0;
        try (FileInputStream yuv = new FileInputStream(in)) {
            boolean done = false;
            while (!done) {
                if (sent <= frames) {
                    int ib = codec.dequeueInputBuffer(10000);
                    if (ib >= 0) {
                        long pts = (long) (sent * 1e6 / fps);
                        if (sent == frames) {
                            codec.queueInputBuffer(ib, 0, 0, pts, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                        } else {
                            for (int n = 0; n < frame.length; ) n += yuv.read(frame, n, frame.length - n);
                            copy(codec.getInputImage(ib), frame, w, h);
                            codec.queueInputBuffer(ib, 0, frame.length, pts, 0);
                        }
                        sent++;
                    }
                }
                int ob = codec.dequeueOutputBuffer(info, 10000);
                if (ob == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    track = mux.addTrack(codec.getOutputFormat());
                    mux.start();
                } else if (ob >= 0) {
                    if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0 && info.size > 0) {
                        mux.writeSampleData(track, codec.getOutputBuffer(ob), info);
                    }
                    done = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    codec.releaseOutputBuffer(ob, false);
                }
            }
        }
        mux.stop();
        mux.release();
        codec.stop();
        codec.release();
        System.out.println("ok " + out);
    }

    /** yuv420p into the encoder's image, whatever its strides (NV12 on most hardware). */
    static void copy(Image img, byte[] f, int w, int h) {
        Image.Plane[] planes = img.getPlanes();
        int[] offset = {0, w * h, w * h + w * h / 4};
        for (int k = 0; k < 3; k++) {
            int pw = k == 0 ? w : w / 2, ph = k == 0 ? h : h / 2;
            ByteBuffer b = planes[k].getBuffer();
            int rs = planes[k].getRowStride(), ps = planes[k].getPixelStride();
            for (int y = 0; y < ph; y++) {
                for (int x = 0; x < pw; x++) {
                    b.put(y * rs + x * ps, f[offset[k] + y * pw + x]);
                }
            }
        }
    }
}
