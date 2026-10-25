.class public Lfix/Stream$b;
.super Ljava/lang/Object;
.source "Stream.java"


# instance fields
.field protected c:F

.field protected d:F


# virtual methods
.method public j(Lfix/Palette;IZLandroid/graphics/Canvas;Landroid/graphics/Rect;)V
    .locals 4

    const/4 v2, 0x0

    const/4 v3, 0x0

    if-eqz p3, :cond_0

    iget v1, p0, Lfix/Stream$b;->d:F

    move v2, v1

    iget v1, p0, Lfix/Stream$b;->c:F

    move v3, v1

    :cond_0
    return-void
.end method
