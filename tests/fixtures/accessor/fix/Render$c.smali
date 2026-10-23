.class Lfix/Render$c;
.super Ljava/lang/Object;
.source "Render.java"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field final synthetic L8:Lfix/Render;


# virtual methods
.method public run()V
    .locals 2

    iget-object v0, p0, Lfix/Render$c;->L8:Lfix/Render;

    iget-object v1, v0, Lfix/Render;->camera:Landroid/graphics/SurfaceTexture;

    invoke-virtual {v1}, Landroid/graphics/SurfaceTexture;->updateTexImage()V

    invoke-static {v0}, Lfix/Render;->b(Lfix/Render;)V

    return-void
.end method
