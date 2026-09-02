# compiles program to .exe

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "dist"
# stops the compile from cluttering up the folder
WORK_DIR = Path(os.environ.get("TEMP", str(PROJECT_DIR / "build"))) / "dbd_build"
SPEC_DIR = WORK_DIR

# couple settiongs
ENTRY = PROJECT_DIR / "dbd_ui.py"
EXE_NAME = "dbd_overlay"
ICON = PROJECT_DIR / "icon" / "icon.ico"

# most of these arent even included anymore but theyre here since i use for testing occasionally
BUNDLES = [
    (PROJECT_DIR / "index.html", "."),
    (PROJECT_DIR / "assets", "assets"),
    (PROJECT_DIR / "config.json", "."),
    (PROJECT_DIR / "killer_wrs.json", "."),
    (PROJECT_DIR / "killer_pbs.json", "."),
    (PROJECT_DIR / "survivor_wrs.json", "."),
    (PROJECT_DIR / "survivor_pbs.json", "."),
    (PROJECT_DIR / "global_streak.json", "."),
    (PROJECT_DIR / "version.txt", "."),
]

# allows skip when not included
OPTIONAL = {"killer_wrs.json", "killer_pbs.json", "survivor_wrs.json", "survivor_pbs.json", "global_streak.json"}


def _sep() -> str:
    return ";" if os.name == "nt" else ":"


def ensure_dependencies():
    # make sure deps are installed, if not install
    missing = []
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")

    try:
        import PyInstaller
    except ImportError:
        missing.append("pyinstaller")

    if not missing:
        print(f"[deps] All dependencies present (Pillow, PyInstaller)")
        return

    print(f"[deps] Missing: {', '.join(missing)} - installing via pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    except Exception as e:
        print(f"[deps] pip upgrade failed (continuing): {e}")

    # install missing
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + missing
    # this is some linux bs that i may or may not deal with later
    # apparently linux needs --break-system-packages sometimes
    try:
        print(f"[deps] Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("[deps] Retrying with --break-system-packages")
        cmd.append("--break-system-packages")
        subprocess.check_call(cmd)

    # verify again
    # this shouldnt happen every guys right?
    # all this defensive programming all over every py file
    # and yet i GUARANTEE that 5 seconds into someone using ts
    # its gonna break anyway
    try:
        import PIL
        import PyInstaller
        print("[deps] Dependencies installed successfully")
    except ImportError as e:
        print(f"[deps] Still missing after install: {e}")
        print("Please manually run: python -m pip install Pillow pyinstaller")
        sys.exit(1)


def clean() -> None:
    for p in [PROJECT_DIR / "build", WORK_DIR, SPEC_DIR, PROJECT_DIR / f"{EXE_NAME}.spec"]:
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                print(f"[clean] Removed {p}")
            elif p.is_file():
                p.unlink(missing_ok=True)
                print(f"[clean] Removed {p}")
        except Exception as e:
            print(f"[clean] Failed to remove {p}: {e}")


def build(output_dir: Path | None = None) -> None:
    ensure_dependencies()

    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    # kill running exe on windows so file isn't locked
    if os.name == "nt":
        try:
            subprocess.run(["TASKKILL", "/F", "/IM", f"{EXE_NAME}.exe"], capture_output=True)
        except Exception:
            pass

    # build --add-data args
    add_data_args = []
    for src, dest in BUNDLES:
        if not src.exists():
            if src.name in OPTIONAL:
                print(f"[build] Skipping missing optional {src.name}")
                continue
            print(f"[build] Warning: missing {src} (will skip)")
            continue
        sep = _sep()
        add_data_args.extend(["--add-data", f"{src}{sep}{dest}"])

    icon_args = []
    if ICON.is_file():
        icon_args = ["-i", str(ICON)]
    else:
        print(f"[build] Warning: icon not found at {ICON}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        EXE_NAME,
        "--distpath",
        str(out),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
    ] + add_data_args + icon_args + [str(ENTRY)]

    print(f"[build] Project: {PROJECT_DIR}")
    print(f"[build] Output : {out}")
    print(f"[build] Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"[build] FAILED with exit {e.returncode}")
        sys.exit(e.returncode)

    exe_path = out / f"{EXE_NAME}.exe" if os.name == "nt" else out / EXE_NAME
    if exe_path.is_file():
        print(f"[build] Complete: {exe_path} ({exe_path.stat().st_size} bytes)")
    else:
        # for linux but havent even tried once on linux so for later
        alt = out / EXE_NAME
        if alt.is_file():
            print(f"[build] Complete: {alt}")
        else:
            print("[build] Warning: exe not found after build")
            print(f"[build] Dist contents: {list(out.iterdir())}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Compile DBD Overlay")
    p.add_argument("--output", "-o", type=str, default=None, help="output dir (default ./dist)")
    p.add_argument("--clean", action="store_true", help="clean build artifacts and exit")
    args = p.parse_args()

    if args.clean:
        clean()
        sys.exit(0)

    build(Path(args.output) if args.output else None)
