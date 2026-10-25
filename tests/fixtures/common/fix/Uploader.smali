.class Lfix/Uploader;
.super Ljava/lang/Object;
.source "Uploader.java"


# instance fields
.field private final a:Lorg/apache/http/client/HttpClient;


# direct methods
# what the analytics thread sets up (no_analytics): it would connect and send, with Apache HTTP
# (http_legacy: the app uses the library)
.method constructor <init>(Landroid/content/Context;Ljava/lang/Thread;)V
    .locals 1

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    new-instance v0, Lorg/apache/http/impl/client/DefaultHttpClient;

    invoke-direct {v0}, Lorg/apache/http/impl/client/DefaultHttpClient;-><init>()V

    iput-object v0, p0, Lfix/Uploader;->a:Lorg/apache/http/client/HttpClient;

    return-void
.end method
