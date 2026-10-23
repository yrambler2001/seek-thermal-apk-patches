.class public Lfix/Prefs;
.super Ljava/lang/Object;
.source "Prefs.java"


# static fields
.field static a:Landroid/content/SharedPreferences;


# direct methods
# "Save Uncompressed" (png_photos)
.method public static H(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "lossless_comp_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method
