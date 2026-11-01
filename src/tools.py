import subprocess
import sys


def format_code() -> None:
    sys.exit(subprocess.run(["ruff", "format", "."], check=False).returncode)


def lint_code() -> None:
    sys.exit(subprocess.run(["ruff", "check", "."], check=False).returncode)


def build_native() -> None:
    """Build the Rust physics kernel and copy it next to src/core/native.py (ADR-0008)."""
    import shutil
    from pathlib import Path

    from src.core.native import library_name

    root = Path(__file__).resolve().parent.parent
    manifest = root / "native" / "Cargo.toml"
    if shutil.which("cargo") is None:
        print("cargo nicht gefunden: Rust über https://rustup.rs installieren.")
        sys.exit(1)
    command = ["cargo", "build", "--release", "--manifest-path", str(manifest)]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)
    built = root / "native" / "target" / "release" / library_name()
    target = root / "src" / "core" / "_native" / library_name()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    print(f"Rust-Kernel gebaut: {target}")
