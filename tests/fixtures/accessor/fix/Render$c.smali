.class Lfix/Render$c;
.super Ljava/lang/Object;
.source "Render.java"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field final synthetic L8:Lfix/Render;


# virtual methods
.method public run()V
    .locals 3

    iget-object v0, p0, Lfix/Render$c;->L8:Lfix/Render;

    iget-object v1, v0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v1}, Landroid/graphics/SurfaceTexture;->updateTexImage()V

    iget-object v2, v0, Lfix/Render;->b:Lfix/Encoder;

    if-eqz v2, :no_encoder

    iget-object v1, v0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v2, v1}, Lfix/Encoder;->e(Landroid/graphics/SurfaceTexture;)V

    :no_encoder

    invoke-static {v0}, Lfix/Render;->b(Lfix/Render;)V

    return-void
.end method
