.class public Lfix/Meter;
.super Ljava/lang/Object;
.source "SourceFile"


# instance fields
.field frames:I

.field last:J

.field rate:D


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
# each frame: the frame rate, frames / seconds, once 3 s have passed (fps_readout)
.method public frame()V
    .locals 8

    .line 1
    iget v0, p0, Lfix/Meter;->frames:I

    add-int/lit8 v0, v0, 0x1

    iput v0, p0, Lfix/Meter;->frames:I

    .line 2
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    iget-wide v2, p0, Lfix/Meter;->last:J

    sub-long v4, v0, v2

    long-to-double v4, v4

    const-wide v6, 0x40a7700000000000L    # 3000.0

    cmpl-double v4, v4, v6

    if-ltz v4, :cond_0

    return-void

    .line 3
    :cond_0
    iget v4, p0, Lfix/Meter;->frames:I

    int-to-double v4, v4

    sub-long v2, v0, v2

    long-to-double v2, v2

    const-wide v6, 0x408f400000000000L    # 1000.0

    div-double/2addr v2, v6

    div-double/2addr v4, v2

    iput-wide v4, p0, Lfix/Meter;->rate:D

    const/4 v4, 0x0

    iput v4, p0, Lfix/Meter;->frames:I

    iput-wide v0, p0, Lfix/Meter;->last:J

    return-void
.end method
