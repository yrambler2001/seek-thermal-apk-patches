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

# whether Settings shows a hidden switch (hidden_settings)
.method public static D(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "allow_reg_optout_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method

# whether Settings shows a hidden switch (hidden_settings)
.method public static E(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "export_frame_rate_allowed_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method

# whether Settings shows a hidden switch (hidden_settings)
.method public static I(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "lossless_comp_allowed_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method

# whether Settings shows a hidden switch (hidden_settings)
.method public static O(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "sim_mode_allowed_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method

# whether Settings shows a hidden switch (hidden_settings)
.method public static P(Landroid/content/Context;)Z
    .locals 2

    .line 1
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v0, "staging_registration_allowed_key"

    const/4 v1, 0x0

    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result p0

    return p0
.end method

# the chosen palette, 2 until one is picked (default_palette)
.method public static b(Landroid/content/Context;)I
    .locals 2

    :try_start_0
    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    .line 6
    const-string v0, "color_palette"

    .line 8
    const/4 v1, 0x2

    .line 9
    invoke-interface {p0, v0, v1}, Landroid/content/SharedPreferences;->getInt(Ljava/lang/String;I)I

    move-result p0
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    return p0

    :catch_0
    const/4 p0, 0x0

    return p0
.end method

.method public static Z(Landroid/content/Context;I)V
    .locals 1

    sget-object p0, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    invoke-interface {p0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;

    move-result-object p0

    const-string v0, "color_palette"

    invoke-interface {p0, v0, p1}, Landroid/content/SharedPreferences$Editor;->putInt(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;

    return-void
.end method
