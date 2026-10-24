.class public Lfix/ImageSettings;
.super Landroid/preference/PreferenceFragment;
.source "ImageSettings.java"

# interfaces
.implements Landroid/content/SharedPreferences$OnSharedPreferenceChangeListener;


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Landroid/preference/PreferenceFragment;-><init>()V

    return-void
.end method


# virtual methods
# the Image & Video screen: its preferences come from a resource (the settings hook goes after them)
.method public onCreate(Landroid/os/Bundle;)V
    .locals 0

    .line 1
    invoke-super {p0, p1}, Landroid/preference/PreferenceFragment;->onCreate(Landroid/os/Bundle;)V

    const p1, 0x7f100003

    .line 2
    invoke-virtual {p0, p1}, Landroid/preference/PreferenceFragment;->addPreferencesFromResource(I)V

    return-void
.end method

# logs a change of the "Image smoothing" switch
.method public onSharedPreferenceChanged(Landroid/content/SharedPreferences;Ljava/lang/String;)V
    .locals 1

    const-string v0, "use_smoothing"

    invoke-virtual {p2, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    return-void
.end method
