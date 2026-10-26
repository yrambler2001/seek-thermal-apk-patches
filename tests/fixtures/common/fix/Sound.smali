.class public Lfix/Sound;
.super Ljava/lang/Object;
.source "Sound.java"


# instance fields
.field private a:Landroid/media/MediaCodec;

.field private b:Landroid/media/MediaCodec$BufferInfo;

.field private c:Landroid/media/AudioRecord;

.field private d:I

.field private e:Ljava/nio/ByteBuffer;


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

# the end of the recording: an empty block flagged end of stream (no microphone read)
.method private f(J)V
    .locals 8

    iget-object v1, p0, Lfix/Sound;->a:Landroid/media/MediaCodec;

    const/4 v2, 0x0

    move v3, v2

    move v4, v2

    move-wide v5, p1

    const/4 v7, 0x4

    invoke-virtual/range {v1 .. v7}, Landroid/media/MediaCodec;->queueInputBuffer(IIIJI)V

    return-void
.end method


# virtual methods
# the writer's thread: the next AAC frame
.method a()Z
    .locals 4

    iget-object v0, p0, Lfix/Sound;->a:Landroid/media/MediaCodec;

    iget-object v1, p0, Lfix/Sound;->b:Landroid/media/MediaCodec$BufferInfo;

    const-wide/16 v2, 0x2710

    invoke-virtual {v0, v1, v2, v3}, Landroid/media/MediaCodec;->dequeueOutputBuffer(Landroid/media/MediaCodec$BufferInfo;J)I

    move-result v0

    if-ltz v0, :cond_0

    const/4 v0, 0x1

    return v0

    :cond_0
    const/4 v0, 0x0

    return v0
.end method

# the microphone's thread: a block read into the encoder, stamped with the time its read started
.method g(J)V
    .locals 9

    iget-object v2, p0, Lfix/Sound;->a:Landroid/media/MediaCodec;

    iget-object v0, p0, Lfix/Sound;->c:Landroid/media/AudioRecord;

    iget-object v1, p0, Lfix/Sound;->e:Ljava/nio/ByteBuffer;

    const/16 v3, 0x400

    invoke-virtual {v0, v1, v3}, Landroid/media/AudioRecord;->read(Ljava/nio/ByteBuffer;I)I

    move-result v5

    invoke-virtual {v2}, Landroid/media/MediaCodec;->getInputBuffers()[Ljava/nio/ByteBuffer;

    move-result-object v0

    const/4 v3, 0x0

    aget-object v0, v0, v3

    invoke-virtual {v1}, Ljava/nio/ByteBuffer;->array()[B

    move-result-object v1

    invoke-virtual {v0, v1, v3, v5}, Ljava/nio/ByteBuffer;->put([BII)Ljava/nio/ByteBuffer;

    move v4, v3

    invoke-static {}, Ljava/lang/System;->nanoTime()J

    move-result-wide v6

    const/4 v8, 0x0

    invoke-virtual/range {v2 .. v8}, Landroid/media/MediaCodec;->queueInputBuffer(IIIJI)V

    return-void
.end method
