#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""info 浮层（任务详情弹窗）"""
import os
import tkinter as tk
import customtkinter as ctk
from config import Theme
from utils import nice_size
from ui_styles import FONT_SMALL, FONT_NORMAL


class InfoOverlay:
    """任务详情浮层。Aria2GUI 持有一个实例，负责全部 info 相关 UI 与状态。"""

    def __init__(self, gui):
        self.gui = gui
        self._info_win = None
        self._info_text = None
        self._info_sb = None
        self._info_gid = None
        self._info_show_id = None
        self._info_hide_id = None
        self._info_refresh_id = None
        self._info_menu_open = False
        self._info_fg_id = None

    def _schedule_info_show(self, gid):
        if self._info_hide_id:
            try:
                self.gui.after_cancel(self._info_hide_id)
            except Exception:
                pass
            self._info_hide_id = None
        if self._info_win and self._info_gid == gid:
            return
        if self._info_show_id:
            try:
                self.gui.after_cancel(self._info_show_id)
            except Exception:
                pass
        self._info_show_id = self.gui.after(600, self._do_show_info, gid)

    def _schedule_info_hide(self):
        if getattr(self, "_info_menu_open", False):
            return
        if self._info_show_id:
            try:
                self.gui.after_cancel(self._info_show_id)
            except Exception:
                pass
            self._info_show_id = None
        if self._info_hide_id:
            try:
                self.gui.after_cancel(self._info_hide_id)
            except Exception:
                pass
        self._info_hide_id = self.gui.after(200, self._do_hide_info)

    def _do_show_info(self, gid):
        self._info_show_id = None
        with self.gui.tasks_lock:
            task = self.gui.tasks.get(gid)
        if not task:
            return
        if self._info_win is None:
            try:
                top = tk.Toplevel(self.gui)
                top.overrideredirect(True)
                top.attributes("-topmost", True)
                _TRANSPARENT = "#010203"
                _use_trans = False
                try:
                    top.configure(bg=_TRANSPARENT)
                    top.attributes("-transparentcolor", _TRANSPARENT)
                    _use_trans = True
                except Exception:
                    top.configure(bg="#1f2937")
                box = ctk.CTkFrame(
                    top, fg_color="#1f2937",
                    border_width=1, border_color="#4b5563",
                    corner_radius=8,
                )
                box.pack(fill="both", expand=True, padx=0, pady=0)
                ctk.CTkLabel(
                    box, text="任务详情", font=(FONT_NORMAL[0], 11, "bold"),
                    text_color=Theme.MUTED, anchor="w",
                ).pack(fill="x", padx=12, pady=(8, 2))
                txt_frame = ctk.CTkFrame(box, fg_color="transparent")
                txt_frame.pack(fill="both", expand=True, padx=(12, 8), pady=(0, 8))
                txt_frame.grid_columnconfigure(0, weight=1)
                txt_frame.grid_rowconfigure(0, weight=1)
                txt = tk.Text(
                    txt_frame, font=FONT_SMALL, bg="#1f2937", fg=Theme.TEXT,
                    bd=0, highlightthickness=0, wrap="none",
                    insertbackground=Theme.TEXT,
                    selectbackground="#3b82f6", selectforeground="#ffffff",
                )
                txt.grid(row=0, column=0, sticky="nsew")
                sb = ctk.CTkScrollbar(txt_frame, command=txt.yview, width=10)
                txt.configure(yscrollcommand=sb.set)
                sb.grid(row=0, column=1, sticky="ns", padx=(2, 0))
                _NAV = {"Left", "Right", "Up", "Down", "Home", "End",
                        "Prior", "Next", "Shift_L", "Shift_R", "Control_L", "Control_R"}
                def _on_key(ev):
                    if ev.keysym in _NAV:
                        return None
                    if ev.state & 0x4:
                        return None
                    if (ev.state & 0x1) and ev.keysym in ("Left", "Right", "Up", "Down", "Home", "End"):
                        return None
                    return "break"
                txt.bind("<KeyPress>", _on_key)
                _menu = tk.Menu(top, tearoff=0)
                def _select_all():
                    try:
                        txt.tag_add("sel", "1.0", "end-1c")
                    except Exception:
                        pass
                def _copy_sel():
                    try:
                        txt.event_generate("<<Copy>>")
                    except Exception:
                        pass
                _menu.add_command(label="全选", command=_select_all)
                _menu.add_command(label="复制", command=_copy_sel)
                def _show_menu(ev):
                    try:
                        txt.focus_set()
                        self._cancel_info_hide()
                        self._info_menu_open = True
                        try:
                            _menu.tk_popup(ev.x_root, ev.y_root)
                        finally:
                            try:
                                _menu.grab_release()
                            except Exception:
                                pass
                    finally:
                        self._info_menu_open = False
                        try:
                            self._schedule_info_hide()
                        except Exception:
                            pass
                txt.bind("<Button-3>", _show_menu, add="+")
                top.bind("<Enter>", lambda e: self._cancel_info_hide())
                top.bind("<Leave>", lambda e: self._schedule_info_hide())
                self._info_win = top
                self._info_text = txt
                self._info_sb = sb
            except Exception:
                self._info_win = None
                return
        self._info_gid = gid
        try:
            self._info_win.deiconify()
            self._info_win.lift()
        except Exception:
            pass
        self._refresh_info_text()
        if self._info_fg_id:
            try:
                self.gui.after_cancel(self._info_fg_id)
            except Exception:
                pass
        self._info_fg_id = self.gui.after(300, self._poll_fg_window)

    def _cancel_info_hide(self):
        if self._info_hide_id:
            try:
                self.gui.after_cancel(self._info_hide_id)
            except Exception:
                pass
            self._info_hide_id = None

    def _refresh_info_text(self):
        gid = self._info_gid
        if not gid or not self._info_text:
            return
        with self.gui.tasks_lock:
            task = self.gui.tasks.get(gid)
        if not task:
            self._do_hide_info()
            return
        text = self._build_info_text(task)
        want_w = 420
        want_h = 120
        try:
            tb = self._info_text
            tb.delete("1.0", "end")
            tb.insert("1.0", text)
            n_lines = max(1, text.count("\n") + 1)
            _content_h = n_lines * 18 + 24
            want_h = min(420, max(80, _content_h)) + 34
            try:
                import tkinter.font as _tkfont
                _f = _tkfont.Font(font=FONT_SMALL)
                _px_w = max((_f.measure(_line) for _line in text.split("\n")), default=0)
            except Exception:
                _px_w = max((len(_line) for _line in text.split("\n")), default=0) * 10
            want_w = max(420, min(1100, _px_w + 80))
            if self._info_sb is not None:
                if _content_h > (want_h - 34):
                    self._info_sb.grid()
                else:
                    self._info_sb.grid_remove()
        except Exception:
            pass
        _ui = task.get("ui", {})
        _frame = _ui.get("frame")
        _btn_info = _ui.get("btn_info")
        if _frame is None:
            self._info_win.geometry(f"{want_w}x{want_h}")
            return
        try:
            fx = _frame.winfo_rootx()
            fw = _frame.winfo_width()
            px = fx + (fw - want_w) // 2
            py = None
            _TIP_GAP = 6
            if _btn_info is not None:
                try:
                    bx = _btn_info.winfo_rootx()
                    by = _btn_info.winfo_rooty()
                    bw = _btn_info.winfo_width()
                    bh = _btn_info.winfo_height()
                    px = bx + bw - want_w
                    py = by + bh + _TIP_GAP
                except Exception:
                    py = None
            if py is None:
                fy = _frame.winfo_rooty()
                fh = _frame.winfo_height()
                py = fy + fh + 10
            try:
                sw = self.gui.winfo_screenwidth()
                sh = self.gui.winfo_screenheight()
                if px + want_w > sw:
                    px = sw - want_w - 4
                if px < 0:
                    px = 0
                if py + want_h > sh:
                    py = sh - want_h - 4
            except Exception:
                pass
            self._info_win.geometry(f"{want_w}x{want_h}+{px}+{py}")
        except Exception:
            self._info_win.geometry(f"{want_w}x{want_h}")

    def _build_info_text(self, task):
        files = task.get("last_files") or []
        base_dir = task.get("last_dir", "") or ""
        if not files:
            group_gids = task.get("group_gids") or []
            gid = group_gids[0] if group_gids else None
            if gid is None:
                return "无任务信息"
            try:
                res = self.gui.rpc.tell_status(gid, ["files", "dir"])
            except Exception:
                res = None
            if not res or "result" not in res:
                return "获取中..."
            result = res["result"]
            files = result.get("files", [])
            base_dir = result.get("dir", "") or base_dir
            if not files:
                return "获取中..."
        root_files = []
        dir_groups = {}
        for f in files:
            p = f.get("path", "")
            if base_dir and p.startswith(base_dir):
                try:
                    rel = os.path.relpath(p, base_dir)
                except Exception:
                    rel = os.path.basename(p)
            else:
                rel = os.path.basename(p)
            parts = rel.replace("/", os.sep).split(os.sep)
            length = int(f.get("length", 0))
            done = int(f.get("completedLength", 0))
            if len(parts) > 1:
                d = parts[0]
                if d not in dir_groups:
                    dir_groups[d] = {"total": 0, "done": 0, "files": []}
                dir_groups[d]["total"] += length
                dir_groups[d]["done"] += done
                dir_groups[d]["files"].append((os.path.join(*parts[1:]), length, done))
            else:
                root_files.append((parts[0] if parts else rel, length, done))
        lines = []
        for d in sorted(dir_groups.keys()):
            g = dir_groups[d]
            total = g["total"]
            done = g["done"]
            pct = (done / total * 100) if total > 0 else 0
            lines.append(f"{d + '/':<48} {nice_size(done):>10} / {nice_size(total):<10}  {pct:>5.1f}%")
            for name, t, dn in g["files"]:
                p2 = (dn / t * 100) if t > 0 else 0
                lines.append(f"  {name[:44]:<44} {nice_size(dn):>10} / {nice_size(t):<10}  {p2:>5.1f}%")
        for name, t, dn in root_files:
            p2 = (dn / t * 100) if t > 0 else 0
            lines.append(f"{name[:48]:<48} {nice_size(dn):>10} / {nice_size(t):<10}  {p2:>5.1f}%")
        return "\n".join(lines) if lines else "无任务信息"

    def _poll_fg_window(self):
        self._info_fg_id = None
        if self._info_win is None:
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != os.getpid():
                self._do_hide_info(force=True)
                return
        except Exception:
            pass
        self._info_fg_id = self.gui.after(300, self._poll_fg_window)

    def _do_hide_info(self, force=False):
        self._info_hide_id = None
        if self._info_fg_id:
            try:
                self.gui.after_cancel(self._info_fg_id)
            except Exception:
                pass
            self._info_fg_id = None
        if not force and getattr(self, "_info_menu_open", False):
            return
        if not force and self._info_win is not None:
            try:
                px, py = self.gui.winfo_pointerxy()
                wx = self._info_win.winfo_rootx()
                wy = self._info_win.winfo_rooty()
                ww = self._info_win.winfo_width()
                wh = self._info_win.winfo_height()
                if wx <= px <= wx + ww and wy <= py <= wy + wh:
                    return
            except Exception:
                pass

        if self._info_refresh_id:
            try:
                self.gui.after_cancel(self._info_refresh_id)
            except Exception:
                pass
            self._info_refresh_id = None
        if self._info_win is not None:
            try:
                self._info_win.destroy()
            except Exception:
                pass
        self._info_win = None
        self._info_text = None
        self._info_gid = None

    def schedule_show(self, gid):
        self._schedule_info_show(gid)

    def schedule_hide(self):
        self._schedule_info_hide()

    def is_showing(self, gid):
        return self._info_gid == gid

    def hide(self, force=False):
        self._do_hide_info(force=force)
