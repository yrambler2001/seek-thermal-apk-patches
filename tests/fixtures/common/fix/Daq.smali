.class public Lfix/Daq;
.super Ljava/lang/Object;
.source "Daq.java"


# virtual methods
.method public run()V
    .locals 1

    const-string v0, "DAQ: awaiting USB copy"

    .line 7
    invoke-static {v0}, Lfix/Log;->a(Ljava/lang/String;)V

    return-void
.end method
