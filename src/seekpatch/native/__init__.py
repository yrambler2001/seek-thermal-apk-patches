"""Native libraries built by helpers/build_native.py from helpers/native (committed, so patching needs
no NDK).  The smart_smoothing patch adds them to lib/<abi>/ with SmaliTree.add_native_library()."""
from __future__ import annotations

from importlib import resources

SMOOTH = "libseekpatch_smooth.so"
ABIS = ("arm64-v8a", "armeabi-v7a")
"""The ABIs the libraries are built for."""


def library(abi: str, name: str = SMOOTH) -> bytes:
    """The built library for one ABI."""
    if abi not in ABIS:
        raise KeyError(f"no {name} for {abi} (built: {', '.join(ABIS)})")
    data = resources.files(__name__).joinpath(abi, name).read_bytes()
    if data[:4] != b"\x7fELF":
        raise ValueError(f"{abi}/{name} is not an ELF file -- run helpers/build_native.py")
    return data
