package seekpatch;

import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbInterface;
import android.util.Log;

/**
 * seek-patch relaunch_fix: the camera's packet numbering starts over each time the app takes it.
 *
 * <p>USB marks the packets of a bulk endpoint DATA0, DATA1, DATA0, ... (the data toggle), so that
 * the receiver can tell a repeated packet from a new one.  When the app's process dies while the
 * camera streams -- swiped away, force-stopped -- the phone and the camera can be left one step
 * apart.  At the next start the phone then takes the camera's first packet for a repeat and drops
 * it: the first 512 bytes of the first frame, with its header.  That frame (type 4) is the one the
 * camera library needs to start its thermography; without it every pixel reads -40 °C (magenta in
 * most palettes) until the camera is unplugged.  {@link #claimInterface} (in place of
 * UsbDeviceConnection.claimInterface) sets the interface again once it is claimed: Linux resets the
 * phone's toggles and sends SET_INTERFACE, which resets the camera's -- or, for a camera that
 * refuses it, CLEAR_FEATURE(ENDPOINT_HALT) on each endpoint, which resets them too.
 */
public final class Relaunch {
    private static final String TAG = "seek-patch";

    private Relaunch() {
    }

    public static boolean claimInterface(UsbDeviceConnection connection, UsbInterface intf, boolean force) {
        if (!connection.claimInterface(intf, force)) {
            return false;
        }
        boolean set = connection.setInterface(intf);
        Log.i(TAG, "relaunch_fix: interface " + intf.getId()
                + (set ? " set again, packet numbering starts over" : ": setInterface failed"));
        return true;
    }
}
