.class public Lfix/Render;
.super Landroid/os/HandlerThread;
.source "Render.java"


# instance fields
.field camera:Landroid/graphics/SurfaceTexture;

.field thermalTexture:I


# direct methods
.method public constructor <init>()V
    .locals 1

    const-string v0, "ThermalPlusRenderThread"

    invoke-direct {p0, v0}, Landroid/os/HandlerThread;-><init>(Ljava/lang/String;)V

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

.method private declared-synchronized w()V
    .locals 0

    monitor-enter p0

    monitor-exit p0

    return-void
.end method
