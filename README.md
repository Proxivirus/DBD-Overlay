# DBD Overlay

Tracks streaks to show on OBS

## Download

1. Download `dbd_overlay.exe` from [Releases](https://github.com/Proxivirus/DBD-Overlay/releases)
2. Double-click to open
3. Follow instructions at bottom to add to OBS
4. Check wiki for more info

## Compile from source

```bash
# 1. Clone
git clone https://github.com/Proxivirus/DBD-Overlay
cd dbd-overlay

# 2. Compile 
python compile_overlay.py
# or custom output foler
python compile_overlay.py --output ./my_build

# clean tmp directory
python compile_overlay.py --clean
```

Requirements: Python 3.10+, pip, internet for first-time `Pillow`/`pyinstaller` download.
