"""The external tools: a Java runtime, apktool, uber-apk-signer and APKEditor, plus a per-user
signing key.

The jars are pinned by version and sha256 and downloaded from their GitHub releases on first use
into the cache directory (override with SEEK_PATCH_HOME); APKEditor, which only merges split
bundles, is fetched the first time a bundle needs it.  SEEK_PATCH_APKTOOL / SEEK_PATCH_SIGNER /
SEEK_PATCH_APKEDITOR point at local copies instead (offline use; the hash is still checked).
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass


class ToolchainError(Exception):
    pass


@dataclass(frozen=True)
class Jar:
    name: str
    version: str
    url: str
    sha256: str
    env: str

    @property
    def filename(self) -> str:
        return os.path.basename(self.url)


APKTOOL = Jar("apktool", "3.0.3",
              "https://github.com/iBotPeaches/Apktool/releases/download/v3.0.3/apktool_3.0.3.jar",
              "dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423", "SEEK_PATCH_APKTOOL")
SIGNER = Jar("uber-apk-signer", "1.3.0",
             "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar",
             "e1299fd6fcf4da527dd53735b56127e8ea922a321128123b9c32d619bba1d835", "SEEK_PATCH_SIGNER")
APKEDITOR = Jar("APKEditor", "1.4.9",
                "https://github.com/REAndroid/APKEditor/releases/download/V1.4.9/APKEditor-1.4.9.jar",
                "a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67", "SEEK_PATCH_APKEDITOR")

KEY_ALIAS = "seek-patch"
KEY_PASSWORD = "seek-patch"  # a local, per-user key: it only has to stay the same across updates


def home() -> str:
    if os.environ.get("SEEK_PATCH_HOME"):
        return os.environ["SEEK_PATCH_HOME"]
    if sys.platform == "win32":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "seek-patch")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/seek-patch")
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "seek-patch")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure_jar(jar: Jar, download: bool = True, log=print) -> str:
    """Path of a verified copy of the jar, downloading it if needed."""
    local = os.environ.get(jar.env)
    if local:
        if not os.path.isfile(local):
            raise ToolchainError(f"{jar.env}={local}: no such file")
        if sha256(local) != jar.sha256:
            raise ToolchainError(f"{jar.env}={local}: sha256 does not match {jar.name} {jar.version}")
        return local
    path = os.path.join(home(), "tools", jar.filename)
    if os.path.isfile(path) and sha256(path) == jar.sha256:
        return path
    if not download:
        raise ToolchainError(f"{jar.name} {jar.version} is not downloaded yet (run: seek-patch doctor)")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    log(f"fetch  {jar.name} {jar.version} from {jar.url}")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
    try:
        try:
            with os.fdopen(fd, "wb") as out, urllib.request.urlopen(jar.url, timeout=120) as r:
                shutil.copyfileobj(r, out)
        except OSError as e:  # URLError, timeouts, disk errors
            raise ToolchainError(f"could not download {jar.name} {jar.version}: {e}  (offline? set {jar.env} "
                                 "to a local copy)") from None
        got = sha256(tmp)
        if got != jar.sha256:
            raise ToolchainError(f"{jar.name}: downloaded file has sha256 {got}, expected {jar.sha256}")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def _java_works(java: str) -> str | None:
    """`java -version` output if this java runs, else None."""
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (r.stderr or r.stdout) if r.returncode == 0 else None


def find_java() -> tuple[str, str]:
    """(java executable, version line).  macOS ships a /usr/bin/java stub that only prints an
    install prompt, so every candidate is actually run."""
    candidates = []
    if os.environ.get("JAVA_HOME"):
        candidates.append(os.path.join(os.environ["JAVA_HOME"], "bin", "java"))
    if sys.platform == "darwin":
        try:
            jh = subprocess.run(["/usr/libexec/java_home"], capture_output=True, text=True, timeout=30).stdout.strip()
            if jh:
                candidates.append(os.path.join(jh, "bin", "java"))
        except OSError:
            pass
        candidates += ["/opt/homebrew/opt/openjdk/bin/java", "/usr/local/opt/openjdk/bin/java"]
    if shutil.which("java"):
        candidates.append(shutil.which("java"))
    for java in candidates:
        out = _java_works(java)
        if out:
            return java, out.strip().splitlines()[0]
    hint = {"darwin": "brew install openjdk", "linux": "apt install default-jdk  (or your distro's JDK)"}
    raise ToolchainError("no working Java found; install a JDK 11+ (" + hint.get(sys.platform, "e.g. Temurin") +
                         ") or set JAVA_HOME")


def java_major(version_line: str) -> int:
    m = re.search(r'version "(\d+)(?:\.(\d+))?', version_line)
    if not m:
        return 0
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major  # "1.8.0_x" -> 8


@dataclass
class Toolchain:
    java: str
    java_version: str
    apktool: str
    signer: str
    download: bool = True

    @classmethod
    def load(cls, download: bool = True, log=print) -> Toolchain:
        java, version = find_java()
        if java_major(version) < 11:
            raise ToolchainError(f"{java}: {version} -- Java 11 or newer is needed")
        return cls(java, version, ensure_jar(APKTOOL, download, log), ensure_jar(SIGNER, download, log), download)

    def merger(self, log=print) -> str:
        """APKEditor, for split bundles only: fetched on first use."""
        return ensure_jar(APKEDITOR, self.download, log)

    def run_jar(self, jar: str, args: list[str], what: str) -> str:
        r = subprocess.run([self.java, "-jar", jar, *args], capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stdout[-3000:] + r.stderr[-3000:]).strip()
            raise ToolchainError(f"{what} failed (exit {r.returncode}):\n{tail}")
        return r.stdout

    def keytool(self) -> str | None:
        exe = "keytool.exe" if platform.system() == "Windows" else "keytool"
        k = os.path.join(os.path.dirname(os.path.realpath(self.java)), exe)
        return k if os.path.isfile(k) else shutil.which("keytool")

    def keystore(self, log=print) -> str:
        """The per-user signing key, created on first use.  There is deliberately no fallback to a
        shared debug key: anyone holding that key could sign an "update" over the patched app."""
        path = os.path.join(home(), "signing-key.jks")
        if os.path.isfile(path):
            return path
        keytool = self.keytool()
        if not keytool:
            raise ToolchainError("keytool not found -- it ships with every JDK; install a JDK (not just a JRE)")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        log(f"key    creating your signing key {path}")
        r = subprocess.run([keytool, "-genkeypair", "-keystore", path, "-storetype", "PKCS12",
                            "-storepass", KEY_PASSWORD, "-keypass", KEY_PASSWORD, "-alias", KEY_ALIAS,
                            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                            "-dname", "CN=seek-patch local key"], capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolchainError(f"keytool failed: {r.stderr.strip()}")
        return path
