.class public abstract synthetic Lfix/Compat;
.super Ljava/lang/Object;
.source "SourceFile"


# direct methods
# the receiver registration with flags (reconnect_fix), outlined as R8 writes a newer API's call
.method public static bridge synthetic a(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;
    .locals 0

    invoke-virtual {p0, p1, p2, p3}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;

    move-result-object p0

    return-object p0
.end method
