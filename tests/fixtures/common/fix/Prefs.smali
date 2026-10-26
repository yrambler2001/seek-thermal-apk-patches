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

# the temperature unit (default_unit): until one is stored, the default_unit integer resource
.method public static t(Landroid/content/Context;)Ljava/lang/String;
    .locals 3

    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    sget v1, Lfix/Ids;->c:I

    invoke-virtual {v0, v1}, Landroid/content/res/Resources;->getInteger(I)I

    move-result v0

    invoke-static {v0}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v0

    sget-object v1, Lfix/Prefs;->a:Landroid/content/SharedPreferences;

    const-string v2, "units"

    invoke-interface {v1, v2, v0}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method

# a default derived from the unit (default_unit): a threshold of 80 (Fahrenheit) or 27 (Celsius)
.method public static u(Landroid/content/Context;)I
    .locals 2

    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    sget v1, Lfix/Ids;->c:I

    invoke-virtual {v0, v1}, Landroid/content/res/Resources;->getInteger(I)I

    move-result v0

    if-nez v0, :cond_0

    const/16 v0, 0x50

    return v0

    :cond_0
    const/16 v0, 0x1b

    return v0
.end method

# another integer resource (default_unit leaves it)
.method public static w(Landroid/content/Context;)I
    .locals 2

    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    sget v1, Lfix/Ids;->a:I

    invoke-virtual {v0, v1}, Landroid/content/res/Resources;->getInteger(I)I

    move-result v0

    return v0
.end method
