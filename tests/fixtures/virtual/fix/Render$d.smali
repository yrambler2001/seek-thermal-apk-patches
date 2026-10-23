.class Lfix/Render$d;
.super Ljava/lang/Object;
.source "Render.java"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field final synthetic a:Lfix/Render;


# virtual methods
.method public run()V
    .locals 2

    .prologue
    iget-object v0, p0, Lfix/Render$d;->a:Lfix/Render;

    iget-object v1, v0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v1}, Landroid/graphics/SurfaceTexture;->updateTexImage()V

    iget-object v0, p0, Lfix/Render$d;->a:Lfix/Render;

    invoke-virtual {v0}, Lfix/Render;->h()V

    return-void
.end method
