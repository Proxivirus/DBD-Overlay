from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

# overlay local site

if getattr(sys, "frozen", False):
    PROG_ROOT = Path(sys.executable).resolve().parent
else:
    PROG_ROOT = Path(__file__).resolve().parent
BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", PROG_ROOT))

def _get_data_root():
    try:
        docs = Path.home() / "Documents" / "DBD Overlay"
        docs.mkdir(parents=True, exist_ok=True)
        return docs
    except OSError:
        # if the proper folder isnt working
        return PROG_ROOT

DATA_ROOT = _get_data_root()
PORT = 8765


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DATA_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

    def translate_path(self, path):
        # try save folder then fallback if you have to
        base = Path(super().translate_path(path))
        if base.is_file():
            return str(base)
        try:
            rel = base.relative_to(DATA_ROOT)
        except ValueError:
            return str(base)
        for alt_root in (PROG_ROOT, BUNDLED_ROOT):
            alt = alt_root / rel
            if alt.is_file():
                return str(alt)
        return str(base)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    import webbrowser
    url = f"http://127.0.0.1:{PORT}/index.html"
    print(f"Overlay running at {url}")
    print("Leave this window open while OBS is using the overlay.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    create_server().serve_forever()
