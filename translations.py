# loads json files from assets/translations
# each lang file is written like en_us.json with a display_name at top of the json
# you can add new ones in save folder in assets/translations and it should detect them
# im just now realizing i never really tested that to see. oh well

import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _PROG_ROOT = Path(sys.executable).resolve().parent
else:
    _PROG_ROOT = Path(__file__).resolve().parent
_BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", _PROG_ROOT))

def _get_data_root():
    # same shi as in the controller
    try:
        docs = Path.home() / "Documents" / "DBD Overlay"
        docs.mkdir(parents=True, exist_ok=True)
        return docs
    except OSError:
        return _PROG_ROOT

_DATA_ROOT = _get_data_root()
_ROOT = _DATA_ROOT  # old from prerelease


def _bundled_translations_dir():
    # hardcoded to where pyinstaller puts it not DATA_ROOT
    for base in (_PROG_ROOT, _BUNDLED_ROOT):
        cand = base / "assets" / "translations"
        if cand.is_dir() and any(cand.glob("*.json")):
            return cand
    for base in (_PROG_ROOT, _BUNDLED_ROOT):
        cand = base / "assets" / "translations"
        if cand.exists():
            return cand
    return _PROG_ROOT / "assets" / "translations"


def _data_translations_dir():
    return _DATA_ROOT / "assets" / "translations"


def _translations_dir():
    # choose user folder if they actually put translations there
    data_dir = _data_translations_dir()
    if data_dir.is_dir() and any(data_dir.glob("*.json")):
        return data_dir
    for base in (_PROG_ROOT, _BUNDLED_ROOT):
        cand = base / "assets" / "translations"
        if cand.is_dir() and any(cand.glob("*.json")):
            return cand
    for base in (_PROG_ROOT, _BUNDLED_ROOT):
        cand = base / "assets" / "translations"
        if cand.exists():
            return cand
    return _PROG_ROOT / "assets" / "translations"


TRANSLATIONS_DIR = _translations_dir()
_BUNDLED_TRANSLATIONS_DIR = _bundled_translations_dir()
DEFAULT_LANG = "en_us"

_cache = {}
_active_lang = None
_active_data = None


def _candidate_paths(lang):
    # user folder first then bundled
    # some bs about lower upper too cuz if i ever do linux ik being lowercase uppercase actually matters
    candidates = []
    search_bases = [_data_translations_dir(), _bundled_translations_dir()]
    if TRANSLATIONS_DIR not in search_bases:
        search_bases.append(TRANSLATIONS_DIR)
    for base in search_bases:
        for name in (lang, lang.lower(), lang.upper()):
            candidates.append(base / f"{name}.json")
            candidates.append(base / f"{name}.JSON")
    # undupe keep order
    seen = set()
    uniq = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _load_file(path):
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    except Exception:
        # okay this one might actually pop i have a habit of
        # changing json by hand and not checking if its valid
        return None
    return None


def _load_bundled_default():
    bundled_dir = _bundled_translations_dir()
    for name in (DEFAULT_LANG, DEFAULT_LANG.lower(), DEFAULT_LANG.upper()):
        for ext in (f"{name}.json", f"{name}.JSON"):
            cand = bundled_dir / ext
            data = _load_file(cand)
            if data is not None:
                return data
    return {"display_name": "English (US)", "code": "en_us"}


def load_translation(lang):
    lang = (lang or DEFAULT_LANG).strip() or DEFAULT_LANG
    if lang in _cache:
        return _cache[lang]
    for cand in _candidate_paths(lang):
        data = _load_file(cand)
        if data is not None:
            _cache[lang] = data
            return data
    if lang != DEFAULT_LANG:
        # if somehow the language isnt there fallback to ingles
        fallback = load_translation(DEFAULT_LANG)
        _cache[lang] = fallback
        return fallback
    bundled = _load_bundled_default()
    _cache[lang] = bundled
    return bundled


def _detect_language():
    # config.json can technically have language or locale since im just a silly guy
    # check all three roots
    for base in (_DATA_ROOT, _PROG_ROOT, _BUNDLED_ROOT):
        try:
            cfg_path = base / "config.json"
            if cfg_path.is_file():
                with open(cfg_path, "r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                    # empty string means default
                    lang = str(cfg.get("language") or cfg.get("locale") or "").strip()
                    if lang:
                        return lang
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        except Exception:
            continue
    return DEFAULT_LANG


def _resolve_key(data, key):
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def get_translation(lang=None):
    global _active_lang, _active_data
    target = (lang or _detect_language()).strip() or DEFAULT_LANG
    if _active_data is not None and _active_lang == target:
        return _active_data
    _active_lang = target
    _active_data = load_translation(target)
    return _active_data


def tr(key, default=None, **kwargs):
    data = get_translation()
    raw = _resolve_key(data, key)
    if raw is None:
        # in theory if a lang file only has partial translations
        # it should load the ones it has and just fallback
        # the missing ones to en_us.. in theory
        for candidate in _candidate_paths(DEFAULT_LANG):
            fallback_data = _load_file(candidate)
            if fallback_data is not None:
                raw = _resolve_key(fallback_data, key)
                if raw is not None:
                    break
        if raw is None:
            return default if default is not None else key
    if not isinstance(raw, str):
        raw = str(raw)
    if kwargs:
        try:
            return raw.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return raw
        except Exception:
            return raw
    return raw

t = tr  # some of my older shit used t and i dont know if i got it all

def get_display_name(lang):
    data = load_translation(lang)
    name = data.get("display_name") or data.get("language_name") or data.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return lang


def list_available_translations():
    result = []
    search_dirs = [_data_translations_dir(), _bundled_translations_dir()]
    if TRANSLATIONS_DIR not in search_dirs:
        search_dirs.append(TRANSLATIONS_DIR)
    seen = set()
    for base in search_dirs:
        if not base.is_dir():
            continue
        for path in base.iterdir():
            if path.is_dir():
                continue
            name = path.name
            if not name.lower().endswith(".json"):
                continue
            code = name[:-5]
            if not code or code.startswith("."):
                continue
            if code.lower() in seen:
                continue
            seen.add(code.lower())
            data = _load_file(path)
            display = None
            if data:
                display = data.get("display_name") or data.get("language_name") or data.get("name")
            if not isinstance(display, str) or not display.strip():
                display = code
            result.append({"code": code, "display_name": str(display).strip(), "path": str(path)})
    if not result:
        bdir = _bundled_translations_dir()
        result.append({"code": DEFAULT_LANG, "display_name": "English (US)", "path": str(bdir / f"{DEFAULT_LANG}.json")})
    result.sort(key=lambda x: x["code"].lower())
    return result


def reload_translations(lang=None):
    global _active_lang, _active_data, TRANSLATIONS_DIR
    _active_lang = None
    _active_data = None
    _cache.clear()
    TRANSLATIONS_DIR = _translations_dir()
    return get_translation(lang)


# preload to find messed up lang quick
try:
    get_translation()
except Exception:
    pass
