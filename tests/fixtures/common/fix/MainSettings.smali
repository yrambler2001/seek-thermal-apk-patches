.class public Lfix/MainSettings;
.super Landroid/preference/PreferenceFragment;
.source "MainSettings.java"


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Landroid/preference/PreferenceFragment;-><init>()V

    return-void
.end method


# virtual methods
# the Settings screen: it names the entry that opens Image & Video, not the "Image smoothing" switch
.method public onCreate(Landroid/os/Bundle;)V
    .locals 0

    invoke-super {p0, p1}, Landroid/preference/PreferenceFragment;->onCreate(Landroid/os/Bundle;)V

    const p1, 0x7f100006

    invoke-virtual {p0, p1}, Lfix/MainSettings;->addPreferencesFromResource(I)V

    return-void
.end method

# the entry that opens Image & Video
.method public onActivityCreated(Landroid/os/Bundle;)V
    .locals 1

    invoke-super {p0, p1}, Landroid/preference/PreferenceFragment;->onActivityCreated(Landroid/os/Bundle;)V

    const-string v0, "image_and_video"

    invoke-virtual {p0, v0}, Lfix/MainSettings;->findPreference(Ljava/lang/CharSequence;)Landroid/preference/Preference;

    return-void
.end method
