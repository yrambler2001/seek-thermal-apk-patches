.class public Lfix/Overlay;
.super Ljava/lang/Object;
.source "SourceFile"


# instance fields
.field private A:Z

.field private X:F

.field private Y:Lfix/Render;


# direct methods
# the stream's Thermal+ switch (phone_camera): blends the phone camera in at X, or not at all
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
.method public b1(Z)V
    .locals 1

    iput-boolean p1, p0, Lfix/Overlay;->A:Z

    iget-object v0, p0, Lfix/Overlay;->Y:Lfix/Render;

    if-eqz v0, :cond_1

    if-eqz p1, :cond_0

    iget p1, p0, Lfix/Overlay;->X:F

    goto :goto_0

    :cond_0
    const/4 p1, 0x0

    :goto_0
    invoke-virtual {v0, p1}, Lfix/Render;->H(F)V

    :cond_1
    return-void
.end method
