package seekpatch;

import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbRequest;
import java.nio.ByteBuffer;

/**
 * seek-patch usb_queue: read the camera's frames without gaps between them.
 *
 * <p>The camera library asks for a frame with a frame request (control transfer 0x53, the frame's
 * length in half-words) and reads it as chunks: 4 on the Compact, 13 on the CompactPRO.  It queues
 * one chunk's USB request at a time, the next only after the previous one arrived.  After the last
 * chunk its USB thread wakes the library's frame loop, which posts the next frame request back to
 * it.  The camera starts sending a frame only while a request is waiting, and only during about
 * the first quarter of a sensor frame; a later request waits for the next sensor frame, which is a
 * 62 ms gap at 32 fps.
 *
 * <p>The patch keeps the library's code and replaces or follows three of its calls:
 * <ul>
 * <li>{@link #queue}: the first chunk's request also queues every other chunk of the frame, in
 *     order, so the phone always has a request waiting for the camera's data;
 * <li>{@link #arrived}: when the frame's last chunk is in, the next frame request goes out at once
 *     from the same thread, before the library looks at the chunk;
 * <li>{@link #frameRequest}: the library's own frame request is skipped when that request is out.
 * </ul>
 * All three run on the library's USB thread.  The camera clears waiting requests when streaming
 * stops, and the library stops it on that same thread, between frames.
 */
public final class UsbQueue {
    /** The library's frame buffer (the patch adds this to it). */
    public interface Frame {
        /** One array per chunk, each the chunk size long. */
        byte[][] seekpatchChunks();
    }

    /** The library's results for its frame request: 0 is success. */
    private static final int OK = 0;
    private static final int NO_DATA = 0x20000001;
    private static final int FAILED = 0x20000005;
    private static final int NO_DEVICE = 0x20000003;

    /** One imaging session: the library makes a new frame-request runnable for each. */
    private static final class Stream {
        final Object owner;
        final Object lock;
        final UsbDeviceConnection connection;
        int halfWords;
        /** The next frame is already requested. */
        boolean requested;
        /**
         * The frame being read: its chunk requests, how many of them are queued here (the library
         * must not queue those again), how many arrived in order (-1: not in order).
         */
        UsbRequest[] chunks;
        int queued;
        int arrived;

        Stream(Object owner, Object lock, UsbDeviceConnection connection) {
            this.owner = owner;
            this.lock = lock;
            this.connection = connection;
        }
    }

    private static volatile Stream stream;

    private UsbQueue() {
    }

    /**
     * Replaces the library's frame request.  lock is the library's command object (its transfers
     * synchronize on it), owner the runnable that reads the frames.
     */
    public static int frameRequest(Object lock, UsbDeviceConnection connection, int halfWords, Object owner) {
        Stream s = stream;
        if (s == null || s.owner != owner || s.connection != connection) {
            s = new Stream(owner, lock, connection);
            stream = s;
        }
        s.chunks = null;
        boolean requested = s.requested && s.halfWords == halfWords;
        s.requested = false;
        s.halfWords = halfWords;
        return requested ? OK : request(lock, connection, halfWords);
    }

    /** The library's frame request, as it sends it. */
    private static int request(Object lock, UsbDeviceConnection connection, int halfWords) {
        if (connection == null) {
            return NO_DEVICE;
        }
        byte[] length = {(byte) halfWords, (byte) (halfWords >> 8), (byte) (halfWords >> 16), (byte) (halfWords >> 24)};
        int n;
        synchronized (lock) {
            n = connection.controlTransfer(0x41, 0x53, 0, 0, length, 4, 1000);
        }
        return n == 0 ? NO_DATA : n < 0 ? FAILED : OK;
    }

    /**
     * Replaces UsbRequest.queue(buffer, length) in the library's frame read.  requests holds the
     * frame's chunk requests in order, frame is its frame buffer.
     */
    public static boolean queue(UsbRequest request, ByteBuffer buffer, int length, UsbRequest[] requests, Object frame) {
        Stream s = stream;
        if (s != null && s.halfWords > 0 && requests != null && requests.length > 1 && request == requests[0]
                && frame instanceof Frame) {
            return queueFrame(s, buffer, length, requests, ((Frame) frame).seekpatchChunks());
        }
        if (s != null && requests != null && requests == s.chunks) {
            for (int i = 1; i < s.queued; i++) {
                if (requests[i] == request) {
                    return true;
                }
            }
        }
        return request.queue(buffer, length);
    }

    /** Queue the first chunk as the library asked, then the others: same size, the last one what is left. */
    private static boolean queueFrame(Stream s, ByteBuffer first, int length, UsbRequest[] requests, byte[][] chunks) {
        s.chunks = requests;
        s.queued = 0;
        s.arrived = 0;
        if (!requests[0].queue(first, length)) {
            return false;
        }
        s.queued = 1;
        int n = requests.length;
        int last = 2 * s.halfWords - length * (n - 1);
        if (chunks == null || chunks.length != n) {
            return true;
        }
        for (int i = 1; i < n; i++) {
            int size = i < n - 1 ? length : last;
            if (size <= 0 || size > chunks[i].length || !requests[i].queue(ByteBuffer.wrap(chunks[i]), size)) {
                break;
            }
            s.queued++;
        }
        return true;
    }

    /**
     * Follows the library's requestWait(): request is what it returned.  Only a frame whose chunks
     * all came back in order asks for the next one; any other frame leaves it to the library.
     */
    public static void arrived(UsbRequest request) {
        Stream s = stream;
        if (s == null || s.chunks == null || s.arrived < 0) {
            return;
        }
        UsbRequest[] chunks = s.chunks;
        if (request == null || s.queued != chunks.length || s.arrived >= chunks.length || request != chunks[s.arrived]) {
            s.arrived = -1;
            return;
        }
        if (++s.arrived == chunks.length) {
            s.requested = request(s.lock, s.connection, s.halfWords) == OK;
        }
    }
}
