"""Optional Rust kernel for the hot physics loops (see ADR-0008).

The kernel is a plain C-ABI library built from `native/` (`uv run build-native`) and loaded with
ctypes. When it is missing, or `PY_WORMS_NATIVE=0` is set, `kernel` is None and the pure Python
reference implementations are used. Both backends are bit-identical (tests/test_native.py).
"""

import ctypes
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.core.constants import PROJECTILE_MAX_AGE, WORM_RADIUS
from src.core.geometry import CIRCLE_POINTS

KERNEL_VERSION = 4
LIBRARY_ENV = "PY_WORMS_NATIVE_LIB"
DISABLE_ENV = "PY_WORMS_NATIVE"

# Projectile state layout shared with native/src/lib.rs.
(
    P_X,
    P_Y,
    P_VX,
    P_VY,
    P_AGE,
    P_FUSE,
    P_HAS_FUSE,
    P_BOUNCE,
    P_HAS_BOUNCE,
    P_WIND,
    P_ASLEEP,
    P_OWNER,
) = range(12)
P_LEN = 12
RESULT_NAMES = {0: None, 1: "explode", 2: "gone"}

_double = ctypes.c_double
_int = ctypes.c_int32
_ptr = ctypes.c_void_p


def library_name() -> str:
    if sys.platform == "win32":
        return "wormkernel.dll"
    if sys.platform == "darwin":
        return "libwormkernel.dylib"
    return "libwormkernel.so"


def candidate_paths() -> list[Path]:
    paths: list[Path] = []
    if os.environ.get(LIBRARY_ENV):
        paths.append(Path(os.environ[LIBRARY_ENV]))
    here = Path(__file__).resolve().parent
    paths.append(here / "_native" / library_name())
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        paths.append(Path(bundle) / library_name())
    paths.append(here.parents[1] / "native" / "target" / "release" / library_name())
    return paths


def _bind(lib: ctypes.CDLL) -> None:
    signatures = {
        "wk_version": (_int, []),
        "wk_init": (_int, [_ptr, _int, _double, _double]),
        "wk_circle_collides": (_int, [_ptr, _int, _int, _double, _double, _double]),
        "wk_normal_at": (None, [_ptr, _int, _int, _double, _double, _int, _ptr]),
        "wk_set_circle": (None, [_ptr, _int, _int, _double, _double, _double, ctypes.c_uint8]),
        "wk_body_collides": (
            _int,
            [_ptr, _int, _int, _double, _double, _double, _double, _double, _ptr, _int, _int, _int],
        ),
        "wk_fly": (
            _int,
            [
                _ptr,
                _int,
                _int,
                _ptr,
                _double,
                _double,
                ctypes.c_int64,
                _double,
                _ptr,
                _int,
                _int,
                _int,
                _ptr,
            ],
        ),
        "wk_walk": (
            None,
            [_ptr, _int, _int, _ptr, _int, _double, _int, _int, _int, _ptr, _int, _int, _int, _ptr],
        ),
        "wk_ground_mask": (None, [_ptr, _int, _int, _ptr, _int, _ptr]),
        "wk_step_projectiles": (
            _int,
            [
                _ptr,
                _int,
                _int,
                _ptr,
                _int,
                _int,
                _double,
                _double,
                _double,
                _double,
                _double,
                _ptr,
                _int,
            ],
        ),
        "wk_simulate": (
            None,
            [
                _ptr,
                _int,
                _int,
                _ptr,
                _int,
                _double,
                _double,
                _double,
                _double,
                _double,
                _ptr,
                _int,
                _double,
                _ptr,
            ],
        ),
    }
    for name, (restype, argtypes) in signatures.items():
        function = getattr(lib, name)
        function.restype = restype
        function.argtypes = argtypes


def load() -> ctypes.CDLL | None:
    """Load and initialise the kernel; None when unavailable or disabled."""
    if os.environ.get(DISABLE_ENV, "1") == "0":
        return None
    for path in candidate_paths():
        if not path.is_file():
            continue
        try:
            lib = ctypes.CDLL(str(path))
            _bind(lib)
        except (OSError, AttributeError):
            continue
        if lib.wk_version() != KERNEL_VERSION:
            continue
        flat = [value for point in CIRCLE_POINTS for value in point]
        points = (_double * len(flat))(*flat)
        if lib.wk_init(points, len(CIRCLE_POINTS), float(WORM_RADIUS), PROJECTILE_MAX_AGE) != 1:
            continue
        return lib
    return None


kernel: ctypes.CDLL | None = load()
_loaded = kernel


def backend_name() -> str:
    return "Rust" if kernel is not None else "Python"


@contextmanager
def disabled() -> Iterator[None]:
    """Temporarily force the Python reference implementation (tests, benchmarks)."""
    global kernel
    previous, kernel = kernel, None
    try:
        yield
    finally:
        kernel = previous


def available() -> bool:
    return _loaded is not None


# ------------------------------------------------------------------------------ helpers
def buffer_address(data: bytearray) -> int:
    """Address of a bytearray's storage (the array must not be resized afterwards)."""
    return ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data))


def doubles(values: list[float]) -> ctypes.Array:
    return (_double * max(1, len(values)))(*values)


class Scratch:
    """Reusable double buffers: building ctypes arrays per call costs more than the call."""

    def __init__(self) -> None:
        self._buffers: dict[str, ctypes.Array] = {}

    def fill(self, name: str, values: list[float]) -> ctypes.Array:
        buffer = self._buffers.get(name)
        if buffer is None or len(buffer) < len(values):
            buffer = (_double * max(16, 2 * len(values)))()
            self._buffers[name] = buffer
        buffer[: len(values)] = values
        return buffer

    def get(self, name: str, size: int) -> ctypes.Array:
        buffer = self._buffers.get(name)
        if buffer is None or len(buffer) < size:
            buffer = (_double * max(16, 2 * size))()
            self._buffers[name] = buffer
        return buffer


scratch = Scratch()


def pack_projectile(p: "Projectile", owner_index: int = -1) -> list[float]:  # noqa: F821
    return [
        p.x,
        p.y,
        p.vx,
        p.vy,
        p.age,
        p.fuse if p.fuse is not None else 0.0,
        1.0 if p.fuse is not None else 0.0,
        p.bounce if p.bounce is not None else 0.0,
        1.0 if p.bounce is not None else 0.0,
        p.wind_factor,
        1.0 if p.asleep else 0.0,
        float(owner_index),
    ]


def unpack_projectile(p: "Projectile", state: ctypes.Array, offset: int = 0) -> None:  # noqa: F821
    p.x = state[offset + P_X]
    p.y = state[offset + P_Y]
    p.vx = state[offset + P_VX]
    p.vy = state[offset + P_VY]
    p.age = state[offset + P_AGE]
    if p.fuse is not None:
        p.fuse = state[offset + P_FUSE]
    p.asleep = state[offset + P_ASLEEP] != 0.0
