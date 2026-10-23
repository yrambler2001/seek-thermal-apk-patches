.class public Lfix/Pipeline;
.super Ljava/lang/Object;
.source "Pipeline.java"


# instance fields
.field private C:Z


# direct methods
.method private c0(J)V
    .locals 3

    const/4 v0, 0x0

    return-void
.end method

.method private e0(Ljava/lang/String;Landroid/graphics/Bitmap;Z)V
    .locals 5

    new-instance v0, Landroid/graphics/Canvas;

    invoke-direct {v0}, Landroid/graphics/Canvas;-><init>()V

    new-instance v2, Landroid/graphics/Rect;

    invoke-direct {v2}, Landroid/graphics/Rect;-><init>()V

    new-instance v3, Landroid/graphics/Paint;

    invoke-direct {v3}, Landroid/graphics/Paint;-><init>()V

    if-eqz p3, :full

    new-instance v1, Landroid/graphics/Rect;

    invoke-direct {v1}, Landroid/graphics/Rect;-><init>()V

    invoke-virtual {v0, p2, v1, v2, v3}, Landroid/graphics/Canvas;->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;Landroid/graphics/Rect;Landroid/graphics/Paint;)V

    goto :save

    :full
    const/4 v1, 0x0

    invoke-virtual {v0, p2, v1, v2, v3}, Landroid/graphics/Canvas;->drawBitmap(Landroid/graphics/Bitmap;Landroid/graphics/Rect;Landroid/graphics/Rect;Landroid/graphics/Paint;)V

    :save
    const-string v4, "_thermal"

    return-void
.end method

.method private set(JLfix/Features;I)V
    .locals 0

    return-void
.end method
