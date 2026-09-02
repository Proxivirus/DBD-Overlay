# biggest spaghetti code of my whole life
# program checks for updates on GitHub repo
# if update found, download new dbd_overlay.exe and update_handler.exe to the save folder in a new folder called Temp
# add location.txt to the temp folder and inside write the current location of the old .exe
# Open update_handler.exe and close old dbd_overlay version
# have update_handler move the old .exe from where it is currently to the temp folder and add .bak to the end of the file extension
# update_handler move the new .exe to the location the old one was
# update_handler launch the new .exe and close itself
# when new .exe launches it checks Temp to see if anything is in there, and if it is deletes it

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

# my asenine save folder bs
try:
    from dbd_controller import DATA_ROOT, PROG_ROOT, BUNDLED_ROOT
except Exception:
    # fallback if for some reason its running standalone
    if getattr(sys, "frozen", False):
        PROG_ROOT = Path(sys.executable).resolve().parent  # type: ignore
    else:
        PROG_ROOT = Path(__file__).resolve().parent
    import pathlib as _pl

    BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", PROG_ROOT))
    try:
        docs = Path.home() / "Documents" / "DBD Overlay"
        docs.mkdir(parents=True, exist_ok=True)
        DATA_ROOT = docs
    except Exception:
        DATA_ROOT = PROG_ROOT

GITHUB_REPO = "Proxivirus/DBD-Overlay"
HANDLER_REPO = "Proxivirus/DBD-Overlay-Updater"
USER_AGENT = "DBD-Overlay-Updater/1.0"

# what we look for in the release assets
MAIN_ASSET_NAMES = ["dbd_overlay.exe", "rexy_dbd_overlay.exe"] # rexy one is a holdover from testing
HANDLER_ASSET_NAMES = ["update_handler.exe"]


def _get_current_version():
    # read version.txt (copied from about_ui)
    for base in (DATA_ROOT, PROG_ROOT, BUNDLED_ROOT, Path(__file__).resolve().parent):
        try:
            cand = base / "version.txt"
            if cand.is_file():
                text = cand.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    return text.splitlines()[0].strip()
        except Exception:
            continue
    return "v0.0.0"


def _get_exe_path():
    # find current location of program .exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    # theres some shit here from testing and i dont remember whats what
    # so its all gonna stay gg
    cand = PROG_ROOT / "dbd_overlay.exe"
    if cand.is_file():
        return cand.resolve()
    return (PROG_ROOT / "dbd_overlay.exe").resolve()


def _get_temp_dir() -> Path:
    p = DATA_ROOT / "Temp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fetch_github_api(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8", "replace")
        return json.loads(data)


def fetch_latest_release(repo=GITHUB_REPO):
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        return _fetch_github_api(api)
    except urllib.error.HTTPError:
        return None  # 404 prob thats rough
    except Exception:
        return None


def is_newer_version(current, latest):
    # its probably fine just to check if current version != latest version
    # this surely wont come back to bite me in the ass later
    c = current.strip()
    l = latest.strip()
    if not l:
        return False
    if not c:
        return True
    if c == l:
        return False
    return True


def check_for_updates(current_version=None, repo=GITHUB_REPO, status_cb=None):
    # returns (available, info, cur, latest)
    if status_cb:
        try:
            status_cb("Checking for updates...")
        except Exception:
            pass

    cur = current_version or _get_current_version()
    info = fetch_latest_release(repo)
    if info is None:
        if status_cb:
            try:
                status_cb("Failed to check for updates")
            except Exception:
                pass
        return False, None, cur, ""

    latest_tag = str(info.get("tag_name") or info.get("name") or "").strip()
    if not latest_tag:
        return False, None, cur, ""

    available = is_newer_version(cur, latest_tag)
    if status_cb:
        try:
            if available:
                status_cb(f"Update available: {latest_tag}")
            else:
                status_cb("No updates found")
        except Exception:
            pass

    return available, info, cur, latest_tag


def _find_asset_url(release_info, wanted_names):
    # find download url for wanted exe names
    assets = release_info.get("assets") or []
    # map lower name -> url
    lower_map: Dict[str, str] = {}
    for a in assets:
        try:
            name = str(a.get("name") or "").strip()
            url = str(a.get("browser_download_url") or "").strip()
            if name and url:
                lower_map[name.lower()] = url
        except Exception:
            continue
    for wanted in wanted_names:
        url = lower_map.get(wanted.lower())
        if url:
            return url
    # fallback: contains check (i dont remember but looks good bro)
    for wanted in wanted_names:
        wl = wanted.lower()
        for name, url in lower_map.items():
            if wl in name:
                return url
    return None


def download_file(url, dest, status_cb=None):
    # try 3 times writes to .tmp then replaces
    tmp = dest.with_name(dest.name + ".tmp")
    for attempt in range(3):
        try:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            if tmp.stat().st_size == 0:
                raise RuntimeError("Empty download")
            try:
                tmp.replace(dest)
            except Exception:
                import os

                os.replace(str(tmp), str(dest))
            return True
        except (OSError, RuntimeError) as e:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
                continue
            if status_cb:
                try:
                    status_cb(f"Download failed: {e}")
                except Exception:
                    pass
            return False
    return False


def prepare_update(release_info, handler_release_info=None, status_cb=None, progress_cb=None):
    # downloads to Temp writes location.txt returns Temp path or None
    temp_dir = _get_temp_dir(
    # clean old Temp files first
    try:
        if temp_dir.is_dir():
            for p in list(temp_dir.iterdir()):
                try:
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        shutil.rmtree(p)
                except Exception:
                    pass
    except Exception:
        pass

    temp_dir.mkdir(parents=True, exist_ok=True)

    # find main exe
    main_url = _find_asset_url(release_info, MAIN_ASSET_NAMES)
    if not main_url:
        # looking for any .exe in releases is probably fine
        assets = release_info.get("assets") or []
        for a in assets:
            name = str(a.get("name") or "")
            if name.lower().endswith(".exe") and "handler" not in name.lower():
                main_url = str(a.get("browser_download_url") or "")
                if main_url:
                    break
    if not main_url:
        if status_cb:
            try:
                status_cb("Main exe not found in release")
            except Exception:
                pass
        return None

    # legacy testing code
    handler_url: Optional[str] = None
    # handler might be in same release
    h_info = handler_release_info or release_info
    handler_url = _find_asset_url(h_info, HANDLER_ASSET_NAMES)
    if not handler_url and h_info is not release_info:
        # try main release for handler too
        handler_url = _find_asset_url(release_info, HANDLER_ASSET_NAMES)

    # grab main exe
    main_dest = temp_dir / "dbd_overlay.exe"
    if status_cb:
        try:
            status_cb("Downloading update...")
        except Exception:
            pass
    if progress_cb:
        try:
            progress_cb(0, 2, "dbd_overlay.exe")
        except Exception:
            pass

    ok = download_file(main_url, main_dest, status_cb)
    if not ok:
        return None

    if progress_cb:
        try:
            progress_cb(1, 2, "update_handler.exe")
        except Exception:
            pass

    # grab handler if found (old)s
    # absolutely brilliant ok2 variable name btw
    if handler_url:
        handler_dest = temp_dir / "update_handler.exe"
        ok2 = download_file(handler_url, handler_dest, status_cb)
        if not ok2:
            # might already have one
            try:
                if handler_dest.is_file():
                    handler_dest.unlink()
            except Exception:
                pass
    else:
        # no handler in release - dev mode will copy local one later
        if status_cb:
            try:
                status_cb("Handler not found in release, using existing")
            except Exception:
                pass

    # write where the old exe lives so handler knows what to replace
    exe_path = _get_exe_path()
    try:
        (temp_dir / "location.txt").write_text(str(exe_path), encoding="utf-8")
    except Exception as e:
        if status_cb:
            try:
                status_cb(f"Failed to write location: {e}")
            except Exception:
                pass
        return None

    if progress_cb:
        try:
            progress_cb(2, 2, "done")
        except Exception:
            pass

    return temp_dir


def launch_handler_and_exit(temp_dir, app=None):
    # start handler and quit this exe
    handler_path = temp_dir / "update_handler.exe"
    # hope to god this never happens
    if not handler_path.is_file():
        for base in (PROG_ROOT, BUNDLED_ROOT, Path(__file__).resolve().parent):
            cand = base / "update_handler.exe"
            if cand.is_file():
                # copy to Temp
                try:
                    shutil.copy2(str(cand), str(handler_path))
                    break
                except Exception:
                    continue
    if not handler_path.is_file():
        # im not gonna touch this but also this is gonna be impossible on release
        py_handler = Path(__file__).resolve().parent / "update_handler.py"
        if py_handler.is_file():
            try:
                # run via python
                subprocess.Popen([sys.executable, str(py_handler)], cwd=str(temp_dir), close_fds=True)
                # close tk
                if app is not None:
                    try:
                        app.destroy()
                    except Exception:
                        pass
                sys.exit(0)
            except Exception:
                pass
        raise FileNotFoundError(f"Handler not found at {handler_path}")

    # launch detached so it stays open after closing ui
    try:
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(
                [str(handler_path)],
                cwd=str(temp_dir),
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            subprocess.Popen([str(handler_path)], cwd=str(temp_dir), start_new_session=True, close_fds=True)
    except Exception as e:
        # fallback without flags
        subprocess.Popen([str(handler_path)], cwd=str(temp_dir), close_fds=True)

    # quit this process to let the handler cook
    if app is not None:
        try:
            # tk needs destroy apparently
            app.destroy()
        except Exception:
            try:
                app.quit()
            except Exception:
                pass
    # huh me? pff just hanging around
    import os

    try:
        sys.exit(0)
    finally:
        os._exit(0)


def cleanup_temp():
    # new exe calls this on launch to delete Temp
    try:
        temp_dir = DATA_ROOT / "Temp"
        if temp_dir.is_dir():
            # check for files
            has_files = any(temp_dir.iterdir())
            if has_files:
                # delete detected fles
                shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# local testing dogshit ignore this ai slop code
# ---------------------------------------------------------------------------

def _create_dummy_new_exes(temp_dir, version="v9.9.9"):
    # test helper makes fake exes so we can test Temp logic without github
    temp_dir.mkdir(parents=True, exist_ok=True)
    # create dummy dbd_overlay.exe as a copy of current exe or this file
    dummy_main = temp_dir / "dbd_overlay.exe"
    try:
        # try to copy current exe if frozen, else create a dummy file
        if getattr(sys, "frozen", False):
            src = Path(sys.executable)
            if src.is_file():
                shutil.copy2(str(src), str(dummy_main))
            else:
                dummy_main.write_text(f"dummy exe {version}", encoding="utf-8")
        else:
            # Create a dummy file that represents new exe
            # For testing, we can copy the current python file or create a text
            dummy_main.write_text(f"dummy new exe version {version}", encoding="utf-8")
            # Also need to make it look like exe for handler test (handler just moves file, doesn't execute)
    except Exception:
        try:
            dummy_main.write_text(f"dummy {version}", encoding="utf-8")
        except Exception:
            pass

    dummy_handler = temp_dir / "update_handler.exe"
    try:
        # Copy current handler exe if exists, else copy this file's handler
        # For test, just create dummy
        dummy_handler.write_text(f"dummy handler {version}", encoding="utf-8")
    except Exception:
        pass


def test_prepare_local_update(version="v9.9.9-test"):
    # local test - no github hit
    temp_dir = _get_temp_dir()
    # Clean
    if temp_dir.is_dir():
        for p in list(temp_dir.iterdir()):
            try:
                if p.is_file():
                    p.unlink()
                else:
                    shutil.rmtree(p)
            except Exception:
                pass
    _create_dummy_new_exes(temp_dir, version)
    exe_path = _get_exe_path()
    (temp_dir / "location.txt").write_text(str(exe_path), encoding="utf-8")
    return temp_dir


def test_run_handler_simulation():
    # simulates what update_handler.exe does - moves old->bak, new->old
    # useful for dev, returns True if moves looked right
    import tempfile

    # Create a temp old exe location
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        old_exe = tmp_path / "dbd_overlay.exe"
        old_exe.write_text("old version", encoding="utf-8")
        # Prepare Temp as DATA_ROOT/Temp with dummy new
        temp_dir = _get_temp_dir()
        # Clean
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        new_exe = temp_dir / "dbd_overlay.exe"
        new_exe.write_text("new version", encoding="utf-8")
        new_handler = temp_dir / "update_handler.exe"
        new_handler.write_text("handler", encoding="utf-8")
        (temp_dir / "location.txt").write_text(str(old_exe), encoding="utf-8")

        # Now simulate handler's move logic directly
        # Move old to bak
        old_bak = temp_dir / (old_exe.name + ".bak")
        old_exe.replace(old_bak)
        new_exe.replace(old_exe)

        # Check
        if not old_exe.is_file():
            return False
        if old_exe.read_text(encoding="utf-8") != "new version":
            return False
        if not old_bak.is_file():
            return False
        if old_bak.read_text(encoding="utf-8") != "old version":
            return False

        # Cleanup: simulate new exe's Temp cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DBD Overlay updater")
    parser.add_argument("--check", action="store_true", help="Check for updates")
    parser.add_argument("--test-prepare", action="store_true", help="Prepare dummy Temp for testing")
    parser.add_argument("--test-handler", action="store_true", help="Run handler simulation test")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup Temp")
    parser.add_argument("--current", type=str, default=None, help="Override current version")
    args = parser.parse_args()

    if args.cleanup:
        cleanup_temp()
        print("Cleaned")
    elif args.test_prepare:
        p = test_prepare_local_update()
        print(f"Prepared {p}, location.txt -> {open(p / 'location.txt').read().strip()}")
        print(f"Files: {list(p.iterdir())}")
    elif args.test_handler:
        ok = test_run_handler_simulation()
        print("Handler simulation:", "PASS" if ok else "FAIL")
    elif args.check:
        cur = args.current or _get_current_version()
        avail, info, cur2, latest = check_for_updates(cur)
        print(f"Current: {cur2}, Latest: {latest}, Available: {avail}")
        if avail and info:
            print(f"Assets: {[a.get('name') for a in info.get('assets',[])]}")
    else:
        parser.print_help()
