.class public Lfix/Pipeline;
.super Ljava/lang/Object;
.source "Pipeline.java"


# instance fields
.field private C:Z

.field private M:Z

.field private ctx:Landroid/content/Context;


# direct methods
.method private c0(J)V
    .locals 3

    sget-object v1, Lfix/Features;->u9:Lfix/Features;

    iget-boolean v2, p0, Lfix/Pipeline;->C:Z

    invoke-direct {p0, p1, p2, v1, v2}, Lfix/Pipeline;->set(JLfix/Features;I)V

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

    iget-object v4, p0, Lfix/Pipeline;->ctx:Landroid/content/Context;

    const-string v4, ".jpg"

    iget-boolean v1, p0, Lfix/Pipeline;->M:Z

    if-eqz v1, :jpeg

    const-string v4, ".png"

    :jpeg
    const-string v1, "deleteme"

    sget-object v1, Landroid/graphics/Bitmap$CompressFormat;->PNG:Landroid/graphics/Bitmap$CompressFormat;

    return-void
.end method

# the EXIF writer (photo_1x): tags the temp file, copies it to its final name
.method private T(Ljava/io/File;Ljava/io/File;Ljava/lang/String;Ljava/lang/String;)V
    .locals 3

    invoke-static {}, Lfix/Pipeline;->o0()I

    move-result v1

    new-instance v0, Landroid/media/ExifInterface;

    invoke-virtual {p1}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;

    move-result-object v2

    invoke-direct {v0, v2}, Landroid/media/ExifInterface;-><init>(Ljava/lang/String;)V

    const-string v2, "Orientation"

    invoke-static {v1}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v2, v1}, Landroid/media/ExifInterface;->setAttribute(Ljava/lang/String;Ljava/lang/String;)V

    invoke-virtual {v0}, Landroid/media/ExifInterface;->saveAttributes()V

    return-void
.end method

.method private static o0()I
    .locals 1

    const/4 v0, 0x6

    return v0
.end method

# the photo format flag (png_photos)
.method public O0(Z)V
    .locals 0

    .line 1
    iput-boolean p1, p0, Lfix/Pipeline;->M:Z

    .line 2
    return-void
.end method

.method private set(JLfix/Features;I)V
    .locals 0

    return-void
.end method

.method protected F0(Landroid/graphics/Canvas;FFFFLandroid/graphics/Bitmap;Ljava/lang/String;)V
    .locals 7

    new-instance v1, Landroid/graphics/Paint;

    invoke-direct {v1}, Landroid/graphics/Paint;-><init>()V

    invoke-virtual {p1, p7, p2, p3, v1}, Landroid/graphics/Canvas;->drawText(Ljava/lang/String;FFLandroid/graphics/Paint;)V

    return-void
.end method
