# grabs the character info from the wiki so i dont have to bundle items
# i dont know if im allowed to bundle it since maybe its copyright
# also this means you can just have the new characters appear in the lists when
# bhvr adds them to the game instead of updating the whole program

from __future__ import annotations

import html
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from storage import load_json, save_json

try:
    from translations import tr
except Exception:  # when running standalone without translations (wtf does this mean??? what is he yapping about)
    def tr(key: str, default: str | None = None, **kwargs: Any) -> str:
        text = default if default is not None else key
        try:
            return text.format(**kwargs) if kwargs else text
        except Exception:
            return text

BASE_URL = "https://deadbydaylight.wiki.gg"
USER_AGENT = "DBD-Overlay-Update/1.0"


def normalize_display(name: str) -> str:
    return html.unescape(name).strip().upper()


def normalize_stem(stem: str) -> str:
    core = stem.split("_", 1)[1].replace("_Portrait", "")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", core).upper()


def fetch_wiki(url: str, status: Optional[Callable[[str], None]], tr_key: str) -> str:
    def report(msg: str) -> None:
        if status:
            status(msg)

    report(tr(tr_key))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def download_with_retry(url, dest, max_attempts=3):
    # download to .tmp then move retry 3x because wiki might throttle
    tmp_dest = dest.with_name(dest.name + ".tmp")
    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            if tmp_dest.exists():
                try:
                    tmp_dest.unlink()
                except Exception:
                    pass
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            try:
                if tmp_dest.stat().st_size == 0:
                    raise RuntimeError("Empty download")
            except OSError:
                pass
            try:
                tmp_dest.replace(dest)
            except Exception:
                os.replace(str(tmp_dest), str(dest))
            return
        except Exception as exc:
            last_exc = exc
            try:
                if tmp_dest.exists():
                    tmp_dest.unlink()
            except Exception:
                pass
            if attempt < max_attempts - 1:
                time.sleep(1 * (attempt + 1))
            else:
                raise
    if last_exc:
        raise last_exc


def parse_wiki_section(
    html_text: str,
    start_marker: str,
    end_marker: str,
    card_re: re.Pattern,
    src_group: int,
    prefix: str,  #K or S
) -> List[Dict[str, Any]]:
    start = html_text.find(start_marker)
    end = html_text.find(end_marker)
    if start != -1 and end != -1:
        section = html_text[start:end]
    else:
        section = html_text
    found: Dict[str, Dict[str, Any]] = {}
    for m in card_re.finditer(section):
        src = m.group(src_group)
        filename = Path(src.split("?")[0]).name
        num_m = re.search(rf"{re.escape(prefix)}(\d+)", src)
        url = src if src.startswith("http") else BASE_URL + src
        found[filename] = {
            "name": normalize_stem(Path(filename).stem),
            "number": int(num_m.group(1)) if num_m else None,
            "filename": filename,
            "url": url,
        }
    return [found[k] for k in sorted(found, key=lambda n: found[n]["number"] or 0)]


def generic_update(  # moved over. i used to have seperate logic for killer and surivivor but theyre basically the same
    icons_dir: Path | str,
    wrs_path: Path | str,
    pbs_path: Path | str,
    wiki_url: str,
    start_marker: str,
    end_marker: str,
    card_re: re.Pattern,
    src_group: int,
    glob_pattern: str,
    prefix: str,
    tr_keys: Dict[str, str],
    status: Optional[Callable[[str], None]] = None,
    progress: Optional[Callable[[int, int, Optional[str]], None]] = None,
) -> List[str]:


    def report(msg: str) -> None:
        if status:
            status(msg)

    def report_progress(done: int, total: int, name: Optional[str] = None) -> None:
        if progress:
            try:
                try:
                    progress(done, total, name)
                except TypeError:
                    progress(done, total)
            except Exception:
                pass

    html_text = fetch_wiki(wiki_url, report, tr_keys["checking"])
    wiki = parse_wiki_section(html_text, start_marker, end_marker, card_re, src_group, prefix)
    if not wiki:
        raise RuntimeError(tr(tr_keys["no_found_error"]))

    icons_dir = Path(icons_dir)
    existing_files = {f.name for f in icons_dir.glob(glob_pattern)}
    new = [x for x in wiki if x["filename"] not in existing_files]
    total = len(new)
    if new:
        report(tr(tr_keys["new_found"], count=total))
    else:
        report(tr(tr_keys["no_new"]))
    report_progress(0, total)

    icons_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Dict[str, Any]] = []

    for idx, entry in enumerate(new, 1):
        report(tr("updater.downloading_image", name=entry["name"]))
        report_progress(idx - 1, total, entry["name"])
        try:
            download_with_retry(entry["url"], icons_dir / entry["filename"], max_attempts=3)
        except Exception as exc:
            report(tr("updater.could_not_download", name=entry["name"], error=str(exc)))
            report_progress(idx, total, entry["name"])
            continue
        downloaded.append(entry)
        report_progress(idx, total, entry["name"])

    if downloaded:
        report(tr(tr_keys["entering"], count=len(downloaded)))
        wrs = load_json(wrs_path, {})
        pbs = load_json(pbs_path, {})
        for entry in downloaded:
            wrs.setdefault(entry["name"], None)
            pbs.setdefault(entry["name"], {"current": 0, "personalBest": 0})
        save_json(wrs_path, wrs)
        save_json(pbs_path, pbs)

    report(tr("updater.update_finished"))
    return [x["name"] for x in downloaded]


def get_data_root() -> Path:
    try:
        docs = Path.home() / "Documents" / "DBD Overlay"
        if docs.exists():
            return docs
        prog = Path(__file__).resolve().parent
        if (prog / "killer_wrs.json").exists() or (prog / "config.json").exists():
            return prog
        docs.mkdir(parents=True, exist_ok=True)
        return docs
    except Exception:
        return Path(__file__).resolve().parent

KILLER_WIKI_URL = "https://deadbydaylight.wiki.gg/wiki/Killers"

# hate doing ts
KILLER_CARD_RE = re.compile(
    r'<div style="display: inline-flex; flex-direction: column; text-align:center; margin-bottom: 35px;">'
    r'<a href="[^"]+"(?: class="[^"]*")? title="[^"]*"[^>]*>[^<]*</a>'
    r"([^\n<]+)\n"
    r'<div style="--defaultCharPortraitDimensions: 250px;" class="charPortraitWrapper".*?'
    r'<a href="[^"]+" title="[^"]*"><img alt="[^"]+" src="([^"]+?Portrait\.png[^"]*)"',
    re.S,
)


def fetch_killer_wiki(status=None):
    return fetch_wiki(KILLER_WIKI_URL, status, "updater.checking_killers")


def parse_killer_wiki(html_text):
    return parse_wiki_section(
        html_text,
        'id="List_of_Killers"',
        'id="List_of_Killer_Powers"',
        KILLER_CARD_RE,
        2,
        "K",
    )


def update_killers(icons_dir, wrs_path, pbs_path, status=None, progress=None):
    return generic_update(
        icons_dir=icons_dir,
        wrs_path=wrs_path,
        pbs_path=pbs_path,
        wiki_url=KILLER_WIKI_URL,
        start_marker='id="List_of_Killers"',
        end_marker='id="List_of_Killer_Powers"',
        card_re=KILLER_CARD_RE,
        src_group=2,
        glob_pattern="K*_Portrait.png",
        prefix="K",
        tr_keys={
            "checking": "updater.checking_killers",
            "no_found_error": "updater.no_killers_found_error",
            "new_found": "updater.new_killers_found",
            "no_new": "updater.no_new_killers",
            "entering": "updater.entering_records",
        },
        status=status,
        progress=progress,
    )


SURVIVOR_WIKI_URL = "https://deadbydaylight.wiki.gg/wiki/Survivors"

SURVIVOR_CARD_RE = re.compile(
    r'<div style="display: inline-flex; flex-direction: column; text-align:center; margin-bottom: 35px;">'
    r'<a href="[^"]+"(?: class="[^"]*")? title="[^"]*"[^>]*>[^<]*</a>[^<]*\s*'
    r'<div style="--defaultCharPortraitDimensions: 250px;" class="charPortraitWrapper".*?'
    r'<img alt="[^"]*" src="([^"]+?S\d+_[\w-]+_Portrait\.png[^"]*)"',
    re.S,
)


def fetch_survivor_wiki(status=None):
    return fetch_wiki(SURVIVOR_WIKI_URL, status, "updater.checking_survivors")


def parse_survivor_wiki(html_text):
    return parse_wiki_section(
        html_text,
        'id="List_of_Survivors"',
        'id="List_of_Survivor_Items"',
        SURVIVOR_CARD_RE,
        1,
        "S",
    )


def update_survivors(icons_dir, wrs_path, pbs_path, status=None, progress=None):
    return generic_update(
        icons_dir=icons_dir,
        wrs_path=wrs_path,
        pbs_path=pbs_path,
        wiki_url=SURVIVOR_WIKI_URL,
        start_marker='id="List_of_Survivors"',
        end_marker='id="List_of_Survivor_Items"',
        card_re=SURVIVOR_CARD_RE,
        src_group=1,
        glob_pattern="S*_Portrait.png",
        prefix="S",
        tr_keys={
            "checking": "updater.checking_survivors",
            "no_found_error": "updater.no_survivors_found_error",
            "new_found": "updater.new_survivors_found",
            "no_new": "updater.no_new_survivors",
            "entering": "updater.entering_records",
        },
        status=status,
        progress=progress,
    )


# interface for the controller

def update_characters(kind, icons_dir, wrs_path, pbs_path, status=None, progress=None):
    # kind is killer or survivor
    kind = str(kind).lower().strip()
    if kind in ("killer", "killers", "k"):
        return update_killers(icons_dir, wrs_path, pbs_path, status=status, progress=progress)
    if kind in ("survivor", "survivors", "s"):
        return update_survivors(icons_dir, wrs_path, pbs_path, status=status, progress=progress)
    raise ValueError(f"Unknown character kind: {kind}")


def _get_data_root():
    return get_data_root()


if __name__ == "__main__":
    # command line for updating characters because its simplest i think
    import argparse

    parser = argparse.ArgumentParser(description="Update DBD characters")
    parser.add_argument("kind", nargs="?", choices=["killer", "survivor"], help="which to update")
    args = parser.parse_args()

    root = get_data_root()

    if args.kind in (None, "killer"):
        added = update_killers(
            root / "assets" / "killer_icons",
            root / "killer_wrs.json",
            root / "killer_pbs.json",
            status=print,
        )
        print(f"Killers added: {', '.join(added) if added else 'none'}")

    if args.kind in (None, "survivor"):
        added = update_survivors(
            root / "assets" / "survivor_icons",
            root / "survivor_wrs.json",
            root / "survivor_pbs.json",
            status=print,
        )
        print(f"Survivors added: {', '.join(added) if added else 'none'}")

    if args.kind is None:
        sys.exit(0)
    else:
        sys.exit(0)
