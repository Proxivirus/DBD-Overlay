# i didnt properly comment this when i was writing it
# so i had to go back and comment touchup before release
# which means some things i just genuinely dont remember
# and the comments reflect that. sorry random person reading this
# trying to understand my code
# main logic for everything

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import json
from overlay_server import PORT, create_server
from storage import load_json, save_json
from update_characters import update_killers, update_survivors


if getattr(sys, "frozen", False):
    PROG_ROOT = Path(sys.executable).resolve().parent
else:
    PROG_ROOT = Path(__file__).resolve().parent

BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", PROG_ROOT))

# set/get save data in Documents/DBD Overlay
def _get_data_root() -> Path:
    try:
        docs = Path.home() / "Documents" / "DBD Overlay"
        docs.mkdir(parents=True, exist_ok=True)
        return docs
    except Exception:
        try:
            # this is for if it fails to write but if it does idek bro bc
            # other shit assumes it doesnt fail and too im lazy to change everything else
            return PROG_ROOT
        except Exception:
            return Path.home() / "DBD Overlay"

DATA_ROOT = _get_data_root()

# get config
def _get_bundled_config_path() -> Path | None:
    for base in (PROG_ROOT, BUNDLED_ROOT):
        cand = base / "config.json"
        try:
            if cand.is_file():
                return cand
        except Exception:
            continue
    return None


def _load_effective_config() -> Dict[str, Any]:
    # try save folder then bundled
    # bundled beceause its good for defaults on first launch
    # config in save folder 
    try:
        if CONFIG_PATH.is_file():
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except (OSError, ValueError):
        pass
    except Exception:
        pass
    # default config in .exe
    for base in (PROG_ROOT, BUNDLED_ROOT):
        cand = base / "config.json"
        try:
            if cand.is_file():
                with open(cand, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        return data
        except Exception:
            continue
    return {}


def _migrate_from_prog_root() -> None:
    # before pub release, saves data lived next to exe, but now its in Documents/DBD Overlay
    # this copies all the save data over into the new spot if it finds it
    # literally wrote this just for you Rexy yw
    try:
        if DATA_ROOT == PROG_ROOT:
            return
        import shutil
        for name in ["config.json", "killer_wrs.json", "killer_pbs.json", "survivor_wrs.json", "survivor_pbs.json", "global_streak.json"]:
            dst = DATA_ROOT / name
            if dst.exists():
                continue
            copied = False
            for base in (PROG_ROOT, BUNDLED_ROOT):
                src = base / name
                if src.is_file():
                    try:
                        shutil.copy2(src, dst)
                        copied = True
                        break
                    except Exception:
                        continue
            if copied:
                continue
        for sub in ["killer_icons", "survivor_icons"]:
            try:
                (DATA_ROOT / "assets" / sub).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    except Exception:
        pass

_migrate_from_prog_root()

# get most optimal asset folder
def _asset_dir(name: str) -> Path:
    for base in (DATA_ROOT, PROG_ROOT, BUNDLED_ROOT):
        path = base / "assets" / name
        if path.exists():
            return path
    return DATA_ROOT / "assets" / name


ICONS_DIR = _asset_dir("killer_icons")
SURV_ICONS_DIR = _asset_dir("survivor_icons")
PALETTE_EMOJI = _asset_dir("palette_emoji.png")
GITHUB_LOGO = _asset_dir("GitHub_Lockup_White_Clearspace.png")
CONFIG_PATH = DATA_ROOT / "config.json"
WRS_PATH = DATA_ROOT / "killer_wrs.json"
PBS_PATH = DATA_ROOT / "killer_pbs.json"
SWRS_PATH = DATA_ROOT / "survivor_wrs.json"
SPBS_PATH = DATA_ROOT / "survivor_pbs.json"
GLOBAL_PATH = DATA_ROOT / "global_streak.json"
OPACITY_PREVIEW_PATH = DATA_ROOT / "opacity_preview.txt"
POLL_MS = 500


def format_name(stem: str) -> str:
    core = stem.split("_", 1)[1].replace("_Portrait", "")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", core).upper()


def discover_characters(directory: Path, pattern: str) -> Dict[str, str]:
    return {format_name(path.stem): path.name for path in sorted(directory.glob(pattern))}


class OverlayController:
    # wholebunchofdogshit.exe
    # its so fat good luck later me

    def __init__(self) -> None:
        self.killers = discover_characters(ICONS_DIR, "K*_Portrait.png")
        self.survivors = discover_characters(SURV_ICONS_DIR, "S*_Portrait.png")
        self.wrs = load_json(WRS_PATH, {})
        self.pbs = load_json(PBS_PATH, {})
        self.swrs = load_json(SWRS_PATH, {})
        self.spbs = load_json(SPBS_PATH, {})
        self.global_data = load_json(GLOBAL_PATH, {"current": 0, "personalBest": 0})
        if not isinstance(self.global_data, dict):
            self.global_data = {"current": 0, "personalBest": 0}
        self.global_data.setdefault("current", 0)
        self.global_data.setdefault("personalBest", 0)
        save_json(GLOBAL_PATH, self.global_data)

        self.k_names = sorted(set(self.killers) | set(self.wrs))
        self.s_names = sorted(set(self.survivors) | set(self.swrs))
        self._ensure_data()

        self.killer = None
        self.survivor = None
        self.active_role = "killer"
        self.streak_mode = "character"
        self.current = 0
        self.pb = 0
        self.wr = None
        self.bg_color = "#000000"
        self.bg_opacity = 0
        self.poll_milliseconds = POLL_MS
        self.overlay_accent_color = "#d10f16"
        self.overlay_port = PORT
        self.show_status_messages = True
        self.language = "en_us"
        self.server = None
        self.overlay_url = ""
        self.restore_from_config()
        # scuffed but when mid drag i dont want it to save
        self.clear_opacity_preview()
        # write config on first run
        if not CONFIG_PATH.is_file():
            try:
                self.write_config()
            except Exception:
                pass
            # im looking at this and i dont remember why this is here
            # maybe im just stupid but config shoulda been written 
            # 100% of the time before this no?
            if not CONFIG_PATH.is_file():
                try:
                    relative_dir = "assets/killer_icons" if self.active_role == "killer" else "assets/survivor_icons"
                    filename = self.icons.get(self.selected) if self.selected else ""
                    save_json(CONFIG_PATH, {
                        "character": self.selected or "",
                        "current": self.current,
                        "personalBest": self.pb,
                        "worldRecord": self.wr,
                        "characterImage": f"{relative_dir}/{filename}" if filename else "",
                        "pollMilliseconds": self.poll_milliseconds,
                        "overlayBackgroundColor": self.bg_color,
                        "overlayBackgroundOpacity": self.bg_opacity,
                        "overlayAccentColor": self.overlay_accent_color,
                        "streakMode": self.streak_mode,
                        "lastKiller": self.killer or "",
                        "lastSurvivor": self.survivor or "",
                        "language": self.language,
                        "overlayPort": self.overlay_port,
                        "showStatusMessages": self.show_status_messages,
                    })
                except Exception:
                    pass

    @property
    def selected(self) -> str | None:
        return self.killer if self.active_role == "killer" else self.survivor

    @property
    def names(self) -> List[str]:
        return self.k_names if self.active_role == "killer" else self.s_names

    @property
    def icons(self) -> Dict[str, str]:
        return self.killers if self.active_role == "killer" else self.survivors

    @property
    def wrs_for_role(self) -> Dict[str, Any]:
        return self.wrs if self.active_role == "killer" else self.swrs

    @property
    def pbs_for_role(self) -> Dict[str, Any]:
        return self.pbs if self.active_role == "killer" else self.spbs

    @property
    def icon_path(self) -> Path | None:
        filename = self.icons.get(self.selected)
        if not filename:
            return None
        # just updates icons more or less
        directory = _asset_dir("killer_icons") if self.active_role == "killer" else _asset_dir("survivor_icons")
        candidate = directory / filename
        if candidate.is_file():
            return candidate
        # this should never trigger probably i think
        alt = (DATA_ROOT / "assets" / "killer_icons" / filename) if self.active_role == "killer" else (DATA_ROOT / "assets" / "survivor_icons" / filename)
        return alt if alt.is_file() else candidate

    def _ensure_data(self) -> None:
        for wrs, pbs, wrs_path, pbs_path, names in (
            (self.wrs, self.pbs, WRS_PATH, PBS_PATH, self.k_names),
            (self.swrs, self.spbs, SWRS_PATH, SPBS_PATH, self.s_names),
        ):
            changed = False
            for name in names:
                if name not in wrs:
                    wrs[name] = None
                    changed = True
                pbs.setdefault(name, {"current": 0, "personalBest": 0})
            if changed:
                save_json(wrs_path, wrs)
            save_json(pbs_path, pbs)

    def restore_from_config(self) -> None:
        data = _load_effective_config()
        self.bg_color = str(data.get("overlayBackgroundColor") or "#000000")
        try:
            self.bg_opacity = int(data.get("overlayBackgroundOpacity") or 0)
        except (TypeError, ValueError):
            self.bg_opacity = 0
        self.bg_opacity = max(0, min(100, self.bg_opacity))
        try:
            self.poll_milliseconds = int(data.get("pollMilliseconds", POLL_MS))
        except (TypeError, ValueError):
            self.poll_milliseconds = POLL_MS
        self.poll_milliseconds = max(25, min(5000, self.poll_milliseconds))
        accent = str(data.get("overlayAccentColor") or "#d10f16").strip()
        self.overlay_accent_color = accent if re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else "#d10f16"
        mode = str(data.get("streakMode", "character"))
        self.streak_mode = mode if mode in ("global", "character") else "character"
        lang = str(data.get("language") or data.get("locale") or "en_us").strip() or "en_us"
        self.language = lang
        try:
            port = int(data.get("overlayPort") or data.get("overlay_port") or PORT)
        except (TypeError, ValueError):
            port = PORT
        self.overlay_port = max(1024, min(65535, port))
        # dont you love backwards compat with genuinely unreleased versions
        # not removing it though im too scared
        if "showStatusMessages" in data:
            self.show_status_messages = bool(data.get("showStatusMessages"))
        elif "show_status_messages" in data:
            self.show_status_messages = bool(data.get("show_status_messages"))
        elif "statusMessagesEnabled" in data:
            self.show_status_messages = bool(data.get("statusMessagesEnabled"))
        else:
            self.show_status_messages = True

        image = str(data.get("characterImage", ""))
        self.active_role = "survivor" if "survivor_icons" in image else "killer"
        name = str(data.get("character", "")).strip()
        last_killer = str(data.get("lastKiller", "")).strip()
        last_survivor = str(data.get("lastSurvivor", "")).strip()
        self.killer = self._restore_name(last_killer, name, "killer")
        self.survivor = self._restore_name(last_survivor, name, "survivor")
        self._load_selected_stats()

    def _restore_name(self, last_name: str, selected_name: str, role: str) -> str | None:
        names = self.k_names if role == "killer" else self.s_names
        if last_name in names:
            return last_name
        if self.active_role == role and selected_name in names:
            return selected_name
        return names[0] if names else None

    def _load_selected_stats(self) -> None:
        name = self.selected
        if not name:
            self.current, self.pb, self.wr = 0, 0, None
            return
        def _to_int(value, fallback=0):
            # strip commas jic since if you edit file manually 
            # adding commas kinda sorta makes sense
            try:
                if isinstance(value, str):
                    value = value.replace(",", "").strip()
                return int(value)
            except (TypeError, ValueError, AttributeError):
                return fallback
            except Exception:
                return fallback

        if self.streak_mode == "global":
            self.current = _to_int(self.global_data.get("current", 0), 0)
            self.pb = _to_int(self.global_data.get("personalBest", 0), 0)
            # make sure min is 0
            self.current = max(0, self.current)
            self.pb = max(0, self.pb)
        else:
            record = self.pbs_for_role.get(name, {"current": 0, "personalBest": 0})
            if not isinstance(record, dict):
                record = {"current": 0, "personalBest": 0}
            self.current = _to_int(record.get("current", 0), 0)
            self.pb = _to_int(record.get("personalBest", 0), 0)
            self.current = max(0, self.current)
            self.pb = max(0, self.pb)
        # wr can be null to show ?
        # since i dont have a good way to 
        # auto grab wrs yet
        raw_wr = self.wrs_for_role.get(name)
        if raw_wr is None:
            self.wr = None
        else:
            try:
                wr_int = _to_int(raw_wr, None)
                self.wr = wr_int if wr_int is not None and wr_int >= 0 else None
            except Exception:
                self.wr = None

    def select(self, role: str, name: str | None = None) -> None:
        # surely this never pops right
        if role not in ("killer", "survivor"):
            raise ValueError(f"Unknown role: {role}")
        self.active_role = role
        if name:
            if name not in (self.k_names if role == "killer" else self.s_names):
                raise ValueError(f"Unknown {role}: {name}")
            if role == "killer":
                self.killer = name
            else:
                self.survivor = name
        elif role == "killer" and self.killer is None and self.k_names:
            self.killer = self.k_names[0]
        elif role == "survivor" and self.survivor is None and self.s_names:
            self.survivor = self.s_names[0]
        self._load_selected_stats()
        self.write_config()

    def set_streak_mode(self, mode: str) -> None:
        # global = one streak across all killers (for tourney), per-character is default
        if mode not in ("global", "character"):
            raise ValueError(f"Unknown streak mode: {mode}")
        self.streak_mode = mode
        self._load_selected_stats()
        self.write_config()

    def increment(self) -> bool:
        # adds a win and checks if streak is new pb
        if not self.selected:
            return False
        self.current += 1
        new_pb = self.current > self.pb
        if new_pb:
            self.pb = self.current
        self.save_stats()
        self.write_config()
        return new_pb

    def reset_streak(self) -> None:
        if not self.selected:
            return
        self.current = 0
        self.save_stats()
        self.write_config()

    def set_stat(self, key: str, value: int | None) -> None:
        if not self.selected:
            return
        if key not in ("current", "pb", "wr"):
            raise ValueError(f"Unknown stat: {key}")
        if key == "wr":
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError("World record must be a non-negative whole number or None.")
            self.wr = value
            self.wrs_for_role[self.selected] = value
            save_json(WRS_PATH if self.active_role == "killer" else SWRS_PATH, self.wrs_for_role)
        else:
            if not isinstance(value, int) or value < 0:
                raise ValueError("Stats must be non-negative whole numbers.")
            if key == "current":
                self.current = value
                self.pb = max(self.pb, value)
            else:
                self.pb = value
            self.save_stats()
        self.write_config()

    def reset_personal_best(self) -> None:
        if not self.selected:
            return
        self.pb = 0
        self.save_stats()
        self.write_config()

    def reset_all_personal_bests(self) -> None:
        if self.streak_mode == "global":
            self.global_data["personalBest"] = 0
            save_json(GLOBAL_PATH, self.global_data)
            for pbs, path in ((self.pbs, PBS_PATH), (self.spbs, SPBS_PATH)):
                for record in pbs.values():
                    record["personalBest"] = 0
                save_json(path, pbs)
        else:
            for name in self.names:
                self.pbs_for_role.setdefault(name, {"current": 0, "personalBest": 0})["personalBest"] = 0
            save_json(PBS_PATH if self.active_role == "killer" else SPBS_PATH, self.pbs_for_role)
        self.pb = 0
        self.write_config()

    def save_stats(self) -> None:
        if not self.selected:
            return
        if self.streak_mode == "global":
            self.global_data.update(current=self.current, personalBest=self.pb)
            save_json(GLOBAL_PATH, self.global_data)
        else:
            self.pbs_for_role[self.selected] = {"current": self.current, "personalBest": self.pb}
            save_json(PBS_PATH if self.active_role == "killer" else SPBS_PATH, self.pbs_for_role)

    def set_background(
        self,
        color: str | None = None,
        opacity: int | None = None,
        poll_milliseconds: int | None = None,
    ) -> None:
        if color is not None:
            self.bg_color = color
        if opacity is not None:
            self.bg_opacity = max(0, min(100, int(opacity)))
        if poll_milliseconds is not None:
            self.poll_milliseconds = max(25, min(5000, int(poll_milliseconds)))
        self.write_config()
    
    # i got annoyed that overlay background drag felt so laggy
    # so it speeds up overlay updating when dragging the slider
    def set_temporary_poll_milliseconds(self, value: int) -> None:
        self.poll_milliseconds = max(25, min(5000, int(value)))
        self.write_config()

    # scuffed way of not accidentally saving 25 ms to config
    def set_opacity_preview(self, opacity: int) -> None:
        value = max(0, min(100, int(opacity)))
        OPACITY_PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        OPACITY_PREVIEW_PATH.write_text(str(value), encoding="ascii")
        
    # scuffed way of not accidentally saving 25 ms to config pt. 2
    def clear_opacity_preview(self) -> None:
        try:
            OPACITY_PREVIEW_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def set_overlay_accent_color(self, color: str) -> None:
        # can change color of the accent bar thing in the overlay
        color = str(color).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Accent color must be a six-digit hex color.")
        self.overlay_accent_color = color.lower()
        self.write_config()

    def write_config(self) -> None:
        if not self.selected:
            # save settings even if no character is picked
            try:
                save_json(CONFIG_PATH, {
                    "character": "",
                    "current": self.current,
                    "personalBest": self.pb,
                    "worldRecord": self.wr,
                    "characterImage": "",
                    "pollMilliseconds": self.poll_milliseconds,
                    "overlayBackgroundColor": self.bg_color,
                    "overlayBackgroundOpacity": self.bg_opacity,
                    "overlayAccentColor": self.overlay_accent_color,
                    "streakMode": self.streak_mode,
                    "lastKiller": self.killer or "",
                    "lastSurvivor": self.survivor or "",
                    "language": self.language,
                    "overlayPort": self.overlay_port,
                    "showStatusMessages": self.show_status_messages,
                })
            except Exception:
                pass
            return
        relative_dir = "assets/killer_icons" if self.active_role == "killer" else "assets/survivor_icons"
        filename = self.icons.get(self.selected)
        save_json(CONFIG_PATH, {
            "character": self.selected,
            "current": self.current,
            "personalBest": self.pb,
            "worldRecord": self.wr,
            "characterImage": f"{relative_dir}/{filename}" if filename else "",
            "pollMilliseconds": self.poll_milliseconds,
            "overlayBackgroundColor": self.bg_color,
            "overlayBackgroundOpacity": self.bg_opacity,
            "overlayAccentColor": self.overlay_accent_color,
            "streakMode": self.streak_mode,
            "lastKiller": self.killer or "",
            "lastSurvivor": self.survivor or "",
            "language": self.language,
            "overlayPort": self.overlay_port,
            "showStatusMessages": self.show_status_messages,
        })

    def set_language(self, code: str) -> None:
        code = str(code or "").strip() or "en_us"
        self.language = code
        self.write_config()

    def set_overlay_port(self, port: int | str) -> None:
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise ValueError("Port must be a number between 1024 and 65535")
        if not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        self.overlay_port = port
        self.write_config()
        try:
            self.restart_server()
        except OSError:
            pass
        except Exception:
            pass

    def set_show_status_messages(self, enabled: bool) -> None:
        self.show_status_messages = bool(enabled)
        self.write_config()

    def restart_server(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
        self.start_server()

    def update_characters(
        self,
        kind: str,
        status: Callable[[str], None] | None = None,
        progress: Callable[[int, int, str | None], None] | None = None,
    ) -> List[str]:
        status = status or (lambda _message: None)
        progress = progress or (lambda *args, **kwargs: None)
        # my scuffed way of automatically selecting a killer
        # when there were no killers before
        # it annoyed me that you had to pick one after first time setup
        was_k_empty = len(getattr(self, "k_names", [])) == 0
        was_s_empty = len(getattr(self, "s_names", [])) == 0
        was_empty = was_k_empty if kind == "killer" else was_s_empty
        had_no_selection = not self.selected
        if kind == "killer":
            directory, wrs_path, pbs_path = DATA_ROOT / "assets" / "killer_icons", WRS_PATH, PBS_PATH
            directory.mkdir(parents=True, exist_ok=True)
            new = update_killers(directory, wrs_path, pbs_path, status=status, progress=progress)
            # recheck for more 
            self.wrs = load_json(WRS_PATH, {})
            self.pbs = load_json(PBS_PATH, {})
            self.killers = discover_characters(directory, "K*_Portrait.png")
            # probaby never
            if not self.killers:
                self.killers = discover_characters(_asset_dir("killer_icons"), "K*_Portrait.png")
            self.k_names = sorted(set(self.killers) | set(self.wrs))
        elif kind == "survivor":
            directory, wrs_path, pbs_path = DATA_ROOT / "assets" / "survivor_icons", SWRS_PATH, SPBS_PATH
            directory.mkdir(parents=True, exist_ok=True)
            new = update_survivors(directory, wrs_path, pbs_path, status=status, progress=progress)
            self.swrs = load_json(SWRS_PATH, {})
            self.spbs = load_json(SPBS_PATH, {})
            self.survivors = discover_characters(directory, "S*_Portrait.png")
            if not self.survivors:
                self.survivors = discover_characters(_asset_dir("survivor_icons"), "S*_Portrait.png")
            self.s_names = sorted(set(self.survivors) | set(self.swrs))
        # if this pops i kms genuinely how
        else:
            raise ValueError(f"Unknown update type: {kind}")
        self._ensure_data()
        # actual logic for loading in the character
        if was_empty:
            if kind == "killer" and self.k_names:
                if self.killer is None or self.killer not in self.k_names:
                    self.killer = self.k_names[0]
                    if had_no_selection:
                        self.active_role = "killer"
                    if self.active_role == "killer" or had_no_selection:
                        self._load_selected_stats()
                        self.write_config()
                    else:
                        # make sure character gets written to config
                        self.write_config()
            elif kind == "survivor" and self.s_names:
                if self.survivor is None or self.survivor not in self.s_names:
                    self.survivor = self.s_names[0]
                    if had_no_selection:
                        self.active_role = "survivor"
                    if self.active_role == "survivor" or had_no_selection:
                        self._load_selected_stats()
                        self.write_config()
                    else:
                        self.write_config()
        return new

    def start_server(self) -> None:
        # start overlay
        # technically i have like a port forward fallback but i never really did do this fully
        # i dont even think if it uses a backup port the ui will show it
        start_port = getattr(self, "overlay_port", PORT)
        try:
            start_port = int(start_port)
            if not 1024 <= start_port <= 65535:
                start_port = PORT
        except (TypeError, ValueError):
            start_port = PORT
        except Exception:
            start_port = PORT
        port = start_port
        for _ in range(10):
            try:
                self.server = create_server(port)
                self.overlay_url = f"http://127.0.0.1:{port}/index.html"
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
                # remember the actual port
                self.overlay_port = port
                return
            except OSError:
                port += 1
                if port > 65535:
                    port = PORT
        self.overlay_url = f"http://127.0.0.1:{PORT}/index.html"

    def close(self):
        # when it gets closed save everything and shutdown overlay
        try:
            self.save_stats()
        except Exception:
            pass  # not much you can do if its closing
        self.clear_opacity_preview()
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except OSError:
                pass
            except Exception:
                pass
            self.server = None
