.class public Lfix/PhoneCam;
.super Landroid/os/HandlerThread;
.source "SourceFile"


# instance fields
.field private b:Landroid/os/Handler;


# direct methods
# the phone camera's handler (phone_camera): opens the camera, starts and switches its preview,
# stops it -- each posted to its own thread
.method public constructor <init>()V
    .locals 1

    const-string v0, "VisibleCameraHandlerThread"

    invoke-direct {p0, v0}, Landroid/os/HandlerThread;-><init>(Ljava/lang/String;)V

    return-void
.end method


# virtual methods
.method public g(Landroid/graphics/SurfaceTexture;)V
    .locals 1

    iget-object v0, p0, Lfix/PhoneCam;->b:Landroid/os/Handler;

    invoke-virtual {v0, p1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    return-void
.end method

.method public declared-synchronized i()V
    .locals 0

    monitor-enter p0

    monitor-exit p0

    return-void
.end method

.method public s(Landroid/content/Context;)V
    .locals 1

    iget-object v0, p0, Lfix/PhoneCam;->b:Landroid/os/Handler;

    invoke-virtual {v0, p1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    invoke-virtual {p0}, Ljava/lang/Object;->wait()V

    return-void
.end method

.method public declared-synchronized v()V
    .locals 1

    monitor-enter p0

    iget-object v0, p0, Lfix/PhoneCam;->b:Landroid/os/Handler;

    invoke-virtual {v0, p0}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    invoke-virtual {p0}, Ljava/lang/Object;->wait()V

    monitor-exit p0

    return-void
.end method

.method public x(Landroid/graphics/SurfaceTexture;)V
    .locals 1

    iget-object v0, p0, Lfix/PhoneCam;->b:Landroid/os/Handler;

    invoke-virtual {v0, p1}, Landroid/os/Handler;->post(Ljava/lang/Runnable;)Z

    return-void
.end method
