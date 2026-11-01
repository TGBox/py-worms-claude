import os
import sys
from pathlib import Path

import PyInstaller.__main__

from src.core.native import library_name


def main() -> None:
    args = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else [
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--paths",
            ".",
            "--add-data",
            "assets;assets",
            "src/main.py",
            "--name",
            "py-worms-claude",
        ]
    )
    kernel = Path("src") / "core" / "_native" / library_name()
    if len(sys.argv) <= 1 and kernel.is_file():
        # Ship the Rust physics kernel (ADR-0008); without it the game uses the Python fallback.
        args += ["--add-binary", f"{kernel}{os.pathsep}."]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
