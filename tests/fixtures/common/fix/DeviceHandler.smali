.class public Lfix/DeviceHandler;
.super Landroid/os/HandlerThread;
.source "SourceFile"


# direct methods
# the camera library's USB thread (steady_fps): a HandlerThread, so its start resets setPriority(10)
.method public constructor <init>()V
    .locals 1

    const-string v0, "SeekwareDeviceHandler"

    invoke-direct {p0, v0}, Landroid/os/HandlerThread;-><init>(Ljava/lang/String;)V

    const/16 v0, 0xa

    invoke-virtual {p0, v0}, Ljava/lang/Thread;->setPriority(I)V

    return-void
.end method
