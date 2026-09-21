#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aria2配置界面 (参数对齐修正版)"""
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from config import APP_TITLE, Theme, DEFAULT_USER_AGENT
from utils import extract_urls_and_out, extract_referer
from ipc_server import try_send_to_main_instance
from ui_styles import (
    create_label, create_entry, create_spinbox, create_checkbox, 
    create_button, center_window, FONT_SMALL, FONT_NORMAL, add_context_menu
)

# 底部按钮与内容的视觉安全边距
HEIGHT_SAFETY_PAD = 10


class Aria2ConfigGUI(ctk.CTkToplevel):
    """Aria2配置界面"""
    
    def __init__(self, parent, is_master=True, auto_referer=False, on_submit=None, initial_log_file=None):
        super().__init__(parent)
        self.is_master = is_master
        self.launch_cfg = None
        self.on_submit = on_submit
        self.initial_log_file = initial_log_file
        self.auto_referer_init = auto_referer   # 保存命令行传入的初始值
        self.current_tab = "link"
        try:
            from config import load_config as _lc
            self._current_theme = _lc().get("theme") or "midnight"
        except Exception:
            self._current_theme = "midnight"
        self._history = self._load_history()
        self._history_popup = None
        self._initial_positioned = False
        self.title(APP_TITLE)
        self.configure(fg_color=Theme.BG) 
        self.resizable(True, True)
        
        self._build_ui()
        
        self.geometry("640x420")
        self.after(50, self._apply_dynamic_height)
        
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_dynamic_height(self):
        try:
            self.update_idletasks()
            phys_h = self.winfo_reqheight()
            try:
                sc = ctk.ScalingTracker.get_window_scaling(self)
            except Exception:
                sc = 1.0
            logical_h = int(phys_h / sc) if sc > 0 else phys_h
            logical_h = max(300, min(900, logical_h)) + HEIGHT_SAFETY_PAD
            if not self._initial_positioned:
                center_window(self, 640, logical_h)
                self._initial_positioned = True
            else:
                x = self.winfo_x()
                y = self.winfo_y()
                self.geometry(f"640x{logical_h}+{x}+{y}")
        except Exception:
            pass

    def _on_close(self):
        self.destroy()

    def _build_ui(self):
        """构建界面（Motrix 风格）"""
        card = ctk.CTkFrame(self, fg_color=Theme.CARD, corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=15)

        # ===== 顶部选项卡 =====
        tab_bar = ctk.CTkFrame(card, fg_color="transparent")
        tab_bar.pack(fill="x", padx=20, pady=(12, 0))

        def _make_tab(text, key):
            return ctk.CTkButton(
                tab_bar, text=text, width=100, height=30,
                fg_color="transparent", hover_color="#4b5563",
                text_color=Theme.MUTED,
                font=(FONT_NORMAL[0], 13, "bold"),
                corner_radius=0, border_width=0,
                command=lambda k=key: self._switch_tab(k),
            )

        self.tab_link_btn = _make_tab("链接任务", "link")
        self.tab_seed_btn = _make_tab("种子任务", "seed")
        self.tab_link_btn.pack(side="left")
        self.tab_seed_btn.pack(side="left", padx=(20, 0))

        ctk.CTkFrame(card, height=1, fg_color="#4b5563").pack(
            fill="x", padx=20, pady=(5, 12))

        # ===== 内容容器 =====
        self.content_container = ctk.CTkFrame(card, fg_color="transparent")
        self.content_container.pack(fill="x", padx=20)

        # --- 链接 tab ---
        self.tab_link_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.url_text = ctk.CTkTextbox(
            self.tab_link_frame, height=100, font=FONT_SMALL,
            fg_color="#2d3748", text_color=Theme.TEXT,
            corner_radius=6, wrap="word",
        )
        self.url_text.pack(fill="x")
        add_context_menu(self.url_text)

        # --- 种子 tab ---
        self.tab_seed_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.drop_canvas = tk.Canvas(
            self.tab_seed_frame, height=120,
            bg="#2d3748", highlightthickness=0, bd=0,
        )
        self.drop_canvas.pack(fill="x")
        self.drop_canvas.bind("<Configure>", self._draw_drop_border)
        self.drop_canvas.bind("<Button-1>", lambda e: self._browse_torrent())
        try:
            self.drop_canvas.configure(cursor="hand2")
        except Exception:
            pass

        self.seed_files_label = ctk.CTkLabel(
            self.tab_seed_frame, text="", text_color=Theme.SEMI_MUTED,
            font=FONT_SMALL, anchor="w", justify="left",
        )
        self.seed_files_label.pack(fill="x", pady=(8, 0))

        # 默认显示链接 tab
        self.tab_link_frame.pack(fill="x")
        self._set_tab_active("link")

        # ===== 核心区：重命名 + 分片数 =====
        row1 = ctk.CTkFrame(self.content_container, fg_color="transparent")
        row1.pack(fill="x", pady=(15, 0))

        create_label(row1, "重命名:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.title_var = tk.StringVar()
        create_entry(row1, self.title_var).pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(row1, width=20, height=1, fg_color="transparent").pack(side="left")

        create_label(row1, "分片数:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.split = create_spinbox(row1, initial=5, width=60)
        self.split.pack(side="left")

        # ===== 存储路径 =====
        row2 = ctk.CTkFrame(self.content_container, fg_color="transparent")
        row2.pack(fill="x", pady=(10, 0))

        create_label(row2, "存储路径:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self._clock_btn = ctk.CTkButton(
            row2, text="\u23f1", width=30, height=26,
            fg_color="#2d3748", hover_color="#4b5563",
            text_color=Theme.TEXT, font=("Segoe UI Symbol", 14),
            corner_radius=6, border_width=0,
            command=self._show_path_history,
        )
        self._clock_btn.pack(side="left", padx=(0, 5))
        self.path_var = tk.StringVar(value=os.path.expanduser("~\\Downloads"))
        create_entry(row2, self.path_var).pack(side="left", fill="x", expand=True)
        create_button(row2, text="浏览", command=self._browse_folder,
                      width=60, style="secondary").pack(side="right", padx=(5, 0))

        # ===== 高级选项容器（默认隐藏）=====
        self.advanced_container = ctk.CTkFrame(self.content_container, fg_color="transparent")

        ua_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        ua_row.pack(fill="x", pady=(10, 0))
        create_label(ua_row, "User-Agent:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.ua_var = tk.StringVar(value=DEFAULT_USER_AGENT)
        create_entry(ua_row, self.ua_var).pack(side="left", fill="x", expand=True)

        ref_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        ref_row.pack(fill="x", pady=(10, 0))
        create_label(ref_row, "Referer:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.referer_var = tk.StringVar()
        create_entry(ref_row, self.referer_var).pack(side="left", fill="x", expand=True)

        self.auto_referer_var = tk.BooleanVar(value=self.auto_referer_init)
        cb = create_checkbox(self.advanced_container, "自动提取 Referer", self.auto_referer_var)
        cb.pack(anchor="w", padx=(75, 0), pady=(2, 0))
        cb.configure(command=self._toggle_auto_referer)

        auth_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        auth_row.pack(fill="x", pady=(10, 0))
        create_label(auth_row, "Authorization:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.auth_var = tk.StringVar()
        create_entry(auth_row, self.auth_var).pack(side="left", fill="x", expand=True)

        cookie_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        cookie_row.pack(fill="x", pady=(10, 0))
        create_label(cookie_row, "Cookie:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.cookie_var = tk.StringVar()
        create_entry(cookie_row, self.cookie_var).pack(side="left", fill="x", expand=True)

        proxy_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        proxy_row.pack(fill="x", pady=(10, 0))
        create_label(proxy_row, "代理:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.proxy_var = tk.StringVar()
        create_entry(proxy_row, self.proxy_var).pack(side="left", fill="x", expand=True)

        pr1 = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        pr1.pack(fill="x", pady=(10, 0))
        create_label(pr1, "最大连接数:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.max_conn = create_spinbox(pr1, initial=16, width=60)
        self.max_conn.pack(side="left")

        ctk.CTkFrame(pr1, width=20, height=1, fg_color="transparent").pack(side="left")

        create_label(pr1, "文件分配:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.file_allocation = ctk.CTkComboBox(
            pr1, values=["none", "prealloc", "trunc", "falloc"],
            state="readonly", font=FONT_SMALL, width=100, height=26,
            fg_color="#2d3748", border_color=Theme.MUTED, button_color=Theme.ACCENT,
        )
        self.file_allocation.set("falloc")
        self.file_allocation.pack(side="left")

        pr2 = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        pr2.pack(fill="x", pady=(10, 0))
        create_label(pr2, "RPC端口:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.rpc_port = create_spinbox(pr2, initial=16800, width=60)
        self.rpc_port.pack(side="left")

        ctk.CTkFrame(pr2, width=20, height=1, fg_color="transparent").pack(side="left")

        create_label(pr2, "最小分片:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.min_split_size = create_entry(pr2, width=60)
        self.min_split_size.insert(0, "1M")
        self.min_split_size.pack(side="left")

        ctk.CTkFrame(pr2, width=20, height=1, fg_color="transparent").pack(side="left")

        create_label(pr2, "速度限制:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.speed_limit = create_entry(pr2, width=60)
        self.speed_limit.insert(0, "0")
        self.speed_limit.pack(side="left")

        log_row = ctk.CTkFrame(self.advanced_container, fg_color="transparent")
        log_row.pack(fill="x", pady=(10, 0))
        self.log_enabled_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            log_row, text="记录日志", variable=self.log_enabled_var,
            text_color=Theme.TEXT, font=FONT_NORMAL,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_LIGHT,
            corner_radius=4, border_width=2,
            checkbox_width=20, checkbox_height=20,
        ).pack(side="left")
        _initial_name = os.path.basename(self.initial_log_file) if self.initial_log_file else ""
        self.log_path_var = tk.StringVar(value=_initial_name)
        create_entry(log_row, self.log_path_var).pack(
            side="left", fill="x", expand=True, padx=(10, 0))

        # ===== 底部 =====
        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=20, pady=(15, 15), side="bottom")

        self.advanced_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            bottom, text="高级选项", variable=self.advanced_var,
            text_color=Theme.TEXT, font=FONT_NORMAL,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_LIGHT,
            corner_radius=4, border_width=2,
            checkbox_width=20, checkbox_height=20,
            command=self._toggle_advanced,
        ).pack(side="left")

        create_button(bottom, text="提交", command=self._start_download,
                      width=100).pack(side="right", padx=(10, 0))
        create_button(bottom, text="取消", command=self.destroy,
                      width=100, style="secondary").pack(side="right")
        create_button(bottom, text="\u25d0 切换皮肤", command=self._cycle_theme,
                      width=120, style="secondary").pack(side="left", padx=(15, 0))
    
    # --- 核心修改区域：参数行对齐 ---
    # 定义标准列宽，实现表格化对齐
    # COL1_W: 第一列标签宽度 (针对 "最大连接数:", "RPC端口:", "文件分配:")
    # COL2_W: 第二列标签宽度 (针对 "分片数:", "最小分片:")
    # COL3_W: 第三列标签宽度 (针对 "速度限制:")
    
    def _switch_tab(self, key):
        self.current_tab = key
        if key == "link":
            self.tab_seed_frame.pack_forget()
            self.tab_link_frame.pack(fill="x")
        else:
            self.tab_link_frame.pack_forget()
            self.tab_seed_frame.pack(fill="x")
        self._set_tab_active(key)

    def _set_tab_active(self, key):
        try:
            self.tab_link_btn.configure(
                text_color=(Theme.ACCENT if key == "link" else Theme.MUTED))
            self.tab_seed_btn.configure(
                text_color=(Theme.ACCENT if key == "seed" else Theme.MUTED))
        except Exception:
            pass

    def _toggle_advanced(self):
        try:
            if self.advanced_var.get():
                self.advanced_container.pack(fill="x")
            else:
                self.advanced_container.pack_forget()
        except Exception:
            pass
        self.after(30, self._apply_dynamic_height)

    def _build_param_row1(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=0, pady=5)
        
        # 第一列: 最大连接数
        create_label(frame, "最大连接数:", width=90, anchor="e").pack(side="left", padx=(0, 5))
        self.max_conn = create_spinbox(frame, initial=16, width=60)
        self.max_conn.pack(side="left")
        
        # 间距
        ctk.CTkFrame(frame, width=20, height=1, fg_color="transparent").pack(side="left")
        
        # 第二列: 分片数
        create_label(frame, "分片数:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.split = create_spinbox(frame, initial=5, width=60)
        self.split.pack(side="left")
        
        # 间距
        ctk.CTkFrame(frame, width=20, height=1, fg_color="transparent").pack(side="left")

        # 第三列: 文件分配 (从原第三行移来)
        # 使用 width=70 与下方 "速度限制" 对齐
        create_label(frame, "文件分配:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.file_allocation = ctk.CTkComboBox(
            frame, values=["none", "prealloc", "trunc", "falloc"],
            state="readonly", font=FONT_SMALL, width=100, height=26, # <--- 高度改为26
            fg_color="#2d3748", border_color=Theme.MUTED, button_color=Theme.ACCENT,
        )
        self.file_allocation.set("falloc")
        self.file_allocation.pack(side="left") # 已经是最后，不需要padx
        
        create_label(frame, "(推荐 falloc)", color=Theme.MUTED, font_size=11).pack(side="left", padx=(5,0))

    def _build_param_row2(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=0, pady=5)
        
        # 第一列: RPC端口
        create_label(frame, "RPC端口:", width=90, anchor="e").pack(side="left", padx=(0, 5))
        self.rpc_port = create_spinbox(frame, initial=16800, width=60)
        self.rpc_port.pack(side="left")
        
        # 间距
        ctk.CTkFrame(frame, width=20, height=1, fg_color="transparent").pack(side="left")
        
        # 第二列: 最小分片
        create_label(frame, "最小分片:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.min_split_size = create_entry(frame, width=60)
        self.min_split_size.insert(0, "1M")
        self.min_split_size.pack(side="left")
        
        # 间距
        ctk.CTkFrame(frame, width=20, height=1, fg_color="transparent").pack(side="left")
        
        # 第三列: 速度限制
        create_label(frame, "速度限制:", width=70, anchor="e").pack(side="left", padx=(0, 5))
        self.speed_limit = create_entry(frame, width=60)
        self.speed_limit.insert(0, "0")
        self.speed_limit.pack(side="left", padx=(0, 5))
        
        create_label(frame, "(0=无)", color=Theme.MUTED, font_size=11).pack(side="left")
    
    def _cycle_theme(self):
        try:
            from config import THEMES, load_config, save_config
        except Exception:
            return
        names = list(THEMES.keys())
        if not names:
            return
        cur = getattr(self, "_current_theme", "midnight")
        try:
            idx = names.index(cur)
        except ValueError:
            idx = -1
        nxt = names[(idx + 1) % len(names)]
        try:
            cfg = load_config()
            cfg["theme"] = nxt
            save_config(cfg)
            self._current_theme = nxt
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showinfo("提示", f"皮肤已保存为 {nxt}，重启后生效")
        except Exception:
            pass

    def _load_history(self):
        try:
            from config import load_config
            cfg = load_config()
            sp = cfg.get("save_paths") or {}
            recent = sp.get("recent", []) if isinstance(sp, dict) else []
            starred = sp.get("starred", []) if isinstance(sp, dict) else []
            return {"recent": list(recent)[:20], "starred": list(starred)}
        except Exception:
            return {"recent": [], "starred": []}

    def _save_history(self):
        try:
            from config import load_config, save_config
            cfg = load_config()
            cfg["save_paths"] = dict(self._history)
            save_config(cfg)
        except Exception:
            pass

    def _add_to_history(self, path):
        if not path:
            return
        path = os.path.abspath(path)
        r = self._history.get("recent", [])
        if path in r:
            r.remove(path)
        r.insert(0, path)
        self._history["recent"] = r[:20]
        self._save_history()

    def _show_path_history(self):
        if self._history_popup is not None:
            try:
                self._history_popup.destroy()
            except Exception:
                pass
            self._history_popup = None
            return
        recent = self._history.get("recent", [])
        starred = self._history.get("starred", [])
        items = []
        for p in starred:
            if p not in items:
                items.append(p)
        for p in recent:
            if p not in items:
                items.append(p)
        if not items:
            return

        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg="#1f2937")

        body = ctk.CTkFrame(pop, fg_color="#1f2937", corner_radius=6)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        def _pick(p):
            self.path_var.set(p)
            self._close_history_popup()

        def _toggle_star(p):
            st = self._history.get("starred", [])
            if p in st:
                st.remove(p)
            else:
                st.insert(0, p)
            self._history["starred"] = st
            self._save_history()
            self._close_history_popup()
            self._show_path_history()

        def _remove(p):
            r = self._history.get("recent", [])
            if p in r:
                r.remove(p)
            self._history["recent"] = r
            st = self._history.get("starred", [])
            if p in st:
                st.remove(p)
            self._history["starred"] = st
            self._save_history()
            self._close_history_popup()
            self._show_path_history()

        for p in items[:10]:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            txt = p if len(p) <= 48 else "..." + p[-45:]
            btn = ctk.CTkButton(
                row, text=txt, width=400, height=28, anchor="w",
                fg_color="transparent", hover_color="#4b5563",
                text_color=Theme.TEXT, font=FONT_SMALL,
                corner_radius=4, border_width=0,
                command=lambda pp=p: _pick(pp),
            )
            btn.pack(side="left", fill="x", expand=True)
            is_star = p in starred
            star_btn = ctk.CTkButton(
                row, text=("\u2605" if is_star else "\u2606"),
                width=26, height=28, fg_color="transparent",
                hover_color="#4b5563", text_color=Theme.ACCENT if is_star else Theme.MUTED,
                font=("Segoe UI Symbol", 14), corner_radius=4, border_width=0,
                command=lambda pp=p: _toggle_star(pp),
            )
            star_btn.pack(side="left")
            del_btn = ctk.CTkButton(
                row, text="\U0001f5d1", width=26, height=28,
                fg_color="transparent", hover_color="#4b5563",
                text_color=Theme.MUTED,
                font=("Segoe UI Symbol", 12), corner_radius=4, border_width=0,
                command=lambda pp=p: _remove(pp),
            )
            del_btn.pack(side="left")

        pop.update_idletasks()
        pw = max(320, pop.winfo_reqwidth())
        ph = pop.winfo_reqheight()
        try:
            x = self._clock_btn.winfo_rootx()
            y = self._clock_btn.winfo_rooty() + self._clock_btn.winfo_height() + 4
        except Exception:
            x, y = 100, 100
        pop.geometry(f"{pw}x{ph}+{x}+{y}")
        self._history_popup = pop
        pop.bind("<FocusOut>", lambda e: self._close_history_popup())
        pop.focus_force()

    def _close_history_popup(self):
        if self._history_popup is not None:
            try:
                self._history_popup.destroy()
            except Exception:
                pass
            self._history_popup = None

    def _draw_drop_border(self, event=None):
        c = self.drop_canvas
        try:
            c.delete("all")
            w = c.winfo_width()
            h = c.winfo_height()
            if w <= 4 or h <= 4:
                return
            c.create_rectangle(6, 6, w - 6, h - 6, outline="#4b5563",
                               dash=(6, 4), width=2, tags="border")
            c.create_text(w // 2, h // 2, text="将种子拖到此处，或点击选择",
                          fill="#9ca3af", font=FONT_NORMAL, tags="label")
        except Exception:
            pass

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder:
            folder = folder.replace("/", "\\")
            self.path_var.set(folder)

    def _browse_torrent(self):
        filename = filedialog.askopenfilename(
            title="选择 BT / MetaLink 文件",
            filetypes=[
                ("BT/MetaLink 文件", "*.torrent *.meta4 *.metalink"),
                ("Torrent Files", "*.torrent"),
                ("Metalink Files", "*.meta4 *.metalink"),
                ("All Files", "*.*"),
            ],
            initialdir=self.path_var.get(),
        )
        if filename:
            current = self.url_text.get("1.0", "end").strip()
            if current:
                self.url_text.insert("end", "\n" + filename)
            else:
                self.url_text.insert("end", filename)
            try:
                _paths = self.url_text.get("1.0", "end").strip().splitlines()
                _seed = [p for p in _paths if p.lower().endswith((".torrent", ".meta4", ".metalink"))]
                self.seed_files_label.configure(text="\n".join(_seed) if _seed else "")
            except Exception:
                pass
                
    def _collect_args(self, save_path, lines):
        # 参数收集逻辑保持不变
        aria2_args = []
        aria2_args.append(f"--dir={save_path}")
        aria2_args.append(f"--max-connection-per-server={self.max_conn.get()}")
        aria2_args.append(f"--split={self.split.get()}")

        speed_limit = self.speed_limit.get().strip()
        if speed_limit and speed_limit != "0":
            aria2_args.append(f"--max-overall-download-limit={speed_limit}")
        min_split = self.min_split_size.get().strip()
        if min_split:
            aria2_args.append(f"--min-split-size={min_split}")
        file_alloc = self.file_allocation.get()
        if file_alloc:
            aria2_args.append(f"--file-allocation={file_alloc}")
        ua = self.ua_var.get().strip()
        if ua:
            aria2_args.append(f"--user-agent={ua}")
        custom_title = self.title_var.get().strip()
        if custom_title:
            aria2_args.append(f'--title={custom_title}')
        processed_urls = []
        for item in lines:
            if item.endswith(".torrent") and os.path.isfile(item):
                aria2_args.append(item)
            else:
                processed_urls.append(item)
                aria2_args.append(item)
        referer = self.referer_var.get().strip()
        # if not referer and processed_urls:
            # first_url = processed_urls[0]
            # if first_url.startswith("http"):
                # referer = extract_referer(first_url)
        
        # 仅当用户勾选“自动提取 Referer”且未手动填写时，才从第一个 URL 提取
        if self.auto_referer_var.get() and not referer and processed_urls:
            first_url = processed_urls[0]
            if first_url.startswith("http"):
                referer = extract_referer(first_url)
                
        if referer:
            aria2_args.append(f"--referer={referer}")
        auth = self.auth_var.get().strip()
        if auth:
            if not auth.lower().startswith("authorization:"):
                auth = "Authorization: " + auth
            aria2_args.append(f"--header={auth}")
        cookie = self.cookie_var.get().strip()
        if cookie:
            if not cookie.lower().startswith("cookie:"):
                cookie = "Cookie: " + cookie
            aria2_args.append(f"--header={cookie}")
        proxy = self.proxy_var.get().strip()
        if proxy:
            aria2_args.append(f"--all-proxy={proxy}")
        return aria2_args

    def _start_download(self):
        # 启动逻辑保持不变
        raw_input = self.url_text.get("1.0", "end").strip()
        if not raw_input:
            messagebox.showerror("错误", "请输入链接或选择种子文件")
            return
        
        lines = [line.strip().strip('"').strip("'") for line in raw_input.split("\n") if line.strip()]
        if not lines:
            messagebox.showerror("错误", "内容为空")
            return
        
        save_path = self.path_var.get().strip()
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建目录:\n{save_path}\n{e}")
                return
        
        aria2_args = self._collect_args(save_path, lines)
        check_urls, _ = extract_urls_and_out(aria2_args)
        if not check_urls:
            messagebox.showerror("无效输入", "无法识别有效的下载链接、磁力链或种子文件。")
            return
        self._add_to_history(save_path)
        
        if not self.is_master:
            reply = try_send_to_main_instance(aria2_args)
            ok = False
            if reply:
                try:
                    if json.loads(reply).get("status") == "success":
                        ok = True
                except Exception:
                    pass
            if ok:
                messagebox.showinfo("提示", "任务已发送至正在运行的主程序")
                self.destroy()
                import sys
                sys.exit(0)
            messagebox.showerror("错误", "已有实例未就绪，无法转发任务")
            import sys
            sys.exit(1)
        
        custom_title = self.title_var.get().strip()
        title = custom_title if custom_title else None
        
        _log_enabled = self.log_enabled_var.get() if hasattr(self, "log_enabled_var") else True
        log_file = None
        if _log_enabled:
            _lp = ""
            if hasattr(self, "log_path_var"):
                _lp = self.log_path_var.get().strip()
            if not _lp:
                _lp = self.initial_log_file or ""
            if _lp and not os.path.isabs(_lp):
                _lp = os.path.join(os.getcwd(), _lp)
            log_file = _lp or None

        if self.on_submit is not None:
            try:
                self.on_submit(aria2_args, title, log_file)
            except Exception:
                pass
            self.destroy()
            return
        
        self.launch_cfg = {
            "title": title,
            "info_text": "正在启动下载...",
            "close_delay": 30,
            "log_file": log_file,
            "aria2_args": aria2_args,
        }
        
        self.destroy()
        
    def _toggle_auto_referer(self):
        """勾选时自动填入 Referer，取消勾选时清空"""
        if self.auto_referer_var.get():
            # 自动提取
            raw = self.url_text.get("1.0", "end").strip()
            lines = [line.strip().strip('"').strip("'") for line in raw.split("\n") if line.strip()]
            for line in lines:
                if line.startswith("http"):
                    referer = extract_referer(line)
                    if referer:
                        self.referer_var.set(referer)
                        return
        else:
            # 取消勾选：清空 Referer
            self.referer_var.set("")