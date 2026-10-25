.class Lfix/Analytics;
.super Ljava/lang/Thread;
.source "Analytics.java"


# instance fields
.field private volatile c:Z

.field private final d:Landroid/content/Context;

.field private volatile e:Z

.field private volatile f:Lfix/Uploader;

.field private final g:Ljava/util/concurrent/LinkedBlockingQueue;


# direct methods
# the analytics thread (no_analytics): named GAThread, it sets up the uploader, then runs queued work
.method constructor <init>(Landroid/content/Context;)V
    .locals 1

    const-string v0, "GAThread"

    invoke-direct {p0, v0}, Ljava/lang/Thread;-><init>(Ljava/lang/String;)V

    new-instance v0, Ljava/util/concurrent/LinkedBlockingQueue;

    invoke-direct {v0}, Ljava/util/concurrent/LinkedBlockingQueue;-><init>()V

    iput-object v0, p0, Lfix/Analytics;->g:Ljava/util/concurrent/LinkedBlockingQueue;

    iput-object p1, p0, Lfix/Analytics;->d:Landroid/content/Context;

    invoke-virtual {p0}, Ljava/lang/Thread;->start()V

    return-void
.end method


# virtual methods
.method public run()V
    .locals 3

    const/4 v0, 0x1

    :try_start_0
    new-instance v1, Lfix/Uploader;

    .line 3
    iget-object v2, p0, Lfix/Analytics;->d:Landroid/content/Context;

    invoke-direct {v1, v2, p0}, Lfix/Uploader;-><init>(Landroid/content/Context;Ljava/lang/Thread;)V

    iput-object v1, p0, Lfix/Analytics;->f:Lfix/Uploader;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    goto :goto_0

    :catchall_0
    move-exception v1

    const-string v1, "Google Analytics will not start up."

    invoke-static {v1}, Lfix/Log;->a(Ljava/lang/String;)V

    iput-boolean v0, p0, Lfix/Analytics;->e:Z

    :cond_0
    :goto_0
    iget-boolean v1, p0, Lfix/Analytics;->c:Z

    if-nez v1, :cond_1

    :try_start_1
    iget-object v1, p0, Lfix/Analytics;->g:Ljava/util/concurrent/LinkedBlockingQueue;

    invoke-virtual {v1}, Ljava/util/concurrent/LinkedBlockingQueue;->take()Ljava/lang/Object;

    move-result-object v1

    .line 9
    check-cast v1, Ljava/lang/Runnable;

    iget-boolean v2, p0, Lfix/Analytics;->e:Z

    if-nez v2, :cond_0

    invoke-interface {v1}, Ljava/lang/Runnable;->run()V
    :try_end_1
    .catch Ljava/lang/InterruptedException; {:try_start_1 .. :try_end_1} :cond_0

    goto :goto_0

    :cond_1
    return-void
.end method

# the app's work: a hit for the uploader
.method public a(Ljava/lang/Runnable;)V
    .locals 1

    iget-object v0, p0, Lfix/Analytics;->g:Ljava/util/concurrent/LinkedBlockingQueue;

    invoke-virtual {v0, p1}, Ljava/util/concurrent/LinkedBlockingQueue;->add(Ljava/lang/Object;)Z

    return-void
.end method
