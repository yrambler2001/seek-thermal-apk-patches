.class public Lfix/Main;
.super Landroid/app/Activity;
.source "Main.java"


# instance fields
.field private q9:I

.field private s9:Z


# direct methods
# photo (0) / video (1) / gallery (2): checks the microphone first on Android 11+ (mic_prompt)
.method public Y0(Ljava/lang/String;I)V
    .locals 7

    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const-string v1, "android.permission.RECORD_AUDIO"

    const/4 v2, 0x1

    const/4 v3, 0x0

    const/16 v4, 0x1d

    if-le v0, v4, :cond_2

    filled-new-array {v1}, [Ljava/lang/String;

    move-result-object v5

    aget-object v6, v5, v3

    .line 3
    invoke-static {p0, v6}, Lfix/Outline;->a(Lfix/Main;Ljava/lang/String;)I

    move-result v6

    if-eqz v6, :cond_0

    invoke-static {p0, v5, v3}, Lfix/Outline;->b(Lfix/Main;[Ljava/lang/String;I)V

    return-void

    :cond_0
    aget-object v5, v5, v3

    invoke-static {p0, v5}, Lfix/Outline;->a(Lfix/Main;Ljava/lang/String;)I

    move-result v5

    if-nez v5, :cond_1

    const/4 v5, 0x1

    goto :goto_0

    :cond_1
    const/4 v5, 0x0

    :goto_0
    sput-boolean v5, Lfix/Encoder;->j:Z

    :cond_2
    if-nez p2, :cond_3

    invoke-direct {p0}, Lfix/Main;->d3()V

    return-void

    :cond_3
    if-ne p2, v2, :cond_4

    invoke-direct {p0}, Lfix/Main;->N3()V

    :cond_4
    return-void
.end method

.method private d3()V
    .locals 0

    return-void
.end method

# the video button: start / stop
.method private N3()V
    .locals 1

    .line 1
    iget-boolean v0, p0, Lfix/Main;->s9:Z

    if-eqz v0, :cond_0

    invoke-direct {p0}, Lfix/Main;->j3()V

    goto :goto_0

    :cond_0
    invoke-direct {p0}, Lfix/Main;->g3()V

    :goto_0
    return-void
.end method

.method private g3()V
    .locals 1

    const/4 v0, 0x1

    iput-boolean v0, p0, Lfix/Main;->s9:Z

    return-void
.end method

.method private j3()V
    .locals 1

    const/4 v0, 0x0

    iput-boolean v0, p0, Lfix/Main;->s9:Z

    return-void
.end method

.method private S0(I)V
    .locals 0

    iput p1, p0, Lfix/Main;->q9:I

    return-void
.end method

.method public u2()V
    .locals 2

    const-string v0, "Main"

    const-string v1, "onSwipeLeft Mode:"

    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    iget v0, p0, Lfix/Main;->q9:I

    const/4 v1, 0x2

    if-ne v0, v1, :cond_1

    const/4 v0, 0x3

    invoke-direct {p0, v0}, Lfix/Main;->S0(I)V

    :cond_1
    return-void
.end method
