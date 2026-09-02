# ui for about popup

import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageTk

from dbd_controller import GITHUB_LOGO
from translations import tr
from theme import ACCENT, ACCENT_HOVER, BG, BORDER, BTN, BTN_HOVER, FG, MUTED, PANEL


def _get_version():
    # theres probably a better way to do the version but idk
    try:
        from dbd_controller import DATA_ROOT, PROG_ROOT, BUNDLED_ROOT

        for base in (DATA_ROOT, PROG_ROOT, BUNDLED_ROOT):
            try:
                cand = base / "version.txt"
                if cand.is_file():
                    text = cand.read_text(encoding="utf-8", errors="ignore").strip()
                    if text:
                        # just checks the first line
                        return text.splitlines()[0].strip()
            except Exception:
                continue
    except Exception:
        pass
    # dev thing
    try:
        cand = Path(__file__).resolve().parent / "version.txt"
        if cand.is_file():
            text = cand.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                return text.splitlines()[0].strip()
    except Exception:
        pass
    return "v0.0.0"

if TYPE_CHECKING:
    from dbd_ui import App


def open_about(app):
    # opens and makes it focused
    if getattr(app, "_about_win", None) is not None and app._about_win.winfo_exists():
        try:
            app._about_win.lift()
            app._about_win.focus_force()
        except Exception:
            pass
        return

    win = tk.Toplevel(app)
    win.withdraw()
    app._about_win = win
    win.title(tr("about.title", default="About"))
    try:
        win.iconbitmap(sys.executable)
    except Exception:
        pass
    win.configure(bg=BG)
    win.transient(app)
    win.resizable(False, False)
    try:
        app.update_idletasks()
        x = app.winfo_x() + (app.winfo_width() // 2) - 180
        y = app.winfo_y() + 80
        win.geometry(f"360x440+{max(x, 0)}+{max(y, 0)}")
    except Exception:
        pass
    win.deiconify()
    win.grab_set()

    def on_close_about() -> None:
        try:
            win.grab_release()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        app._about_win = None

    win.protocol("WM_DELETE_WINDOW", on_close_about)

    outer = tk.Frame(win, bg=BG)
    outer.pack(fill="both", expand=True, padx=16, pady=14)
    outer.columnconfigure(0, weight=1)

    # top row is for version check/update
    update_box = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    update_box.pack(fill="x", pady=(0, 12))
    update_box.columnconfigure(0, weight=1)
    update_box.columnconfigure(1, weight=0)
    version_str = _get_version()
    version_label = tk.Label(
        update_box,
        text=f"{tr('about.version', default='Version')}: {version_str}",
        bg=PANEL,
        fg=FG,
        font=("Segoe UI", 9),
    )
    version_label.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=12)
    win._version_label = version_label
    win._version_str = version_str
    check_label = tk.Label(
        update_box,
        text=tr("about.check_updates", default="Check for Updates"),
        bg=BTN,
        fg="#ffffff",
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
        padx=14,
        pady=6,
    )
    check_label.grid(row=0, column=1, sticky="e", padx=(8, 12), pady=8)
    win._check_label = check_label
    # little status line below
    status_label = tk.Label(update_box, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 8))
    status_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 8))
    win._update_status = status_label
    win._checking = False

    def _set_status(msg: str) -> None:
        try:
            status_label.config(text=msg)
        except Exception:
            pass

    def on_check_click(_e=None) -> None:
        if getattr(win, "_checking", False):
            return
        win._checking = True
        orig_text = tr("about.check_updates", default="Check for Updates")
        try:
            check_label.config(text=tr("about.checking", default="Checking..."), bg=BTN)
        except Exception:
            pass
        _set_status("")

        import threading

        def worker() -> None:
            try:
                import updater

                def status_cb(msg: str) -> None:
                    try:
                        win.after(0, lambda m=msg: _set_status(m))
                    except Exception:
                        pass

                avail, info, cur, latest = updater.check_for_updates(status_cb=status_cb)
                if not avail:
                    def _no_update() -> None:
                        try:
                            check_label.config(text=tr("about.no_updates", default="No updates found"))
                        except Exception:
                            pass
                        _set_status(f"{tr('about.current_version', default='Current')}: {cur}")
                        win.after(2500, lambda: check_label.config(text=orig_text))
                        win.after(2500, lambda: _set_status(""))
                        win._checking = False

                    win.after(0, _no_update)
                    return

                # update found
                def _downloading() -> None:
                    try:
                        check_label.config(text=tr("about.downloading", default="Downloading..."))
                    except Exception:
                        pass
                    _set_status(f"{tr('about.found_version', default='Found')}: {latest}")

                win.after(0, _downloading)

                temp_dir = updater.prepare_update(info, status_cb=status_cb)
                if temp_dir is None:
                    def _failed() -> None:
                        try:
                            check_label.config(text=tr("about.update_failed", default="Update failed"))
                        except Exception:
                            pass
                        win.after(2500, lambda: check_label.config(text=orig_text))
                        win.after(2500, lambda: _set_status(""))
                        win._checking = False

                    win.after(0, _failed)
                    return

                def _launching() -> None:
                    try:
                        check_label.config(text=tr("about.launching", default="Launching..."))
                    except Exception:
                        pass
                    _set_status(tr("about.restarting", default="Restarting..."))

                win.after(0, _launching)
                # small delay to actually see launching
                win.after(500, lambda: updater.launch_handler_and_exit(temp_dir, app))

            except Exception as exc:
                def _err() -> None:
                    try:
                        check_label.config(text=tr("about.update_failed", default="Update failed"))
                    except Exception:
                        pass
                    _set_status(str(exc)[:80])
                    win.after(2500, lambda: check_label.config(text=orig_text))
                    win.after(2500, lambda: _set_status(""))
                    win._checking = False

                try:
                    win.after(0, _err)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    check_label.bind("<Button-1>", on_check_click)
    check_label.bind("<Enter>", lambda _e: check_label.config(bg=BTN_HOVER) if not getattr(win, "_checking", False) else None)
    check_label.bind("<Leave>", lambda _e: check_label.config(bg=BTN) if not getattr(win, "_checking", False) else None)

    # github logo
    github_box = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    github_box.pack(fill="x", pady=(0, 12))
    github_box.columnconfigure(0, weight=1)

    # try to load logo
    github_img = None
    github_label = None
    try:
        if GITHUB_LOGO.is_file():
            img = Image.open(GITHUB_LOGO).convert("RGBA")
            # logo shrink
            img.thumbnail((200, 200), Image.LANCZOS)
            github_img = ImageTk.PhotoImage(img)
            github_label = tk.Label(github_box, image=github_img, bg=PANEL, cursor="hand2")
            github_label.image = github_img
            github_label.pack(pady=(14, 6))
        else:
            github_label = tk.Label(github_box, text="GitHub", bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold"), cursor="hand2")
            github_label.pack(pady=(14, 6))
    except Exception:
        try:
            github_label = tk.Label(github_box, text="GitHub", bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold"), cursor="hand2")
            github_label.pack(pady=(14, 6))
        except Exception:
            github_label = None

    if github_label is not None:
        url = "https://github.com/Proxivirus/DBD-Overlay"
        github_label.bind("<Button-1>", lambda _e: webbrowser.open(url))
        # clickable logo + text link
        link = tk.Label(github_box, text=url, bg=PANEL, fg=FG, font=("Segoe UI", 8, "underline"), cursor="hand2")
        link.pack(pady=(0, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(url))

    # credits
    # i didnt actually do any translation work for the credits
    # i couldnt be bothered
    credits_title = tk.Label(outer, text=tr("about.credits", default="Credits"), bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold"))
    credits_title.pack(anchor="w", pady=(10, 4), padx=2)
    win._credits_title = credits_title
    sep = tk.Frame(outer, bg=BORDER, height=1)
    sep.pack(fill="x", pady=(0, 8))

    credits_box = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    credits_box.pack(fill="x")
    credits_box.columnconfigure(0, weight=1)
    tk.Label(
        credits_box,
        text="Artist Palette Emoji: https://github.com/twitter/twemoji (Twitter/Twemoji 15.0)",
        bg=PANEL,
        fg=FG,
        font=("Segoe UI", 8),
        wraplength=320,
        justify="left",
    ).pack(anchor="w", padx=12, pady=(10, 4))
    tk.Label(
        credits_box,
        text="Character names & images: https://deadbydaylight.wiki.gg",
        bg=PANEL,
        fg=FG,
        font=("Segoe UI", 8),
        wraplength=320,
        justify="left",
    ).pack(anchor="w", padx=12, pady=(0, 10))

    win.bind("<Escape>", lambda _e: on_close_about())
