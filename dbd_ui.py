# the ui for the control panel
# i really REALLY dont understand most of ts
# there was a lot of copy -> pasting in this one
# hate this dude tkinter
# also the try excepts in here are nuts
# i was gonna do proper except logging or messages or something
# but i never got around to it so they just prevent program crashes
# id say ill come back to it but i literally never will

import os
import sys
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import colorchooser, messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from dbd_controller import DATA_ROOT, OverlayController, PALETTE_EMOJI
import translations
from translations import tr
import settings_ui
import about_ui
from theme import ACCENT, ACCENT_HOVER, BG, BORDER, BTN, BTN_HOVER, FG, GREEN, MUTED, PANEL, PANEL2


class App(tk.Tk):
    # ts now over 1k lines balright

    def __init__(self) -> None:
        super().__init__()
        # clean leftover Temp from update_handler
        try:
            import updater

            updater.cleanup_temp()
        except Exception:
            pass
        self.title(tr("app.title"))
        self.iconbitmap(sys.executable)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.controller = OverlayController()
        self.update_queue = queue.Queue()
        self.updating = False
        self.icon_img = self.palette_img = None
        self.edit_entry = self.edit_label = self.edit_key = None
        self._tip = None
        self._settings_win = None
        self._about_win = None
        self._first_time_setup_active = False
        self._first_time_pending_survivor = False
        self._opacity_drag_poll_ms: int | None = None
        self._style()
        self.controller.start_server()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._sync_view()
        self.after(150, self._poll_update_status)
        # does first time setup if the assets arent in the save folder
        self.after(500, self._check_first_time_setup)
        # i do NOT remember adding this but i guess we auto check updates
        self.after(2000, self._auto_check_updates)

    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG,
                        arrowcolor=FG, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        insertcolor=FG, padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
                  selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", BTN_HOVER)
        self.option_add("*TCombobox*Listbox.selectForeground", FG)
        # updater progress bar styling - matches DBD dark theme
        style.configure("Update.Horizontal.TProgressbar", troughcolor=PANEL2, background=ACCENT, bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT, troughrelief="flat", relief="flat", thickness=8)
        style.layout("Update.Horizontal.TProgressbar", [("Horizontal.Progressbar.trough", {"children": [("Horizontal.Progressbar.pbar", {"side": "left", "sticky": "ns"})], "sticky": "nswe"})])

    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=18, pady=(16, 8))

        # top banner to say wait until killers and survivors loaded
        self.first_time_banner = tk.Frame(outer, bg=PANEL, highlightbackground=ACCENT, highlightthickness=1)
        self.first_time_label = tk.Label(self.first_time_banner, text=tr("status_messages.first_time_setup"), bg=PANEL, fg=ACCENT, font=("Segoe UI", 10, "bold"))
        self.first_time_label.pack(padx=12, pady=8)

        # top bar
        # has streak and that annoying ass settings button
        top_bar = tk.Frame(outer, bg=BG)
        self.top_bar = top_bar
        top_bar.pack(fill="x", pady=(0, 14))
        mode_row = tk.Frame(top_bar, bg=BG)
        mode_row.pack(side="left")
        self.header_streak_label = tk.Label(mode_row, text=tr("header.streak"), bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.header_streak_label.pack(side="left", padx=(0, 10))
        holder = tk.Frame(mode_row, bg=BORDER, highlightbackground=BORDER, highlightthickness=1)
        holder.pack(side="left")
        self.seg_global = self._segment(holder, tr("header.global"), "global")
        self.seg_char = self._segment(holder, tr("header.per_character"), "character")
        # settings button
        self.header_right = tk.Frame(top_bar, bg=BG)
        self.header_right.pack(side="right", anchor="n")
        self.settings_btn = tk.Label(self.header_right, text="⚙", font=("Segoe UI Symbol", 21), bg=BG, fg=MUTED, cursor="hand2")
        self.settings_btn.pack(side="right", padx=(8, 0))
        self.settings_btn.bind("<Button-1>", lambda _e: self._open_settings())
        self.settings_btn.bind("<Enter>", lambda _e: (self.settings_btn.config(fg=FG), self._show_tip(tr("tooltips.settings", default="Settings"))))
        self.settings_btn.bind("<Leave>", lambda _e: (self.settings_btn.config(fg=MUTED), self._hide_tip()))

        card = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        icon_frame = tk.Frame(card, bg=PANEL2, width=150, height=150,
                             highlightbackground=BORDER, highlightthickness=1)
        icon_frame.pack(side="right", padx=16, pady=16)
        icon_frame.pack_propagate(False)
        self.icon_label = tk.Label(icon_frame, bg=PANEL2)
        self.icon_label.pack(fill="both", expand=True)
        bar = tk.Frame(card, bg=BORDER, width=16)
        bar.pack(side="right", fill="y", pady=16)
        bar.pack_propagate(False)
        self.bar_top = self._role_button(bar, tr("role.killer_short"), "killer")
        self.bar_bottom = self._role_button(bar, tr("role.survivor_short"), "survivor")
        self.bar_top.pack(fill="both", expand=True, side="top")
        self.bar_bottom.pack(fill="both", expand=True, side="bottom")

        pick = tk.Frame(card, bg=PANEL)
        pick.pack(side="left", fill="both", expand=True, padx=16, pady=16)
        pick.columnconfigure(0, weight=1)
        self.combo, self.update_btn, _ = self._character_picker(pick, tr("picker.killer_label"), "killer", 0)
        self.scombo, self.s_update_btn, _ = self._character_picker(pick, tr("picker.survivor_label"), "survivor", 2)

        stats = tk.Frame(outer, bg=BG)
        stats.pack(fill="x", pady=14)
        self.cur_card = self._stat_card(stats, tr("stats.current"), ACCENT)
        self.pb_card = self._stat_card(stats, tr("stats.personal_best"), FG)
        self.wr_card = self._stat_card(stats, tr("stats.world_record"), FG, last=True)
        for label, key in ((self.cur_card, "current"), (self.pb_card, "pb"), (self.wr_card, "wr")):
            label._key = key
            label.configure(cursor="hand2")
            label.bind("<Button-1>", self._edit_stat)

        buttons = tk.Frame(outer, bg=BG)
        buttons.pack(fill="x", pady=(10, 0))
        self._action_buttons: list[tk.Label] = []
        self._action_button_keys = [
            "buttons.plus_one_win",
            "buttons.reset_streak",
            "buttons.reset_this_pb",
            "buttons.reset_all_pbs",
        ]
        for text, command, padding, primary in (
            (tr("buttons.plus_one_win"), self.inc, (0, 12), True),
            (tr("buttons.reset_streak"), self.reset, (0, 12), False),
            (tr("buttons.reset_this_pb"), self.reset_pb, (0, 12), False),
            (tr("buttons.reset_all_pbs"), self.reset_all_pbs, (0, 0), False),
        ):
            btn = self._make_button(buttons, text, command, ACCENT if primary else BTN,
                              ACCENT_HOVER if primary else BTN_HOVER)
            btn.pack(side="left", fill="x", expand=True, padx=padding, ipady=8)
            self._action_buttons.append(btn)

        self._build_background_controls(outer)
        self._build_obs_setup(outer)
        bottom = tk.Frame(outer, bg=BG)
        bottom.pack(fill="x", pady=(6, 0))
        # only way i could figure out how to get ready not to show
        initial_status = tr("status.ready") if getattr(self.controller, "show_status_messages", True) else ""
        self.status = tk.Label(bottom, text=initial_status, bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.status.pack(side="left")
        # copyright + info button
        self.bottom_right = tk.Frame(bottom, bg=BG)
        self.bottom_right.pack(side="right")
        self.about_btn = tk.Label(self.bottom_right, text="\u2139", font=("Segoe UI Symbol", 13), bg=BG, fg=MUTED, cursor="hand2")
        self.about_btn.pack(side="right")
        self.about_btn.bind("<Button-1>", lambda _e: self._open_about())
        self.about_btn.bind("<Enter>", lambda _e: (self.about_btn.config(fg=FG), self._show_tip(tr("tooltips.about", default="About"))))
        self.about_btn.bind("<Leave>", lambda _e: (self.about_btn.config(fg=MUTED), self._hide_tip()))
        self.copyright_label = tk.Label(self.bottom_right, text="Copyright (c) 2026 Proxi", bg=BG, fg=MUTED, font=("Segoe UI", 7))
        self.copyright_label.pack(side="right", padx=(0, 6))

    def _role_button(self, parent, label, role):  # tuff ahh killer survivor switcher
        button = tk.Label(parent, text=label, bg=PANEL2, fg=MUTED, font=("Segoe UI", 8, "bold"), cursor="hand2")
        button.bind("<Button-1>", lambda _event: self._activate_role(role))
        button.bind("<Enter>", lambda _event, r=role: self._show_tip(tr(f"tooltips.role_{r}", default=r.upper())))
        button.bind("<Leave>", lambda _event: self._hide_tip())
        return button

    def _character_picker(self, parent, label, role, row):  # dropdowns and download buttons
        label_frame = tk.Frame(parent, bg=PANEL)
        label_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(12 if row else 0, 0))
        picker_label = tk.Label(label_frame, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"))
        picker_label.pack(side="left")
        if role == "killer":
            self.killer_picker_label = picker_label
        else:
            self.survivor_picker_label = picker_label
        # little "(Downloading: NAME)" next to character type label
        downloading_label = tk.Label(label_frame, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "italic"))
        downloading_label.pack(side="left", padx=(8, 0))
        if role == "killer":
            self.killer_downloading_label = downloading_label
        else:
            self.survivor_downloading_label = downloading_label
        combo = ttk.Combobox(parent, state="readonly", font=("Segoe UI", 11))
        combo.grid(row=row + 1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        combo.bind("<<ComboboxSelected>>", lambda _event: self._select(role, combo.get()))
        # progress bar for downloads
        progress = ttk.Progressbar(parent, style="Update.Horizontal.TProgressbar", mode="determinate", maximum=100)
        progress.grid(row=row + 1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        progress.grid_remove()
        update = tk.Label(parent, text="⬇", bg=BTN, fg="#ffffff", font=("Segoe UI Symbol", 13, "bold"),
                          cursor="hand2", padx=10, pady=2, highlightbackground=BORDER, highlightthickness=1)
        update.grid(row=row + 1, column=1, sticky="ns", pady=(4, 0))
        update.bind("<Button-1>", lambda _event: self._start_update(role))
        update.bind("<Enter>", lambda _event: self._update_hover(role, True))
        update.bind("<Leave>", lambda _event: self._update_hover(role, False))
        # lets you switch between dropdown and progress bar
        if role == "killer":
            self.killer_progress = progress
            self.killer_combo = combo
        else:
            self.survivor_progress = progress
            self.survivor_combo = combo
        return combo, update, progress

    def _stat_card(self, parent, title, color, last=False):  # shows current pb and wr
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=(0, 0 if last else 12))
        title_label = tk.Label(card, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"))
        title_label.pack(anchor="w", padx=16, pady=(12, 0))
        value = tk.Label(card, text="0", bg=PANEL, fg=color, font=("Segoe UI", 30, "bold"))
        value.pack(anchor="w", padx=16, pady=(0, 12))
        value._card = card
        value._title_label = title_label
        return value

    def _segment(self, parent, text, mode):  # global and percharacter switcher i think but idk why its down here
        segment = tk.Label(parent, text=text, bg=BTN, fg=FG, font=("Segoe UI", 9, "bold"), cursor="hand2", padx=14, pady=4)
        segment.pack(side="left")
        segment.bind("<Button-1>", lambda _event: self._set_streak_mode(mode))
        segment.bind("<Enter>", lambda _event: self._seg_hover(mode, True))
        segment.bind("<Leave>", lambda _event: self._seg_hover(mode, False))
        return segment

    def _build_background_controls(self, outer):  # opacity slider and color picker
        background = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        background.pack(fill="x", pady=(10, 0))
        self.background_title_label = tk.Label(background, text=tr("background.title"), bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.background_title_label.pack(anchor="w", padx=16, pady=(10, 2))
        controls = tk.Frame(background, bg=PANEL)
        controls.pack(fill="x", padx=16, pady=(0, 12))
        self.bg_opacity_scale = tk.Scale(controls, from_=0, to=100, orient="horizontal", showvalue=False,
                                         bg=PANEL, fg=FG, troughcolor=PANEL2, highlightthickness=0,
                                         activebackground=ACCENT, sliderrelief="flat", bd=0, command=self._on_bg_opacity_drag)
        self.bg_opacity_scale.pack(side="left", fill="x", expand=True, padx=(0, 12))
        # trying to prevent gigawriting to config for the overlay change
        self.bg_opacity_scale.bind("<ButtonPress-1>", self._on_bg_opacity_press)
        self.bg_opacity_scale.bind("<ButtonRelease-1>", self._on_bg_opacity_release)
        self.bg_opacity_label = tk.Label(controls, bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold"))
        self.bg_opacity_label.pack(side="left", padx=(0, 12))
        self.bg_color_btn = tk.Canvas(controls, width=44, height=28, cursor="hand2", highlightbackground=BORDER, highlightthickness=1)
        self.bg_color_btn.pack(side="left")
        self.bg_color_btn.bind("<Button-1>", lambda _event: self._pick_bg_color())
        self.bg_color_btn.bind("<Configure>", lambda _event: self._draw_palette())

    def _build_obs_setup(self, outer):  # obs setup stuff
        setup = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        setup.pack(fill="x", pady=(14, 0))
        self.obs_title_label = tk.Label(setup, text=tr("obs.title"), bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"))
        self.obs_title_label.pack(anchor="w", padx=16, pady=(12, 0))
        row = tk.Frame(setup, bg=PANEL)
        row.pack(fill="x", padx=16, pady=(6, 0))
        self.url_label = tk.Label(row, bg=PANEL, fg=FG, font=("Segoe UI", 11), cursor="hand2")
        self.url_label.pack(side="left")
        self.url_label.bind("<Button-1>", lambda _event: self._copy_url())
        self.obs_copy_btn = self._make_button(row, tr("obs.copy"), self._copy_url, BTN, BTN_HOVER)
        self.obs_copy_btn.pack(side="left", padx=(10, 0))
        self.obs_open_btn = self._make_button(row, tr("obs.open"), self._open_url, BTN, BTN_HOVER)
        self.obs_open_btn.pack(side="left", padx=(8, 0))
        self.copy_indicator = tk.Label(row, text="", bg=PANEL, fg=GREEN, font=("Segoe UI", 10, "bold"))
        self.copy_indicator.pack(side="left", padx=(10, 0))
        self.obs_step_labels: list[tk.Label] = []
        for text, padding in ((tr("obs.step1"), (10, 0)),
                              (tr("obs.step2"), (0, 0)),
                              (tr("obs.step3"), (0, 12))):
            lbl = tk.Label(setup, text=text, bg=PANEL, fg=MUTED, font=("Segoe UI", 10))
            lbl.pack(anchor="w", padx=16, pady=padding)
            self.obs_step_labels.append(lbl)

    def _make_button(self, parent, text, command, background, hover):  # some bs i needed at some point idk
        button = tk.Label(parent, text=text, bg=background, fg="#ffffff", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=8, pady=8)
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.config(bg=hover))
        button.bind("<Leave>", lambda _event: button.config(bg=background))
        return button

    def refresh_translations(self):
        # runs after settings language switch
        # buncha spaghetti code because i dont know how else to do the translations
        try:
            self.title(tr("app.title"))
        except Exception:
            pass
        try:
            self.first_time_label.config(text=tr("status_messages.first_time_setup"))
        except Exception:
            pass
        try:
            self.header_streak_label.config(text=tr("header.streak"))
        except Exception:
            pass
        try:
            self.seg_global.config(text=tr("header.global"))
            self.seg_char.config(text=tr("header.per_character"))
        except Exception:
            pass
        try:
            self.bar_top.config(text=tr("role.killer_short"))
            self.bar_bottom.config(text=tr("role.survivor_short"))
        except Exception:
            pass
        try:
            if hasattr(self, "killer_picker_label"):
                self.killer_picker_label.config(text=tr("picker.killer_label"))
            if hasattr(self, "survivor_picker_label"):
                self.survivor_picker_label.config(text=tr("picker.survivor_label"))
        except Exception:
            pass
        try:
            self.cur_card._title_label.config(text=tr("stats.current"))
            self.pb_card._title_label.config(text=tr("stats.personal_best"))
            self.wr_card._title_label.config(text=tr("stats.world_record"))
        except Exception:
            pass
        try:
            for btn, key in zip(getattr(self, "_action_buttons", []), getattr(self, "_action_button_keys", [])):
                btn.config(text=tr(key))
        except Exception:
            pass
        try:
            self.background_title_label.config(text=tr("background.title"))
        except Exception:
            pass
        try:
            self.obs_title_label.config(text=tr("obs.title"))
            self.obs_copy_btn.config(text=tr("obs.copy"))
            self.obs_open_btn.config(text=tr("obs.open"))
            steps = [tr("obs.step1"), tr("obs.step2"), tr("obs.step3")]
            for lbl, txt in zip(getattr(self, "obs_step_labels", []), steps):
                lbl.config(text=txt)
        except Exception:
            pass
        # refresh debug messages
        try:
            if not getattr(self.controller, "show_status_messages", True):
                self.status.config(text="")
            else:
                try:
                    cur = str(self.status.cget("text"))
                except Exception:
                    cur = ""
                if cur != "":
                    # genuinely dont know what i was doing it cant be that hard
                    try:
                        candidates: set[str] = set()
                        for info in translations.list_available_translations():
                            try:
                                data = translations.load_translation(info["code"])
                                val = data.get("status", {}).get("ready") if isinstance(data.get("status"), dict) else None
                                if isinstance(val, str):
                                    candidates.add(val)
                            except Exception:
                                continue
                        try:
                            candidates.add(tr("status.ready"))
                        except Exception:
                            pass
                        if cur in candidates:
                            self.status.config(text=tr("status.ready"))
                    except Exception:
                        pass
        except Exception:
            pass
        # refresh about window if open
        try:
            win = getattr(self, "_about_win", None)
            if win is not None and win.winfo_exists():
                try:
                    win.title(tr("about.title", default="About"))
                except Exception:
                    pass
                try:
                    if hasattr(win, "_version_label") and hasattr(win, "_version_str"):
                        win._version_label.config(text=f"{tr('about.version', default='Version')}: {win._version_str}")
                except Exception:
                    pass
                try:
                    if hasattr(win, "_check_label"):
                        win._check_label.config(text=tr("about.check_updates", default="Check for Updates"))
                except Exception:
                    pass
                try:
                    if hasattr(win, "_credits_title"):
                        win._credits_title.config(text=tr("about.credits", default="Credits"))
                except Exception:
                    pass
        except Exception:
            pass

    def _sync_view(self) -> None:
        state = self.controller
        self.combo.configure(values=state.k_names)
        self.scombo.configure(values=state.s_names)
        if state.killer:
            self.combo.set(state.killer)
        if state.survivor:
            self.scombo.set(state.survivor)
        self.url_label.configure(text=state.overlay_url)
        self._refresh_role()
        self._refresh_mode()
        self._refresh_stats()
        self._refresh_background()
        self._update_icon()

    def _refresh_role(self) -> None:
        killer_active = self.controller.active_role == "killer"
        self.bar_top.config(bg=ACCENT if killer_active else PANEL2, fg="#ffffff" if killer_active else MUTED)
        self.bar_bottom.config(bg=ACCENT if not killer_active else PANEL2, fg="#ffffff" if not killer_active else MUTED)

    def _refresh_mode(self) -> None:
        global_active = self.controller.streak_mode == "global"
        self.seg_global.config(bg=ACCENT if global_active else BTN, fg="#ffffff" if global_active else FG)
        self.seg_char.config(bg=ACCENT if not global_active else BTN, fg="#ffffff" if not global_active else FG)

    def _refresh_stats(self) -> None:
        state = self.controller
        self.cur_card.config(text=str(state.current))
        self.pb_card.config(text=str(state.pb), fg=GREEN if state.current > 0 and state.current >= state.pb else FG)
        self.wr_card.config(text="?" if state.wr is None else str(state.wr))

    def _refresh_background(self) -> None:
        self.bg_opacity_scale.set(self.controller.bg_opacity)
        self.bg_opacity_label.config(text=f"{self.controller.bg_opacity}%")
        self.bg_color_btn.config(bg=self.controller.bg_color)
        self._draw_palette()

    def _select(self, role: str, name: str) -> None:
        if name:
            self._cancel_stat()
            self.controller.select(role, name)
            self._sync_view()

    def _activate_role(self, role: str) -> None:
        if role != self.controller.active_role:
            self._cancel_stat()
            self.controller.select(role)
            self._sync_view()

    def _set_streak_mode(self, mode: str) -> None:
        if mode != self.controller.streak_mode:
            self._cancel_stat()
            self.controller.set_streak_mode(mode)
            self._sync_view()
            if mode == "global":
                self._set_status(tr("status_messages.streak_mode_global"))
            else:
                self._set_status(tr("status_messages.streak_mode_per_character"))

    def _seg_hover(self, mode: str, hovered: bool) -> None:
        if mode != self.controller.streak_mode:
            (self.seg_global if mode == "global" else self.seg_char).config(bg=BTN_HOVER if hovered else BTN)

    def _update_icon(self) -> None:
        path = self.controller.icon_path
        if not path:
            self.icon_label.configure(image="")
            return
        try:
            image = Image.open(path).convert("RGBA")
            image.thumbnail((150, 150), Image.LANCZOS)
            self.icon_img = ImageTk.PhotoImage(image)
            self.icon_label.configure(image=self.icon_img)
        except Exception as exc:
            # missing portrait somehow
            if os.environ.get("DBD_UI_DEBUG"):
                print(f"Could not load icon {path}: {exc}")
            self.icon_label.configure(image="")

    def inc(self):  # +1 w rp
        if not self.controller.selected:
            return
        new_pb = self.controller.increment()
        self._refresh_stats()
        if new_pb:
            self._set_status(tr("status_messages.new_pb", value=self.controller.pb))
        elif self.controller.streak_mode == "global":
            self._set_status(tr("status_messages.streak_now_global", value=self.controller.current))
        else:
            self._set_status(tr("status_messages.streak_now_character", name=self.controller.selected, value=self.controller.current))

    def reset(self):  # reset current streak to 0
        if not self.controller.selected:
            return
        name, mode = self.controller.selected, self.controller.streak_mode
        self.controller.reset_streak()
        self._refresh_stats()
        if mode == "global":
            self._set_status(tr("status_messages.reset_global_streak"))
        else:
            self._set_status(tr("status_messages.reset_character_streak", name=name))

    def _edit_stat(self, event):  # click to edit
        label = event.widget
        key = getattr(label, "_key", None)
        if not self.controller.selected or not key or self.edit_entry is not None:
            return
        value = {"current": self.controller.current, "pb": self.controller.pb,
                 "wr": "?" if self.controller.wr is None else self.controller.wr}[key]
        label.pack_forget()
        self.edit_key, self.edit_label = key, label
        self.edit_entry = tk.Entry(label._card, bg=PANEL, fg=FG, insertbackground=FG, font=("Segoe UI", 30, "bold"),
                                   relief="flat", highlightbackground=BORDER, highlightcolor=ACCENT, highlightthickness=1,
                                   width=max(len(str(value)), 4))
        self.edit_entry.insert(0, str(value))
        self.edit_entry.pack(anchor="w", padx=16, pady=(4, 8))
        self.edit_entry.focus_set()
        self.edit_entry.select_range(0, "end")
        self.edit_entry.bind("<Return>", self._commit_stat)
        self.edit_entry.bind("<FocusOut>", self._commit_stat)
        self.edit_entry.bind("<Escape>", self._cancel_stat)

    def _commit_stat(self, _event=None):
        if self.edit_entry is None:
            return
        key, raw = self.edit_key, self.edit_entry.get().strip()
        try:
            value = None if key == "wr" and raw in ("", "?") else int(raw.replace(",", ""))
            self.controller.set_stat(key, value)
        except ValueError:
            self._finish_stat_edit()
            return
        name, mode = self.controller.selected, self.controller.streak_mode
        self._finish_stat_edit()
        self._refresh_stats()
        if key == "wr":
            display = "?" if value is None else str(value)
            self._set_status(tr("status_messages.world_record_set", name=name, value=display))
        elif key == "current":
            if mode == "global":
                self._set_status(tr("status_messages.global_streak_set", value=value))
            else:
                self._set_status(tr("status_messages.character_streak_set", name=name, value=value))
        else:
            if mode == "global":
                self._set_status(tr("status_messages.global_pb_set", value=value))
            else:
                self._set_status(tr("status_messages.character_pb_set", name=name, value=value))

    def _cancel_stat(self, _event=None):
        self._finish_stat_edit()

    def _finish_stat_edit(self):
        entry, label = self.edit_entry, self.edit_label
        self.edit_entry = self.edit_label = self.edit_key = None
        if entry:
            entry.destroy()
        if label:
            label.pack(anchor="w", padx=16, pady=(0, 12))

    def reset_pb(self):
        if not self.controller.selected:
            return
        is_global = self.controller.streak_mode == "global"
        target = tr("misc.global_streak") if is_global else self.controller.selected
        if messagebox.askyesno(tr("dialogs.reset_pb_title"), tr("dialogs.reset_pb_message", target=target), parent=self):
            self.controller.reset_personal_best()
            self._refresh_stats()
            self._set_status(tr("status_messages.reset_pb_done", target=target))

    def reset_all_pbs(self):  # wipes all PBs for role or global if set global
        global_mode = self.controller.streak_mode == "global"
        label_key = "survivor" if self.controller.active_role == "survivor" else "killer"
        label = tr(f"misc.{label_key}")
        if global_mode:
            prompt = tr("dialogs.reset_all_pbs_message_global")
        else:
            prompt = tr("dialogs.reset_all_pbs_message_role", role=label)
        if messagebox.askyesno(tr("dialogs.reset_all_pbs_title"), prompt, parent=self):
            self.controller.reset_all_personal_bests()
            self._refresh_stats()
            if global_mode:
                self._set_status(tr("status_messages.reset_all_pbs_done_global"))
            else:
                self._set_status(tr("status_messages.reset_all_pbs_done_role", role=label))

    def _on_bg_opacity_drag(self, value):
        # this writes to opacity_preview.txt not config.json but i dont know why i have it write at all
        try:
            val = max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            val = self.controller.bg_opacity
        self.bg_opacity_label.config(text=f"{val}%")
        if self._opacity_drag_poll_ms is not None:
            self.controller.set_opacity_preview(val)

    def _on_bg_opacity_press(self, _event=None):
        # speed up update while drag so it doesnt feel like its lagging so bad
        if self._opacity_drag_poll_ms is None:
            self._opacity_drag_poll_ms = self.controller.poll_milliseconds
            self.controller.set_temporary_poll_milliseconds(25)
            try:
                self.controller.set_opacity_preview(int(self.bg_opacity_scale.get()))
            except (TypeError, ValueError):
                self.controller.set_opacity_preview(self.controller.bg_opacity)

    def _on_bg_opacity_release(self, _event=None):
        # only now save to config.json
        try:
            val = int(self.bg_opacity_scale.get())
        except (TypeError, ValueError):
            try:
                val = int(float(self.bg_opacity_scale.get()))
            except Exception:
                val = self.controller.bg_opacity
        previous_poll_ms = self._opacity_drag_poll_ms
        self._opacity_drag_poll_ms = None
        self.controller.set_background(opacity=val, poll_milliseconds=previous_poll_ms)
        self.controller.clear_opacity_preview()
        self.bg_opacity_label.config(text=f"{self.controller.bg_opacity}%")

    def _pick_bg_color(self) -> None:
        result = colorchooser.askcolor(color=self.controller.bg_color, parent=self, title=tr("background.color_picker_title"))
        if result and result[1]:
            self.controller.set_background(color=result[1])
            self._refresh_background()

    def _draw_palette(self):  # draws the little palette emoji on color button
        canvas = self.bg_color_btn
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            return
        if self.palette_img is None and PALETTE_EMOJI.is_file():
            try:
                image = Image.open(PALETTE_EMOJI)
                image.thumbnail((24, 24), Image.LANCZOS)
                self.palette_img = ImageTk.PhotoImage(image)
            except Exception:
                pass
        if self.palette_img:
            canvas.create_image(width // 2, height // 2, image=self.palette_img)

    def _copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.controller.overlay_url)
        self.update()
        self.copy_indicator.config(text=tr("obs.copied"))
        self.after(1800, lambda: self.copy_indicator.config(text=""))

    def _open_url(self):
        try:
            webbrowser.open(self.controller.overlay_url)
        except Exception:
            pass

    def _update_hover(self, kind, hovered):
        if self.updating:
            return
        button = self.update_btn if kind == "killer" else self.s_update_btn
        button.config(bg=BTN_HOVER if hovered else BTN)
        if hovered:
            if kind == "killer":
                self._show_tip(tr("picker.update_tooltip_killer"))
            else:
                self._show_tip(tr("picker.update_tooltip_survivor"))
        else:
            self._hide_tip()

    def _show_tip(self, text):
        self._hide_tip()
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.wm_attributes("-topmost", True)
        x, y = self.winfo_pointerxy()
        tip.wm_geometry(f"+{x + 12}+{y + 14}")
        tk.Label(tip, text=text, bg="#202020", fg="#f4f4f4", relief="solid", borderwidth=1,
                 padx=8, pady=4, font=("Segoe UI", 9)).pack()
        self._tip = tip

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _start_update(self, kind, force=False):  # updates characters
        if self.updating and not force:
            return
        self.updating = True
        (self.update_btn if kind == "killer" else self.s_update_btn).config(state="disabled", bg=BTN)
        # replace dropdown with loading bar
        if kind == "killer":
            self.combo.grid_remove()
            self.killer_progress.config(value=0, maximum=100)
            self.killer_progress.grid()
            try:
                self.killer_downloading_label.config(text="")
            except Exception:
                pass
        else:
            self.scombo.grid_remove()
            self.survivor_progress.config(value=0, maximum=100)
            self.survivor_progress.grid()
            try:
                self.survivor_downloading_label.config(text="")
            except Exception:
                pass
        threading.Thread(target=self._update_worker, args=(kind,), daemon=True).start()

    def _update_worker(self, kind):
        def _progress(done: int, total: int, name: str | None = None) -> None:
            # total has to be known so you know how far the bar needs to go per download
            self.update_queue.put(("progress", kind, done, total, name))
        try:
            new = self.controller.update_characters(kind, status=self.update_queue.put, progress=_progress)
            self.update_queue.put(("done", kind, new))
        except Exception as exc:
            self.update_queue.put(tr("status_messages.update_failed", error=str(exc)))
            self.update_queue.put(("done", kind, None))

    def _poll_update_status(self):  # called every 150ms to pull progress from queue
        try:
            while True:
                message = self.update_queue.get_nowait()
                if isinstance(message, tuple) and message[0] == "done":
                    self._finish_update(message[1], message[2])
                elif isinstance(message, tuple) and message[0] == "progress":
                    # made it support both (progress, kind, done, total) and (progress, kind, done, total, name)
                    if len(message) == 5:
                        _, kind, done, total, name = message
                    else:
                        _, kind, done, total = message
                        name = None
                    bar = self.killer_progress if kind == "killer" else self.survivor_progress
                    label = self.killer_downloading_label if kind == "killer" else self.survivor_downloading_label
                    try:
                        # can be 0 or None but i dont remember why
                        if total is None or int(total) == 0:
                            bar.config(maximum=100, value=0)
                        else:
                            total_int = max(1, int(total))
                            done_int = max(0, min(int(done), total_int))
                            bar.config(maximum=total_int, value=done_int)
                    except (ValueError, TypeError):
                        try:
                            bar.config(maximum=100, value=0)
                        except Exception:
                            pass  # how is it gone dawg
                    # show downloading text
                    try:
                        if name:
                            # i had some random bs happening where the translation would work for the word downloading
                            # so i hardcoded it sue me
                            label.config(text=f"(Downloading {name})")
                        elif done == 0:
                            label.config(text="")
                    except Exception:
                        try:
                            if name:
                                label.config(text=f"(Downloading {name})")
                            elif done == 0:
                                label.config(text="")
                        except Exception:
                            pass
                else:
                    self._set_status(str(message))
        except queue.Empty:
            pass
        self.after(150, self._poll_update_status)

    def _finish_update(self, kind, new):
        # lot of crap but basically if its first time
        # dont stop marking as active until both killer and survivor are updated
        is_first_time = getattr(self, "_first_time_setup_active", False)
        if is_first_time and kind == "killer":
            try:
                (self.update_btn if kind == "killer" else self.s_update_btn).config(state="normal")
            except Exception:
                pass
            if kind == "killer":
                try:
                    self.killer_progress.grid_remove()
                except Exception:
                    pass
                try:
                    self.combo.grid()
                except Exception:
                    pass
                try:
                    self.killer_downloading_label.config(text="")
                except Exception:
                    pass
            else:
                try:
                    self.survivor_progress.grid_remove()
                except Exception:
                    pass
                try:
                    self.scombo.grid()
                except Exception:
                    pass
                try:
                    self.survivor_downloading_label.config(text="")
                except Exception:
                    pass
            self._sync_view()
            self.updating = True
            self.after(400, lambda: self._start_update("survivor", force=True))
            return
        elif is_first_time and kind == "survivor":
            self.updating = False
            (self.update_btn if kind == "killer" else self.s_update_btn).config(state="normal")
            if kind == "killer":
                try:
                    self.killer_progress.grid_remove()
                except Exception:
                    pass
                try:
                    self.combo.grid()
                except Exception:
                    pass
                try:
                    self.killer_downloading_label.config(text="")
                except Exception:
                    pass
            else:
                try:
                    self.survivor_progress.grid_remove()
                except Exception:
                    pass
                try:
                    self.scombo.grid()
                except Exception:
                    pass
                try:
                    self.survivor_downloading_label.config(text="")
                except Exception:
                    pass
            self._sync_view()
            self._first_time_setup_active = False
            self._hide_first_time_banner()
            try:
                self.status.config(text=tr("status.ready") if getattr(self.controller, "show_status_messages", True) else "")
            except Exception:
                pass
            return
        # simple shi if not first tinme
        self.updating = False
        (self.update_btn if kind == "killer" else self.s_update_btn).config(state="normal")
        # switch back to dropdown and nuke downloading text
        if kind == "killer":
            try:
                self.killer_progress.grid_remove()
            except Exception:
                pass
            try:
                self.combo.grid()
            except Exception:
                pass
            try:
                self.killer_downloading_label.config(text="")
            except Exception:
                pass
        else:
            try:
                self.survivor_progress.grid_remove()
            except Exception:
                pass
            try:
                self.scombo.grid()
            except Exception:
                pass
            try:
                self.survivor_downloading_label.config(text="")
            except Exception:
                pass
        self._sync_view()
        # bit doubled up code but it was breaking sometimes idk why
        label = tr("misc.killers") if kind == "killer" else tr("misc.survivors")
        if new:
            self._set_status(tr("status_messages.update_complete", count=len(new), label=label))
        else:
            self._set_status(tr("status_messages.no_new_found", label=label))

    def _set_status(self, text):
        # status bar at bottom
        try:
            if not getattr(self.controller, "show_status_messages", True):
                return
        except Exception:
            pass
        try:
            self.status.config(text=str(text))
        except Exception:
            pass

    def _open_settings(self):
        settings_ui.open_settings(self)

    def _open_about(self):
        about_ui.open_about(self)

    def _check_first_time_setup(self):
        # check if its first run bc Documents/DBD Overlay will be empty
        try:
            killer_icons = DATA_ROOT / "assets" / "killer_icons"
            surv_icons = DATA_ROOT / "assets" / "survivor_icons"
            has_killer = killer_icons.exists() and any(killer_icons.glob("*.png"))
            has_surv = surv_icons.exists() and any(surv_icons.glob("*.png"))
            # only skip if BOTH surv and killer have their icons
            # idk it just felt right
            if has_killer and has_surv:
                return
            # If one side missing, still trigger chain but updater will handle 0 new
            if not has_killer and not has_surv:
                pass
            elif not has_killer or not has_surv:
                # dont know why just one would be missing
                pass
            self._first_time_setup_active = True
            self._show_first_time_banner()
            self._set_status(tr("status_messages.first_time_setup"))
            self.after(300, lambda: self._start_update("killer"))
        except Exception:
            pass

    def _auto_check_updates(self):
        # check github for new exe in background
        try:
            import threading

            def _worker() -> None:
                try:
                    import updater

                    avail, _info, cur, latest = updater.check_for_updates()
                    if avail:
                        # show in debug bar
                        try:
                            self.after(0, lambda: self._set_status(f"Update available: {latest} (current {cur}) - see About"))
                        except Exception:
                            pass
                except Exception:
                    pass

            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _show_first_time_banner(self):
        try:
            if hasattr(self, "first_time_banner") and self.first_time_banner.winfo_exists():
                # how is bro already there
                if self.first_time_banner.winfo_ismapped():
                    return
            try:
                self.first_time_banner.pack(fill="x", pady=(0, 12), before=self.top_bar)
            except Exception:
                # theres no way
                try:
                    self.first_time_banner.pack(fill="x", pady=(0, 12))
                except Exception:
                    pass
        except Exception:
            pass

    def _hide_first_time_banner(self):
        try:
            if hasattr(self, "first_time_banner"):
                self.first_time_banner.pack_forget()
        except Exception:
            pass

    def on_close(self):
        try:
            self.controller.close()
        finally:
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
