.class Lfix/Render$e;
.super Ljava/lang/Object;
.source "Render.java"

# interfaces
.implements Ljava/lang/Runnable;


# instance fields
.field final synthetic O8:Lfix/Render;

.field final synthetic frame:Ljava/nio/ByteBuffer;


# virtual methods
.method public run()V
    .locals 5

    iget-object v1, p0, Lfix/Render$e;->O8:Lfix/Render;

    iget-object v2, p0, Lfix/Render$e;->frame:Ljava/nio/ByteBuffer;

    const/16 v3, 0xce

    const/16 v4, 0x9c

    invoke-static {v1, v2, v3, v4}, Lfix/Render;->d(Lfix/Render;Ljava/nio/ByteBuffer;II)V

    return-void
.end method
