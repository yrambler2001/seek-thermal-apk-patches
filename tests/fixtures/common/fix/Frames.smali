.class public Lfix/Frames;
.super Ljava/lang/Object;
.source "SourceFile"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field private final finished:Ljava/util/ArrayList;

.field private final free:Ljava/util/ArrayList;


# direct methods
# the camera library's frame loop (steady_fps): queues each frame request, waits for each USB chunk,
# hands finished frames to the processing thread and takes their buffers back
.method public constructor <init>()V
    .locals 1

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    new-instance v0, Ljava/util/ArrayList;

    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V

    iput-object v0, p0, Lfix/Frames;->finished:Ljava/util/ArrayList;

    new-instance v0, Ljava/util/ArrayList;

    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V

    iput-object v0, p0, Lfix/Frames;->free:Ljava/util/ArrayList;

    return-void
.end method

.method private m(Landroid/hardware/usb/UsbDeviceConnection;)Z
    .locals 1

    invoke-virtual {p1}, Landroid/hardware/usb/UsbDeviceConnection;->requestWait()Landroid/hardware/usb/UsbRequest;

    move-result-object v0

    if-nez v0, :cond_0

    const/4 v0, 0x0

    return v0

    :cond_0
    const/4 v0, 0x1

    return v0
.end method

# a frame is complete: state 1, onto the finished list
.method private n(Lfix/Frame;)V
    .locals 2

    iget-object v0, p0, Lfix/Frames;->finished:Ljava/util/ArrayList;

    monitor-enter v0

    const/4 v1, 0x1

    :try_start_0
    invoke-virtual {p1, v1}, Lfix/Frame;->l(I)V

    iget-object v1, p0, Lfix/Frames;->finished:Ljava/util/ArrayList;

    invoke-virtual {v1, p1}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z

    iget-object p1, p0, Lfix/Frames;->finished:Ljava/util/ArrayList;

    invoke-virtual {p1}, Ljava/lang/Object;->notify()V

    monitor-exit v0

    return-void

    :catchall_0
    move-exception p1

    monitor-exit v0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    throw p1
.end method

# a buffer comes back: cleared, onto the free list, state 0
.method private o(Lfix/Frame;)V
    .locals 2

    iget-object v0, p0, Lfix/Frames;->free:Ljava/util/ArrayList;

    monitor-enter v0

    :try_start_0
    invoke-virtual {p1}, Lfix/Frame;->a()V

    iget-object v1, p0, Lfix/Frames;->free:Ljava/util/ArrayList;

    invoke-virtual {v1, p1}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z

    const/4 v1, 0x0

    invoke-virtual {p1, v1}, Lfix/Frame;->l(I)V

    iget-object p1, p0, Lfix/Frames;->free:Ljava/util/ArrayList;

    invoke-virtual {p1}, Ljava/lang/Object;->notify()V

    monitor-exit v0

    return-void

    :catchall_0
    move-exception p1

    monitor-exit v0
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    throw p1
.end method


# virtual methods
.method public run()V
    .locals 0

    :goto_0
    invoke-static {}, Ljava/lang/Thread;->yield()V

    goto :goto_0
.end method
