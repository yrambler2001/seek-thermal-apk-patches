.class public Lfix/NativeLib;
.super Ljava/lang/Object;
.source "NativeLib.java"


# direct methods
.method static constructor <clinit>()V
    .locals 1

    const-string v0, "seekip"

    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V

    return-void
.end method

.method public static c(JILjava/nio/ByteBuffer;I)I
    .locals 1

    invoke-static/range {p0 .. p4}, Lfix/NativeLib;->seekIPgetFeature(JILjava/nio/ByteBuffer;I)I

    move-result v0

    return v0
.end method

.method public static g(JILjava/nio/ByteBuffer;I)I
    .locals 1

    invoke-static/range {p0 .. p4}, Lfix/NativeLib;->seekIPsetFeature(JILjava/nio/ByteBuffer;I)I

    move-result v0

    return v0
.end method

.method private static native seekIPgetFeature(JILjava/nio/ByteBuffer;I)I
.end method

.method private static native seekIPsetFeature(JILjava/nio/ByteBuffer;I)I
.end method
