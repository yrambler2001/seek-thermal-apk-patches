.class Lfix/Render$f;
.super Ljava/lang/Object;
.source "Render.java"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field final synthetic a:Lfix/Render;

.field final synthetic frame:Ljava/nio/ByteBuffer;


# virtual methods
.method public run()V
    .locals 5

    .prologue
    iget-object v0, p0, Lfix/Render$f;->a:Lfix/Render;

    iget-object v2, p0, Lfix/Render$f;->frame:Ljava/nio/ByteBuffer;

    const/16 v3, 0xce

    const/16 v4, 0x9c

    invoke-virtual {v0, v2, v3, v4}, Lfix/Render;->a(Ljava/nio/ByteBuffer;II)V

    return-void
.end method
