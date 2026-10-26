.class public Lfix/Devices;
.super Ljava/lang/Object;
.source "SourceFile"


# static fields
.field private static c:Lfix/CameraDevice;


# direct methods
# the DeviceManager (reconnect_fix): has it a camera?
.method public static declared-synchronized g()Z
    .locals 2

    const-class v0, Lfix/Devices;

    monitor-enter v0

    :try_start_0
    sget-object v1, Lfix/Devices;->c:Lfix/CameraDevice;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    if-eqz v1, :cond_0

    const/4 v1, 0x1

    goto :goto_0

    :cond_0
    const/4 v1, 0x0

    :goto_0
    monitor-exit v0

    return v1

    :catchall_0
    move-exception v1

    monitor-exit v0

    throw v1
.end method
