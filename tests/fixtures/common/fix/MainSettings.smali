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
# another settings screen: it does not name the "Image smoothing" switch
.method public onCreate(Landroid/os/Bundle;)V
    .locals 0

    invoke-super {p0, p1}, Landroid/preference/PreferenceFragment;->onCreate(Landroid/os/Bundle;)V

    const p1, 0x7f100006

    invoke-virtual {p0, p1}, Lfix/MainSettings;->addPreferencesFromResource(I)V

    return-void
.end method
