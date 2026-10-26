.class public Lfix/CameraDevice;
.super Ljava/lang/Object;
.source "SourceFile"


# instance fields
.field private final a:Lfix/UsbHolder;


# direct methods
# a camera of the library (reconnect_fix): closed on unplugging, its USB connection in a holder
.method public constructor <init>(Lfix/UsbHolder;)V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lfix/CameraDevice;->a:Lfix/UsbHolder;

    return-void
.end method


# virtual methods
.method C0()V
    .locals 0

    return-void
.end method

.method public Z()Lfix/UsbHolder;
    .locals 1

    iget-object v0, p0, Lfix/CameraDevice;->a:Lfix/UsbHolder;

    return-object v0
.end method
