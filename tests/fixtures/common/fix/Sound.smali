.class public Lfix/Sound;
.super Ljava/lang/Object;
.source "Sound.java"


# instance fields
.field private a:Landroid/media/MediaCodec;

.field private c:Landroid/media/AudioRecord;

.field private d:I


# direct methods
# the microphone + AAC encoder (video_quality): mono 44.1 kHz, 64 kbit/s
.method public constructor <init>()V
    .locals 8

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    const v0, 0xac44

    const/16 v1, 0x10

    const/4 v2, 0x2

    invoke-static {v0, v1, v2}, Landroid/media/AudioRecord;->getMinBufferSize(III)I

    move-result v1

    mul-int/lit8 v1, v1, 0x6

    iput v1, p0, Lfix/Sound;->d:I

    new-instance v1, Landroid/media/AudioRecord;

    const/4 v6, 0x2

    iget v7, p0, Lfix/Sound;->d:I

    const/4 v3, 0x5

    const v4, 0xac44

    const/16 v5, 0x10

    move-object v2, v1

    invoke-direct/range {v2 .. v7}, Landroid/media/AudioRecord;-><init>(IIIII)V

    iput-object v1, p0, Lfix/Sound;->c:Landroid/media/AudioRecord;

    const-string v1, "audio/mp4a-latm"

    const/4 v2, 0x1

    invoke-static {v1, v0, v2}, Landroid/media/MediaFormat;->createAudioFormat(Ljava/lang/String;II)Landroid/media/MediaFormat;

    move-result-object v0

    invoke-static {v1}, Landroid/media/MediaCodec;->createEncoderByType(Ljava/lang/String;)Landroid/media/MediaCodec;

    move-result-object v1

    iput-object v1, p0, Lfix/Sound;->a:Landroid/media/MediaCodec;

    const/4 v3, 0x0

    invoke-virtual {v1, v0, v3, v3, v2}, Landroid/media/MediaCodec;->configure(Landroid/media/MediaFormat;Landroid/view/Surface;Landroid/media/MediaCrypto;I)V

    return-void
.end method
