.class public Lfix/Render;
.super Landroid/os/HandlerThread;
.source "Render.java"


# instance fields
.field protected b:Lfix/Encoder;

.field camera:Landroid/graphics/SurfaceTexture;

.field protected g:Lfix/Window;

.field protected j:Lfix/PhoneCam;

.field thermalTexture:I


# direct methods
# the phone camera is opened with the thread (phone_camera)
.method public constructor <init>(Landroid/content/Context;)V
    .locals 1

    const-string v0, "ThermalPlusRenderThread"

    invoke-direct {p0, v0}, Landroid/os/HandlerThread;-><init>(Ljava/lang/String;)V

    new-instance v0, Lfix/PhoneCam;

    invoke-direct {v0}, Lfix/PhoneCam;-><init>()V

    iput-object v0, p0, Lfix/Render;->j:Lfix/PhoneCam;

    invoke-virtual {v0, p1}, Lfix/PhoneCam;->s(Landroid/content/Context;)V

    return-void
.end method

.method static synthetic b(Lfix/Render;)V
    .locals 0

    invoke-direct {p0}, Lfix/Render;->w()V

    return-void
.end method

.method static synthetic d(Lfix/Render;Ljava/nio/ByteBuffer;II)V
    .locals 0

    invoke-direct {p0, p1, p2, p3}, Lfix/Render;->h(Ljava/nio/ByteBuffer;II)V

    return-void
.end method

.method private declared-synchronized h(Ljava/nio/ByteBuffer;II)V
    .locals 11

    monitor-enter p0

    iget v0, p0, Lfix/Render;->thermalTexture:I

    const/16 v1, 0xde1

    invoke-static {v1, v0}, Landroid/opengl/GLES20;->glBindTexture(II)V

    const/16 v8, 0x1908

    const/16 v9, 0x1401

    const/16 v2, 0xde1

    const/4 v3, 0x0

    const/16 v4, 0x1908

    const/4 v7, 0x0

    move v5, p2

    move v6, p3

    move-object v10, p1

    invoke-static/range {v2 .. v10}, Landroid/opengl/GLES20;->glTexImage2D(IIIIIIIILjava/nio/Buffer;)V

    const/4 p1, 0x0

    invoke-static {v1, p1}, Landroid/opengl/GLES20;->glBindTexture(II)V

    monitor-exit p0

    return-void
.end method

# the draw: presented now (steady_fps paces it)
.method private declared-synchronized w()V
    .locals 3

    monitor-enter p0

    iget-object v0, p0, Lfix/Render;->g:Lfix/Window;

    .line 30
    invoke-static {}, Ljava/lang/System;->nanoTime()J

    move-result-wide v1

    invoke-virtual {v0, v1, v2}, Lfix/Window;->f(J)V

    monitor-exit p0

    return-void
.end method

# the live view's window (resume_fix): created on start, dropped on pause
.method o(Landroid/view/Surface;)V
    .locals 3

    new-instance v0, Lfix/Core;

    invoke-direct {v0}, Lfix/Core;-><init>()V

    new-instance v1, Lfix/Window;

    const/4 v2, 0x1

    invoke-direct {v1, v0, p1, v2}, Lfix/Window;-><init>(Lfix/Core;Landroid/view/Surface;Z)V

    iput-object v1, p0, Lfix/Render;->g:Lfix/Window;

    iget-object v0, p0, Lfix/Render;->j:Lfix/PhoneCam;

    iget-object v1, p0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v0, v1}, Lfix/PhoneCam;->g(Landroid/graphics/SurfaceTexture;)V

    return-void
.end method

# stop: the phone camera too (phone_camera)
.method public declared-synchronized P()V
    .locals 1

    monitor-enter p0

    iget-object v0, p0, Lfix/Render;->j:Lfix/PhoneCam;

    invoke-virtual {v0}, Lfix/PhoneCam;->v()V

    monitor-exit p0

    return-void
.end method

# the front / back camera switch (phone_camera)
.method public declared-synchronized Q()V
    .locals 2

    monitor-enter p0

    iget-object v0, p0, Lfix/Render;->j:Lfix/PhoneCam;

    iget-object v1, p0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v0, v1}, Lfix/PhoneCam;->x(Landroid/graphics/SurfaceTexture;)V

    monitor-exit p0

    return-void
.end method

.method private synthetic v()V
    .locals 1

    const/4 v0, 0x0

    iput-object v0, p0, Lfix/Render;->g:Lfix/Window;

    return-void
.end method
