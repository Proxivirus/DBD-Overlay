# settings window with normal and advanced settings

import tkinter as tk
from tkinter import colorchooser, ttk
from typing import TYPE_CHECKING, Any

import sys

import translations
from translations import tr
from theme import ACCENT, ACCENT_HOVER, BG, BORDER, BTN, BTN_HOVER, FG, MUTED, PANEL, PANEL2

if TYPE_CHECKING:
    from dbd_ui import App


def open_settings(app):
    # focus window and only have 1
    if getattr(app, "_settings_win", None) is not None and app._settings_win.winfo_exists():
        try:
            app._settings_win.lift()
            app._settings_win.focus_force()
        except Exception:
            pass
        return

    win = tk.Toplevel(app)
    win.withdraw()
    app._settings_win = win
    win.title(tr("settings.title", default="Settings"))
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
        win.geometry(f"360x385+{max(x, 0)}+{max(y, 0)}")
    except Exception:
        pass
    win.deiconify()
    win.grab_set()

    def on_close_settings() -> None:
        try:
            win.grab_release()
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        app._settings_win = None

    win.protocol("WM_DELETE_WINDOW", on_close_settings)

    outer = tk.Frame(win, bg=BG)
    outer.pack(fill="both", expand=True, padx=16, pady=14)
    outer.columnconfigure(0, weight=1)

    # language 
    normal = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    normal.pack(fill="x", pady=(0, 8))
    normal.columnconfigure(1, weight=1)
    tk.Label(normal, text=tr("settings.language", default="Language"), bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=10)
    try:
        langs = translations.list_available_translations()
    except Exception:
        langs = [{"code": "en_us", "display_name": "English (US)"}]
    cur_code = getattr(app.controller, "language", "en_us")
    codes = [l["code"] for l in langs]
    if cur_code not in codes:
        langs = langs + [{"code": cur_code, "display_name": translations.get_display_name(cur_code)}]
    display_to_code = {l["display_name"]: l["code"] for l in langs}
    code_to_display = {l["code"]: l["display_name"] for l in langs}
    cur_display = code_to_display.get(cur_code, translations.get_display_name(cur_code))
    lang_var = tk.StringVar(value=cur_display)
    cmb = ttk.Combobox(normal, textvariable=lang_var, state="readonly", font=("Segoe UI", 10), values=[l["display_name"] for l in langs])
    cmb.grid(row=0, column=1, sticky="ew", padx=(12, 12), pady=10)
    win._lang_cmb = cmb
    win._lang_var = lang_var
    win._lang_map = display_to_code

    # this rescans when you click it in case later i add some way to live download new languages
    # (i probably wont)
    # also clearly i barely understand this code dont judge
    def _refresh_lang_list(_event: tk.Event[Any] | None = None) -> None:
        nonlocal display_to_code
        try:
            fresh = translations.list_available_translations()
            # keep current selection (?)
            fresh_codes = [l["code"] for l in fresh]
            # keep current if its not in the dropdown (?)
            if cur_code not in fresh_codes:
                fresh = fresh + [{"code": cur_code, "display_name": translations.get_display_name(cur_code)}]
            new_map = {l["display_name"]: l["code"] for l in fresh}
            new_display = [l["display_name"] for l in fresh]
            # update if new languages
            try:
                cmb.configure(values=new_display)
            except Exception:
                pass
            # something something update for when you close it
            win._lang_map.clear()
            win._lang_map.update(new_map)
            # something something update for the save file
            display_to_code = new_map
        except Exception:
            pass
    # refresh list every way possible
    for seq in ("<Button-1>", "<FocusIn>", "<KeyPress-Down>", "<<ComboboxSelected>>"):
        try:
            cmb.bind(seq, _refresh_lang_list, add="+")
        except Exception:
            pass

    # overlay theme and overlay theme only. NOT ui theme (though i should)
    tk.Label(outer, text=tr("settings.themes", default="Theme"), bg=BG, fg=MUTED,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 4), padx=2)
    theme_box = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    theme_box.pack(fill="x")
    tk.Label(theme_box, text=tr("settings.overlay_accent", default="Overlay accent color"),
             bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)
    accent_var = tk.StringVar(value=getattr(app.controller, "overlay_accent_color", ACCENT))
    accent_swatch = tk.Label(theme_box, width=4, height=1, bg=accent_var.get(), cursor="hand2",
                             relief="solid", bd=1)
    accent_swatch.pack(side="right", padx=12, pady=8)

    def _choose_accent(_event: tk.Event[Any] | None = None) -> None:
        chosen = colorchooser.askcolor(color=accent_var.get(), parent=win,
                                       title=tr("settings.choose_color", default="Choose overlay accent color"))
        if chosen and chosen[1]:
            accent_var.set(chosen[1])
            accent_swatch.configure(bg=chosen[1])

    accent_swatch.bind("<Button-1>", _choose_accent)

    # advanced section
    tk.Label(outer, text=tr("settings.advanced", default="Advanced"), bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 4), padx=2)
    sep = tk.Frame(outer, bg=BORDER, height=1)
    sep.pack(fill="x", pady=(0, 8))

    # port change and debug change
    advanced = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    advanced.pack(fill="x", pady=(0, 12))
    advanced.columnconfigure(1, weight=1)

    tk.Label(advanced, text=tr("settings.overlay_port", default="Overlay Port"), bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 10))
    port_var = tk.StringVar(value=str(getattr(app.controller, "overlay_port", 8765)))
    port_entry = tk.Entry(advanced, textvariable=port_var, bg=PANEL2, fg=FG, insertbackground=FG, font=("Segoe UI", 10), relief="flat", highlightbackground=BORDER, highlightcolor=ACCENT, highlightthickness=1, width=8, justify="center")
    port_entry.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 10))
    # this is an old thing because used to be you needed to restart for port to changes
    # but you dont anymore so this just sits here
    # can probably remove it but everything works and id like to keep it that way
    win._port_var = port_var
    win._port_entry = port_entry

    status_var = tk.BooleanVar(value=bool(getattr(app.controller, "show_status_messages", True)))
    chk = tk.Checkbutton(advanced, text=tr("settings.show_status_messages", default="Show status messages"), variable=status_var, bg=PANEL, fg=FG, activebackground=PANEL, activeforeground=FG, selectcolor=PANEL2, font=("Segoe UI", 10), anchor="w", highlightthickness=0, bd=0)
    chk.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 0))
    tk.Label(advanced, text=tr("settings.show_status_desc", default="Show debug messages at the bottom when changes are made"), bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=300, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))
    win._status_var = status_var

    btn_row = tk.Frame(outer, bg=BG)
    btn_row.pack(fill="x", pady=(8, 0))
    err_label = tk.Label(btn_row, text="", bg=BG, fg=ACCENT, font=("Segoe UI", 8))
    err_label.pack(side="left")

    def save_and_close() -> None:
        sel_display = lang_var.get()
        sel_code = display_to_code.get(sel_display, cur_code)
        raw_port = port_var.get().strip()
        try:
            port_int = int(raw_port)
            if not 1024 <= port_int <= 65535:
                raise ValueError
        except Exception:
            err_label.config(text=tr("settings.port_invalid", default="Port must be between 1024 and 65535"))
            return
        try:
            if sel_code != cur_code:
                app.controller.set_language(sel_code)
                try:
                    translations.reload_translations(sel_code)
                except Exception:
                    pass
                try:
                    if hasattr(app, "refresh_translations"):
                        app.refresh_translations()
                    else:
                        app.title(tr("app.title"))
                except Exception:
                    try:
                        app.title(tr("app.title"))
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            app.controller.set_overlay_accent_color(accent_var.get())
        except ValueError as exc:
            err_label.config(text=str(exc))
            return
        try:
            if port_int != getattr(app.controller, "overlay_port", 8765):
                app.controller.set_overlay_port(port_int)
                try:
                    app.url_label.config(text=app.controller.overlay_url)
                except Exception:
                    pass
        except Exception as exc:
            err_label.config(text=str(exc))
            return
        try:
            new_show = bool(status_var.get())
            app.controller.set_show_status_messages(new_show)
            try:
                # this bar needs to GO AWAY bro pmo
                app.status.config(text=tr("status.ready") if new_show else "")
            except Exception:
                pass
        except Exception:
            pass
        on_close_settings()

    save_btn = tk.Label(btn_row, text=tr("settings.save", default="Save"), bg=ACCENT, fg="#ffffff", font=("Segoe UI", 10, "bold"), cursor="hand2", padx=14, pady=6)
    save_btn.pack(side="right", padx=(8, 0))
    save_btn.bind("<Button-1>", lambda _e: save_and_close())
    save_btn.bind("<Enter>", lambda _e: save_btn.config(bg=ACCENT_HOVER))
    save_btn.bind("<Leave>", lambda _e: save_btn.config(bg=ACCENT))

    cancel_btn = tk.Label(btn_row, text=tr("settings.cancel", default="Cancel"), bg=BTN, fg="#ffffff", font=("Segoe UI", 10, "bold"), cursor="hand2", padx=14, pady=6)
    cancel_btn.pack(side="right")
    cancel_btn.bind("<Button-1>", lambda _e: on_close_settings())
    cancel_btn.bind("<Enter>", lambda _e: cancel_btn.config(bg=BTN_HOVER))
    cancel_btn.bind("<Leave>", lambda _e: cancel_btn.config(bg=BTN))

    win.bind("<Escape>", lambda _e: on_close_settings())
