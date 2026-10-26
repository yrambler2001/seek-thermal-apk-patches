.class public Lfix/UsbLink;
.super Ljava/lang/Object;
.source "SourceFile"


# direct methods
# the library's USB wrapper (reconnect_fix, relaunch_fix): opens a camera, and closes one -- interface released, connection closed
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public a(Lfix/UsbHolder;)I
    .locals 2

    invoke-virtual {p1}, Lfix/UsbHolder;->c()Landroid/hardware/usb/UsbDeviceConnection;

    move-result-object v0

    invoke-virtual {p1}, Lfix/UsbHolder;->f()Landroid/hardware/usb/UsbInterface;

    move-result-object v1

    if-eqz v1, :cond_0

    if-eqz v0, :cond_0

    invoke-virtual {v0, v1}, Landroid/hardware/usb/UsbDeviceConnection;->releaseInterface(Landroid/hardware/usb/UsbInterface;)Z

    invoke-virtual {v0}, Landroid/hardware/usb/UsbDeviceConnection;->close()V

    :cond_0
    const/4 v0, 0x0

    return v0
.end method

# opens a camera: its interface claimed, forced (relaunch_fix)
.method public c(Lfix/UsbHolder;)I
    .locals 5

    invoke-virtual {p1}, Lfix/UsbHolder;->c()Landroid/hardware/usb/UsbDeviceConnection;

    move-result-object v1

    invoke-virtual {p1}, Lfix/UsbHolder;->f()Landroid/hardware/usb/UsbInterface;

    move-result-object v2

    const/4 v4, 0x1

    invoke-virtual {v1, v2, v4}, Landroid/hardware/usb/UsbDeviceConnection;->claimInterface(Landroid/hardware/usb/UsbInterface;Z)Z

    move-result v4

    if-eqz v4, :cond_0

    const/4 v0, 0x0

    return v0

    :cond_0
    const-string v3, "UsbInit"

    const-string v4, "claim interface failed"

    invoke-static {v3, v4}, Lfix/Log;->b(Ljava/lang/String;Ljava/lang/String;)V

    const v0, 0x2000000a

    return v0
.end method
