.class public Lfix/Program;
.super Ljava/lang/Object;
.source "Program.java"


# direct methods
.method public constructor <init>()V
    .locals 1

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    const-string v0, "#version 100\nprecision mediump float;\nuniform mat4 uTexMatrix;\nattribute vec4 aPosition;\nattribute vec4 aTextureCoord;\nvarying vec2 vTextureCoord;\nvoid main() {\n gl_Position = aPosition;\n vTextureCoord = (uTexMatrix * aTextureCoord).xy;\n}\n"

    return-void
.end method

.method private static fragment(Z)Ljava/lang/String;
    .locals 1

    if-eqz p0, :plain

    const-string v0, "#version 100\n#extension GL_OES_EGL_image_external : require\nprecision mediump float;\nvarying vec2 vTextureCoord;\nuniform sampler2D thermalTexture;\nuniform samplerExternalOES zzvisTexture;\nvoid main() {\n vec3 thrm = texture2D(thermalTexture, vTextureCoord).rgb;\n gl_FragColor = vec4(thrm, 1.0);\n}\n"

    return-object v0

    :plain
    const-string v0, "#version 100\n#extension GL_OES_EGL_image_external : require\nprecision mediump float;\nvarying vec2 vTextureCoord;\nuniform sampler2D thermalTexture;\nuniform samplerExternalOES visTexture;\nvoid main() {\n vec3 thrm = texture2D(thermalTexture, vTextureCoord).rgb;\n gl_FragColor = vec4(thrm, 1.0);\n}\n"

    return-object v0
.end method


# virtual methods
.method public draw()V
    .locals 3

    const/4 v0, 0x5

    const/4 v1, 0x0

    const/4 v2, 0x4

    invoke-static {v0, v1, v2}, Landroid/opengl/GLES20;->glDrawArrays(III)V

    return-void
.end method
