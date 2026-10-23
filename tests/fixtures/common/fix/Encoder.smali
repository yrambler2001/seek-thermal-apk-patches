.class public Lfix/Encoder;
.super Ljava/lang/Object;
.source "Encoder.java"


# static fields
.field public static j:Z


# virtual methods
# a frame for the video (video_quality feeds it per thermal frame)
.method public e(Landroid/graphics/SurfaceTexture;)V
    .locals 2

    const-string v0, "ThermalVideoEncoder"

    const-string v1, "frame"

    invoke-static {v0, v1}, Landroid/util/Log;->v(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method
