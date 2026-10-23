.class public final enum Lfix/Features;
.super Ljava/lang/Enum;
.source "Features.java"


# static fields
.field public static final enum u9:Lfix/Features;


# direct methods
.method static constructor <clinit>()V
    .locals 4

    new-instance v0, Lfix/Features;

    const-string v1, "featureEnhancedProcessing"

    const/4 v2, 0x0

    const/16 v3, 0x384

    invoke-direct {v0, v1, v2, v3}, Lfix/Features;-><init>(Ljava/lang/String;II)V

    sput-object v0, Lfix/Features;->u9:Lfix/Features;

    return-void
.end method

.method private constructor <init>(Ljava/lang/String;II)V
    .locals 0

    invoke-direct {p0, p1, p2}, Ljava/lang/Enum;-><init>(Ljava/lang/String;I)V

    return-void
.end method
