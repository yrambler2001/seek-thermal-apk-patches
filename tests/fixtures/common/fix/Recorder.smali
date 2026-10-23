.class public Lfix/Recorder;
.super Ljava/lang/Object;
.source "Recorder.java"


# instance fields
.field private c:Landroid/view/Surface;

.field private e:Landroid/media/MediaCodec;


# direct methods
# the video recorder (video_quality): H.264, its size, a fixed bitrate
.method public constructor <init>(III)V
    .locals 3

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    const-string v0, "video/avc"

    invoke-static {v0, p1, p2}, Landroid/media/MediaFormat;->createVideoFormat(Ljava/lang/String;II)Landroid/media/MediaFormat;

    move-result-object p1

    const-string p2, "bitrate"

    invoke-virtual {p1, p2, p3}, Landroid/media/MediaFormat;->setInteger(Ljava/lang/String;I)V

    .line 4
    invoke-static {v0}, Landroid/media/MediaCodec;->createEncoderByType(Ljava/lang/String;)Landroid/media/MediaCodec;

    move-result-object p2

    iput-object p2, p0, Lfix/Recorder;->e:Landroid/media/MediaCodec;

    const/4 p3, 0x0

    const/4 v1, 0x1

    invoke-virtual {p2, p1, p3, p3, v1}, Landroid/media/MediaCodec;->configure(Landroid/media/MediaFormat;Landroid/view/Surface;Landroid/media/MediaCrypto;I)V

    invoke-virtual {p2}, Landroid/media/MediaCodec;->createInputSurface()Landroid/view/Surface;

    move-result-object p1

    iput-object p1, p0, Lfix/Recorder;->c:Landroid/view/Surface;

    invoke-virtual {p2}, Landroid/media/MediaCodec;->start()V

    return-void
.end method
