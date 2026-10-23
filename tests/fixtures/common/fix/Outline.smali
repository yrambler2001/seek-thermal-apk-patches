.class public final synthetic Lfix/Outline;
.super Ljava/lang/Object;
.source "R8$$SyntheticClass"


# direct methods
# d8 API outlines, as the app calls permission APIs (mic_prompt)
.method public static synthetic a(Lfix/Main;Ljava/lang/String;)I
    .locals 0

    invoke-virtual {p0, p1}, Landroid/app/Activity;->checkSelfPermission(Ljava/lang/String;)I

    move-result p0

    return p0
.end method

.method public static synthetic b(Lfix/Main;[Ljava/lang/String;I)V
    .locals 0

    invoke-virtual {p0, p1, p2}, Landroid/app/Activity;->requestPermissions([Ljava/lang/String;I)V

    return-void
.end method
