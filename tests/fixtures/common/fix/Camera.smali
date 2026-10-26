.class public Lfix/Camera;
.super Landroid/content/BroadcastReceiver;
.source "SourceFile"


# static fields
.field protected static p:Landroid/app/PendingIntent;

.field protected static t:Lfix/Camera;


# instance fields
.field protected b:Ljava/util/ArrayList;

.field protected d:Ljava/lang/Runnable;

.field protected n:Lfix/UsbLink;


# direct methods
# the camera library (reconnect_fix): a singleton, and the receiver for its USB events, registered once --
# exported (flag 2) on Android 13+ -- with the permission request's PendingIntent, an implicit broadcast
.method protected constructor <init>(Landroid/content/Context;)V
    .locals 3

    invoke-direct {p0}, Landroid/content/BroadcastReceiver;-><init>()V

    new-instance v0, Ljava/util/ArrayList;

    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V

    iput-object v0, p0, Lfix/Camera;->b:Ljava/util/ArrayList;

    new-instance v0, Lfix/UsbLink;

    invoke-direct {v0}, Lfix/UsbLink;-><init>()V

    iput-object v0, p0, Lfix/Camera;->n:Lfix/UsbLink;

    new-instance v0, Landroid/content/Intent;

    const-string v1, "com.tyriansystems.Seekware.SeekwareLibrary.USB_PERMISSION"

    invoke-direct {v0, v1}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const/4 v2, 0x0

    invoke-static {p1, v2, v0, v2}, Landroid/app/PendingIntent;->getBroadcast(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;

    move-result-object v0

    sput-object v0, Lfix/Camera;->p:Landroid/app/PendingIntent;

    new-instance v0, Landroid/content/IntentFilter;

    invoke-direct {v0, v1}, Landroid/content/IntentFilter;-><init>(Ljava/lang/String;)V

    const-string v1, "android.hardware.usb.action.USB_DEVICE_DETACHED"

    invoke-virtual {v0, v1}, Landroid/content/IntentFilter;->addAction(Ljava/lang/String;)V

    sget v1, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v2, 0x21

    if-lt v1, v2, :cond_0

    const/4 v1, 0x2

    invoke-static {p1, p0, v0, v1}, Lfix/Compat;->a(Landroid/content/Context;Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;

    goto :goto_0

    :cond_0
    invoke-virtual {p1, p0, v0}, Landroid/content/Context;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;)Landroid/content/Intent;

    :goto_0
    return-void
.end method

# the camera screen closing: the receiver goes
.method public static L(Landroid/content/Context;)V
    .locals 1

    .line 1
    sget-object v0, Lfix/Camera;->t:Lfix/Camera;

    if-eqz v0, :cond_0

    :try_start_0
    invoke-virtual {p0, v0}, Landroid/content/Context;->unregisterReceiver(Landroid/content/BroadcastReceiver;)V
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_0

    :catch_0
    move-exception p0

    invoke-virtual {p0}, Ljava/lang/Throwable;->printStackTrace()V

    :cond_0
    :goto_0
    return-void
.end method

.method public static v(Landroid/content/Context;)Lfix/Camera;
    .locals 1

    sget-object v0, Lfix/Camera;->t:Lfix/Camera;

    if-nez v0, :cond_0

    new-instance v0, Lfix/Camera;

    invoke-direct {v0, p0}, Lfix/Camera;-><init>(Landroid/content/Context;)V

    sput-object v0, Lfix/Camera;->t:Lfix/Camera;

    :cond_0
    return-object v0
.end method

# the search: permission asked for each camera
.method private G()V
    .locals 0

    return-void
.end method


# virtual methods
# the next camera screen's listener: the search runs when no camera is listed
.method public D(Ljava/lang/Runnable;)I
    .locals 0

    if-eqz p1, :cond_1

    iput-object p1, p0, Lfix/Camera;->d:Ljava/lang/Runnable;

    iget-object p1, p0, Lfix/Camera;->b:Ljava/util/ArrayList;

    .line 2
    invoke-virtual {p1}, Ljava/util/ArrayList;->size()I

    move-result p1

    if-nez p1, :cond_0

    invoke-direct {p0}, Lfix/Camera;->G()V

    :cond_0
    const/4 p1, 0x0

    return p1

    :cond_1
    const/4 p1, 0x1

    return p1
.end method

# unplugging: the wrapper's close with the intent's device, then each matching camera closed and taken off the list
.method protected t(Landroid/content/Intent;)V
    .locals 4

    new-instance v1, Lfix/UsbHolder;

    invoke-direct {v1}, Lfix/UsbHolder;-><init>()V

    iget-object p1, p0, Lfix/Camera;->n:Lfix/UsbLink;

    invoke-virtual {p1, v1}, Lfix/UsbLink;->a(Lfix/UsbHolder;)I

    new-instance p1, Ljava/util/ArrayList;

    invoke-direct {p1}, Ljava/util/ArrayList;-><init>()V

    iget-object v0, p0, Lfix/Camera;->b:Ljava/util/ArrayList;

    invoke-virtual {v0}, Ljava/util/ArrayList;->iterator()Ljava/util/Iterator;

    move-result-object v0

    :goto_0
    invoke-interface {v0}, Ljava/util/Iterator;->hasNext()Z

    move-result v2

    if-eqz v2, :cond_0

    invoke-interface {v0}, Ljava/util/Iterator;->next()Ljava/lang/Object;

    move-result-object v2

    check-cast v2, Lfix/CameraDevice;

    invoke-virtual {v2}, Lfix/CameraDevice;->Z()Lfix/UsbHolder;

    move-result-object v3

    if-ne v3, v1, :goto_0

    invoke-virtual {p1, v2}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z

    goto :goto_0

    :cond_0
    invoke-virtual {p1}, Ljava/util/ArrayList;->iterator()Ljava/util/Iterator;

    move-result-object p1

    :goto_1
    invoke-interface {p1}, Ljava/util/Iterator;->hasNext()Z

    move-result v0

    if-eqz v0, :cond_1

    invoke-interface {p1}, Ljava/util/Iterator;->next()Ljava/lang/Object;

    move-result-object v0

    check-cast v0, Lfix/CameraDevice;

    invoke-virtual {v0}, Lfix/CameraDevice;->C0()V

    iget-object v1, p0, Lfix/Camera;->b:Ljava/util/ArrayList;

    invoke-virtual {v1, v0}, Ljava/util/ArrayList;->remove(Ljava/lang/Object;)Z

    goto :goto_1

    :cond_1
    return-void
.end method

# a permission answer: the camera is opened through the wrapper
.method protected c(Lfix/UsbHolder;)V
    .locals 1

    iget-object v0, p0, Lfix/Camera;->n:Lfix/UsbLink;

    invoke-virtual {v0, p1}, Lfix/UsbLink;->c(Lfix/UsbHolder;)I

    return-void
.end method

.method public onReceive(Landroid/content/Context;Landroid/content/Intent;)V
    .locals 0

    invoke-virtual {p0, p2}, Lfix/Camera;->t(Landroid/content/Intent;)V

    return-void
.end method
