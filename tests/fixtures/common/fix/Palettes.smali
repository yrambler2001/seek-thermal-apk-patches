.class public Lfix/Palettes;
.super Ljava/lang/Object;
.source "Palettes.java"


# direct methods
# the palette list: one aput-object per name (default_palette)
.method static f()V
    .locals 8

    const/16 v1, 0x8

    new-array v3, v1, [Ljava/lang/String;

    const-string v4, "White"

    .line 2
    const/4 v5, 0x0

    aput-object v4, v3, v5

    const-string v4, "Black"

    .line 3
    const/4 v5, 0x1

    aput-object v4, v3, v5

    const-string v4, "Spectra"

    .line 4
    const/4 v5, 0x2

    aput-object v4, v3, v5

    const-string v4, "Prism"

    .line 5
    const/4 v5, 0x3

    aput-object v4, v3, v5

    const-string v4, "Tyrian"

    .line 6
    const/4 v5, 0x4

    aput-object v4, v3, v5

    const-string v4, "Iron"

    .line 7
    const/4 v5, 0x5

    aput-object v4, v3, v5

    const-string v4, "Amber"

    .line 8
    const/4 v5, 0x6

    aput-object v4, v3, v5

    const-string v4, "Hi"

    .line 9
    const/4 v5, 0x7

    aput-object v4, v3, v5

    return-void
.end method
