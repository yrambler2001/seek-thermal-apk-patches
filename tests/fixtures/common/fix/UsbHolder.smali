.class public Lfix/UsbHolder;
.super Ljava/lang/Object;
.source "SourceFile"


# instance fields
.field private b:Landroid/hardware/usb/UsbDeviceConnection;

.field private f:Landroid/hardware/usb/UsbInterface;


# direct methods
# a camera's USB connection and interface (reconnect_fix)
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public c()Landroid/hardware/usb/UsbDeviceConnection;
    .locals 1

    iget-object v0, p0, Lfix/UsbHolder;->b:Landroid/hardware/usb/UsbDeviceConnection;

    return-object v0
.end method

.method public f()Landroid/hardware/usb/UsbInterface;
    .locals 1

    iget-object v0, p0, Lfix/UsbHolder;->f:Landroid/hardware/usb/UsbInterface;

    return-object v0
.end method
