import json
import os
import tempfile
from pathlib import Path
from typing import Any

# some dogshit to hopefully prevent the json from corrupting maybe possibly


def load_json(path, default):
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        # file missing or someone touched it and it didnt like it
        return default
    except Exception:
        return default


def save_json(path, data):
    # i learned atomic replace peepoHappy
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        # NamedTemporaryFile with delete=False so os.replace after close
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as f:
            tmp = f.name
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # makin me mad
        os.replace(tmp, target)
        tmp = None
    except OSError as e:
        # either the perms changed or this dude doesnt have space for like a 1kb file
        # either way thats crazy bro lock in
        raise
    finally:
        if tmp:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
