.class public Lfix/Usb;
.super Ljava/lang/Object;
.source "SourceFile"


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public mode(Landroid/hardware/usb/UsbDeviceConnection;[B)I
    .locals 8

    const/16 v1, 0x41

    const/16 v2, 0x3c

    const/4 v3, 0x0

    const/4 v4, 0x0

    const/4 v6, 0x2

    const/16 v7, 0x3e8

    move-object v0, p1

    move-object v5, p2

    invoke-virtual/range {v0 .. v7}, Landroid/hardware/usb/UsbDeviceConnection;->controlTransfer(IIII[BII)I

    move-result v0

    return v0
.end method

.method public request(Landroid/hardware/usb/UsbDeviceConnection;I)I
    .locals 9

    .line 1
    const/4 v0, 0x4

    new-array v6, v0, [B

    int-to-byte v1, p2

    const/4 v2, 0x0

    aput-byte v1, v6, v2

    monitor-enter p0

    const/16 v2, 0x41

    const/16 v3, 0x53

    const/4 v4, 0x0

    const/4 v5, 0x0

    const/4 v7, 0x4

    const/16 v8, 0x3e8

    move-object v1, p1

    invoke-virtual/range {v1 .. v8}, Landroid/hardware/usb/UsbDeviceConnection;->controlTransfer(IIII[BII)I

    move-result v0

    monitor-exit p0

    return v0
.end method
