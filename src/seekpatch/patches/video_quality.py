"""video_quality: record video at the photo's size and quality, one frame per thermal frame, with
good sound.

The stock recording is H.264 at 480x640 and a fixed 1.5 Mbit/s, 15 fps, keyframes every 5 s, and
mono 44.1 kHz AAC at 64 kbit/s.  The patch changes six places:

    the video encoder       MediaCodec.createEncoderByType + configure in the recorder's
                            constructor become seekpatch.Video.encoder(format): HEVC (or H.264,
                            in the settings), hardware first, 960x1280 (the photo's pixels), constant
                            QP 18 where the encoder takes QP bounds, else constant-quality
                            mode, else 12 Mbit/s -- or VBR at a bitrate chosen in the settings;
                            keyframe every second; BT.709 colour tags.
                            Falls back to the app's own format if no encoder takes these.
    the frame clock         the GL thread handed a frame to the encoder on every *phone-camera*
                            frame (15 fps); the patch hands one over after every thermal upload
                            instead (~27 - 30 fps on a Compact Pro, no cap), and drops the camera one.
    the microphone          getMinBufferSize / the AudioRecord's rate and channels: 48 kHz stereo,
                            else 48 kHz mono, else the app's own (seekpatch.Audio)
    the sound encoder       AAC-LC at 256 kbit/s stereo / 160 kbit/s mono
    the sound's bytes       the block's ByteBuffer.array() in the read: the app copies a direct
                            buffer's array from index 0, where Android keeps its bytes a few in
                            (a click every block, 50 a second); seekpatch.Audio.samples gives
                            them from the first
    the sound's timestamps  queueInputBuffer / dequeueOutputBuffer: each block and each AAC frame
                            stamped with the time of its first sample, counted in samples (the app
                            stamps blocks with the time their read started, and Android 7's
                            encoder gives frames the stamp of the block they start in: the sound
                            stuttered three times a second); the encoder's 2-byte configuration no
                            longer goes into the file as a sound frame

Where the release has the settings screen (settings.py), Settings -> Image & Video gets a "Video
codec" list (H.265 / H.264, starting from H.265) and a "Video quality" list
(seekpatch.VideoSettings): the QP, starting from 18, or a bitrate, 2 - 40 Mbit/s; where the
encoder takes no QP, only the bitrates, 12 Mbit/s by default.  seekpatch.Video reads them at the
start of each recording.

The picture is drawn by the same GL code as the live view (the encoder thread calls the render
thread's draw), so sharp_scaling and the overlays apply to it exactly as on screen.  Sources of the
helpers: helpers/java/seekpatch/{Video,Audio}.java.
"""
from __future__ import annotations

import re

from ..helpers import add_helpers
from ..smali import GAP, REG, PatchError, SmaliTree, methods, smali_escape
from .base import ensure_unpatched, mark
from .seek import render_thread, upload_call
from .settings import optional_settings

NAME = "video_quality"
SUMMARY = "video at the photo's size, HEVC constant quality, every thermal frame (no 15 fps cap), 48 kHz stereo"
VERSIONS = "2.1.2 - 2.3.4"
RECOMMENDED = True

MARK = mark(NAME)
MIME = "video/hevc"          # the codec at the start, H.265 (Settings: H.264)
QP = 18                      # the constant quantizer at the start (lower = better and bigger)
LONG_SIDE = 1280             # the photo is 1280x960 (16:9: 1280x720)
MAX_BITRATE = 40_000_000     # ceiling for the constant-QP encoder: keeps the signalled level at 5.1 (HEVC)
FALLBACK_BITRATE = 12_000_000  # 960x1280 when the encoder has no quality control (the owner's choice)

CREATE_ENCODER = "Landroid/media/MediaCodec;->createEncoderByType(Ljava/lang/String;)Landroid/media/MediaCodec;"
CONFIGURE = "Landroid/media/MediaCodec;->configure(Landroid/media/MediaFormat;Landroid/view/Surface;Landroid/media/MediaCrypto;I)V"
VIDEO_FORMAT = "Landroid/media/MediaFormat;->createVideoFormat(Ljava/lang/String;II)Landroid/media/MediaFormat;"
AUDIO_FORMAT = "Landroid/media/MediaFormat;->createAudioFormat(Ljava/lang/String;II)Landroid/media/MediaFormat;"
MIN_BUFFER = "Landroid/media/AudioRecord;->getMinBufferSize(III)I"
AUDIO_RECORD = "Landroid/media/AudioRecord;-><init>(IIIII)V"
AUDIO_READ = "Landroid/media/AudioRecord;->read("
BUFFER_ARRAY = "Ljava/nio/ByteBuffer;->array()[B"
QUEUE_INPUT = "Landroid/media/MediaCodec;->queueInputBuffer(IIIJI)V"
DEQUEUE_OUTPUT = "Landroid/media/MediaCodec;->dequeueOutputBuffer(Landroid/media/MediaCodec$BufferInfo;J)I"
UPDATE_TEX_IMAGE = "Landroid/graphics/SurfaceTexture;->updateTexImage()V"
SURFACE_TEXTURE = "Landroid/graphics/SurfaceTexture;"
VIDEO_FRAME = "seekpatchVideoFrame()V"

CONFIG_SMALI = """.class public final Lseekpatch/VideoConfig;
.super Ljava/lang/Object;
.source "seek-thermal-apk-patches video_quality"

{mark}: values from the command line, read by seekpatch.Video


# static fields
.field public static bitrate:I = {bitrate}

.field public static longSide:I = {long_side}

.field public static maxBitrate:I = {max_bitrate}

.field public static mime:Ljava/lang/String; = "{mime}"

.field public static qp:I = {qp}

.field public static target:I = 0x0
"""

FRAME_METHOD = """
{mark}: hand every thermal frame to the video encoder (it draws the scene itself)
.method public {frame}
    .locals 2

    iget-object v0, p0, {encoder_field}
    if-eqz v0, :seekpatch_none
    iget-object v1, p0, {texture_field}
    if-eqz v1, :seekpatch_none

    # the encoder draws from its own GL context: the upload has to be finished first
    invoke-static {{}}, Landroid/opengl/GLES20;->glFinish()V

    :seekpatch_try_start
    invoke-virtual {{v0, v1}}, {encoder_call}
    :seekpatch_try_end
    .catch Ljava/lang/Throwable; {{:seekpatch_try_start .. :seekpatch_try_end}} :seekpatch_failed

    :seekpatch_none
    return-void

    :seekpatch_failed
    move-exception v0
    return-void
.end method
"""


def _one(pattern: str, text: str, what: str, flags=re.M) -> re.Match:
    found = list(re.finditer(pattern, text, flags))
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one {what}, found {len(found)}")
    return found[0]


_WRITES = r"(?:move-result(?:-object|-wide)?|const(?:/\d+|/high16|/wide|-string|-class|/jumbo)?|i?get[\w-]*|sget[\w-]*|aget[\w-]*|new-instance|new-array|move(?:-object|-wide)?(?:/from16|/16)?)"


def _overwritten_before_read(rest: str, reg: str) -> bool:
    """Is `reg` written (or never touched again) before it is next read in `rest`?  Only follows
    straight-line code: a branch before the answer counts as a read."""
    for line in rest.splitlines():
        s = line.strip()
        if not s or s.startswith((".", "#", ":")):
            continue
        if re.search(r"(?<![\w])" + reg + r"(?![\w])", s):
            return bool(re.match(_WRITES + r" " + reg + r",", s))
        if s.startswith(("return", "throw")):
            return True
        if s.startswith(("goto", "if-", "packed-switch", "sparse-switch")):
            return False
    return True


def _encoder(tree: SmaliTree) -> str:
    hits = [(p, m) for p in tree.containing(VIDEO_FORMAT, CREATE_ENCODER, CONFIGURE) for m in methods(tree.get(p))
            if VIDEO_FORMAT in m.body and CREATE_ENCODER in m.body and CONFIGURE in m.body]
    if len(hits) != 1:
        raise PatchError(f"{NAME}: expected one method that creates and configures the video encoder, found {len(hits)}")
    path, m = hits[0]
    body = m.body
    vf = _one(r"invoke-static \{" + REG + ", " + REG + ", " + REG + r"\}, " + re.escape(VIDEO_FORMAT) + GAP
              + r"move-result-object (" + REG + ")", body, "createVideoFormat")
    create = _one(r"^([ \t]*)invoke-static \{(" + REG + r")\}, " + re.escape(CREATE_ENCODER) + "$", body, "createEncoderByType")
    conf = _one(r"^([ \t]*)invoke-virtual \{(" + REG + "), (" + REG + "), " + REG + ", " + REG + ", " + REG + r"\}, "
                + re.escape(CONFIGURE) + "$", body, "video encoder configure()")
    fmt = conf.group(3)
    if not vf.end() < create.start() < conf.start() or vf.group(1) != fmt:
        raise PatchError(f"{NAME}: the video encoder is not configured with the format createVideoFormat made")
    if re.search(r"^\s*" + _WRITES + " " + fmt + ",", body[vf.end():conf.start()], re.M):
        raise PatchError(f"{NAME}: the video format register {fmt} changes before configure()")
    ind = create.group(1)
    new = (body[:create.start()]
           + f"{ind}{MARK}: choose and configure the encoder (seekpatch.Video)\n"
           + f"{ind}invoke-static {{{fmt}}}, Lseekpatch/Video;->encoder(Landroid/media/MediaFormat;)Landroid/media/MediaCodec;"
           + body[create.end():conf.start()]
           + f"{conf.group(1)}{MARK}: configured by seekpatch.Video"
           + body[conf.end():])
    tree.replace_method_body(path, m, new)
    return f"{tree.rel(path)} {m.name}()"


def _audio(tree: SmaliTree) -> str:
    hits = [(p, m) for p in tree.containing(AUDIO_RECORD, MIN_BUFFER, AUDIO_FORMAT, CONFIGURE) for m in methods(tree.get(p))
            if AUDIO_RECORD in m.body and MIN_BUFFER in m.body and AUDIO_FORMAT in m.body and CONFIGURE in m.body]
    if len(hits) != 1:
        raise PatchError(f"{NAME}: expected one method that sets up the microphone and the AAC encoder, found {len(hits)}")
    path, m = hits[0]
    body = m.body
    mb = _one(r"^([ \t]*)invoke-static (\{" + REG + ", " + REG + ", " + REG + r"\}), " + re.escape(MIN_BUFFER) + "$",
              body, "getMinBufferSize")
    rec = _one(r"^([ \t]*)invoke-direct(/range)? \{([^}]*)\}, " + re.escape(AUDIO_RECORD) + "$", body, "new AudioRecord")
    if rec.group(2):
        lo, hi = re.fullmatch(r"v(\d+) \.\. v(\d+)", rec.group(3)).groups()
        regs = [f"v{i}" for i in range(int(lo), int(hi) + 1)]
    else:
        regs = [r.strip() for r in rec.group(3).split(",")]
    if len(regs) != 6:
        raise PatchError(f"{NAME}: unexpected AudioRecord constructor call {rec.group(0).strip()}")
    rate, channels = regs[2], regs[3]  # (this, source, sampleRate, channelConfig, format, bufferSize)
    rest = body[rec.end():]
    if not (_overwritten_before_read(rest, rate) and _overwritten_before_read(rest, channels)):
        raise PatchError(f"{NAME}: {rate} / {channels} are read again after the AudioRecord constructor")
    conf = _one(r"^([ \t]*)invoke-virtual (\{" + ", ".join([REG] * 5) + r"\}), " + re.escape(CONFIGURE) + "$", body,
                "AAC encoder configure()")
    if not mb.start() < rec.start() < conf.start():
        raise PatchError(f"{NAME}: the microphone setup is not in the expected order")
    ind = rec.group(1)
    rec_hook = (f"{ind}{MARK}: 48 kHz stereo when the phone has it (seekpatch.Audio)\n"
                f"{ind}invoke-static {{}}, Lseekpatch/Audio;->rate()I\n{ind}move-result {rate}\n"
                f"{ind}invoke-static {{}}, Lseekpatch/Audio;->channelMask()I\n{ind}move-result {channels}\n")
    new = (body[:mb.start()]
           + f"{mb.group(1)}{MARK}: choose the recording format\n"
           + f"{mb.group(1)}invoke-static {mb.group(2)}, Lseekpatch/Audio;->minBufferSize(III)I"
           + body[mb.end():rec.start()] + rec_hook + body[rec.start():conf.start()]
           + f"{conf.group(1)}{MARK}: AAC at the recording's rate and channels, 256 kbit/s stereo\n"
           + f"{conf.group(1)}invoke-static {conf.group(2)}, Lseekpatch/Audio;->configure(Landroid/media/MediaCodec;"
             "Landroid/media/MediaFormat;Landroid/view/Surface;Landroid/media/MediaCrypto;I)V"
           + body[conf.end():])
    tree.replace_method_body(path, m, new)
    return f"{tree.rel(path)} {m.name}()", path


def _static_call(body: str, ref: str, helper: str, what: str, note: str) -> str:
    """The one invoke-virtual of ref in body, as an invoke-static of the helper with the same registers."""
    call = _one(r"^([ \t]*)invoke-virtual(/range)? (\{[^}]*\}), " + re.escape(ref) + "$", body, what)
    ind = call.group(1)
    return (body[:call.start()] + f"{ind}{MARK}: {note}\n"
            + f"{ind}invoke-static{call.group(2) or ''} {call.group(3)}, {helper}" + body[call.end():])


def _sound_clock(tree: SmaliTree, path: str) -> str:
    """The microphone's blocks and the AAC frames stamped by their samples (seekpatch.Audio.queue / .dequeue)."""
    text = tree.get(path)
    reads = [m for m in methods(text) if AUDIO_READ in m.body]
    if len(reads) != 1 or reads[0].body.count(QUEUE_INPUT) != 1:
        raise PatchError(f"{NAME}: expected one method that reads the microphone into the AAC encoder, found "
                         f"{[(m.name, m.body.count(QUEUE_INPUT)) for m in reads]}")
    body = _static_call(reads[0].body, QUEUE_INPUT, "Lseekpatch/Audio;->queue(Landroid/media/MediaCodec;IIIJI)V",
                        "queueInputBuffer of the microphone's block", "the block stamped with its first sample's time")
    body = _static_call(body, BUFFER_ARRAY, "Lseekpatch/Audio;->samples(Ljava/nio/ByteBuffer;)[B",
                        "array() of the microphone's block", "the block's bytes from its first (a direct buffer's "
                        "array holds them a few bytes in)")
    tree.replace_method_body(path, reads[0], body)
    text = tree.get(path)
    drains = [m for m in methods(text) if DEQUEUE_OUTPUT in m.body]
    if len(drains) != 1:
        raise PatchError(f"{NAME}: expected one method that takes the AAC frames, found {len(drains)}")
    tree.replace_method_body(path, drains[0], _static_call(
        drains[0].body, DEQUEUE_OUTPUT,
        "Lseekpatch/Audio;->dequeue(Landroid/media/MediaCodec;Landroid/media/MediaCodec$BufferInfo;J)I",
        "dequeueOutputBuffer of the AAC frames", "frames stamped by their samples, no configuration frame"))
    return f"timestamps by sample count, blocks copied from their first byte ({reads[0].name}(), {drains[0].name}())"


def _frame_clock(tree: SmaliTree) -> str:
    rpath, cls = render_thread(tree, NAME)
    encoders = {p for p in tree.containing('"ThermalVideoEncoder"')}
    c = re.escape(cls)
    found = []
    for p in tree.containing(cls, UPDATE_TEX_IMAGE):
        for m in methods(tree.get(p)):
            if UPDATE_TEX_IMAGE not in m.body:
                continue
            for call in re.finditer(r"^([ \t]*)invoke-virtual \{(" + REG + "), (" + REG + r")\}, (L[\w/$]+;)->([\w$]+)\("
                                    + re.escape(SURFACE_TEXTURE) + r"\)V$", m.body, re.M):
                enc_reg, tex_reg, enc_cls = call.group(2), call.group(3), call.group(4)
                if tree.path_of(enc_cls) not in encoders:
                    continue
                before = m.body[:call.start()]
                ef = re.findall(r"iget-object " + enc_reg + ", " + REG + ", " + c + r"->([\w$]+):" + re.escape(enc_cls), before)
                tf = re.findall(r"iget-object " + tex_reg + ", " + REG + ", " + c + r"->([\w$]+):" + re.escape(SURFACE_TEXTURE), before)
                if ef and tf:
                    found.append((p, m, call, f"{cls}->{ef[-1]}:{enc_cls}", f"{cls}->{tf[-1]}:{SURFACE_TEXTURE}",
                                  f"{enc_cls}->{call.group(5)}({SURFACE_TEXTURE})V"))
    if len(found) != 1:
        raise PatchError(f"{NAME}: expected one camera-frame handler that feeds the video encoder, found {len(found)}")
    cam_path, cam, call, encoder_field, texture_field, encoder_call = found[0]

    # 1. no encoder frame per phone-camera frame (the try block around it keeps an instruction)
    ind = call.group(1)
    tree.replace_method_body(cam_path, cam, cam.body[:call.start()]
                             + f"{ind}{MARK}: the encoder gets thermal frames instead\n{ind}nop" + cam.body[call.end():])
    # 2. a frame per thermal upload
    text = tree.get(rpath)
    if VIDEO_FRAME in text:
        raise PatchError(f"{NAME}: {cls} already has {VIDEO_FRAME}")
    tree.set(rpath, text.rstrip("\n") + "\n" + FRAME_METHOD.format(
        mark=MARK, frame=VIDEO_FRAME, encoder_field=encoder_field, texture_field=texture_field, encoder_call=encoder_call))
    site_path, site = upload_call(tree, rpath, cls, NAME)
    text = tree.get(site_path)
    tree.set(site_path, text[:site.end()] + f"\n{site.group(1)}{MARK}: a video frame per thermal frame\n"
             f"{site.group(1)}invoke-virtual {{{site.group(2)}}}, {cls}->{VIDEO_FRAME}\n" + text[site.end():])
    return f"{tree.rel(site_path)}: encoder frame after the thermal upload; {tree.rel(cam_path)}: none per camera frame"


def apply(tree: SmaliTree) -> list[str]:
    ensure_unpatched(tree, NAME)
    encoder = _encoder(tree)
    audio, sound_path = _audio(tree)
    stamps = _sound_clock(tree, sound_path)
    clock = _frame_clock(tree)
    tree.add_class("Lseekpatch/VideoConfig;", CONFIG_SMALI.format(
        mark=MARK, bitrate=hex(FALLBACK_BITRATE), long_side=hex(LONG_SIDE), max_bitrate=hex(MAX_BITRATE),
        mime=smali_escape(MIME), qp=hex(QP)))
    add_helpers(tree, "Video", "Audio")
    return [f"HEVC QP {QP}, long side {LONG_SIDE}: encoder {encoder}, sound {audio}, "
            f"{stamps}",
            clock, *optional_settings(tree, NAME, "VideoSettings", "Video quality")]
