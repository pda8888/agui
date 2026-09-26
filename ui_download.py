#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aria2下载任务监控界面 (动态高度修正版)"""
import os, json
import time
import base64
import threading
# import tkinter as tk
import tkinter as tk
from tkinter import messagebox
from urllib.parse import urlparse, unquote
import customtkinter as ctk

from config import APP_TITLE, Theme
from utils import nice_size, nice_duration, extract_urls_and_out, get_long_path_win32, translate_error_online, parse_metalink_hashes, parse_metalink_hashes_from_b64, HashVerifier
from rpc_client import Aria2RPC
from process_manager import start_aria2c, stop_aria2c
from ipc_server import IPCServer
from arg_parser import get_task_options, parse_custom_t_arg
from ui_styles import create_button, FONT_NORMAL, FONT_SMALL, get_work_area_and_scaling
from info_overlay import InfoOverlay

class Aria2GUI(ctk.CTkToplevel):
    """Aria2下载任务管理界面"""
    def __init__(self, parent, config, server_socket=None):
        super().__init__(parent)
        self.withdraw()
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        try:
            from config import get_asset_path
            _icon = get_asset_path("boat.ico")
            if os.path.exists(_icon):
                self.iconbitmap(_icon)
        except Exception:
            pass
        
        self.config = config
        self.server_socket = server_socket
        self.log_file = config.get("log_file")
        self.base_title = APP_TITLE
        self.global_countdown = config.get("global_countdown")
        self.retry_count = config.get("retry_count", 3)
        self.retry_interval = config.get("retry_interval", 2)
        self.position_offset = config.get("position")
        self.is_position_set = False
        self.retry_exhausted_timeout = config.get("retry_exhausted_timeout", 10)
        self.configure(fg_color=Theme.BG)
        # 允许调整大小
        self.resizable(True, True)
        
        self.tasks = {}
        self.tasks_lock = threading.RLock()
        self.selected_gids = set()
        self._drag_start = None
        self._drag_active = False
        self._drag_rect_win = None
        self._drag_source_gid = None
        self._drag_ctrl = False
        self._active_tooltip = None
        self.info = InfoOverlay(self)
        self.is_running = True
        self.shutdown_start_time = None
        self._refresh_after_id = None
        self.app_start_time = time.time()
        try:
            from config import load_config as _lc
            self._current_theme = _lc().get("theme") or "midnight"
        except Exception:
            self._current_theme = "midnight"
        self._tick_started = False
        self._theme_menu_win = None
        self._theme_fg_id = None
        
        secret = next(
            (a.split("=", 1)[1] for a in config["aria2_args"] if a.startswith("--rpc-secret=")),
            None
        )
        self.rpc = Aria2RPC(secret)
        self.aria2_proc = None
        
        self._build_ui()
        
        if server_socket:
            self.ipc_server = IPCServer(server_socket, self._ipc_handler, self.log_file)
            threading.Thread(target=self.ipc_server.start, daemon=True).start()
        
        threading.Thread(
            target=self._start_aria2_and_first_task,
            args=(config["aria2_args"],),
            daemon=True
        ).start()
        
        # 如果指定了 --http-port，启动 HTTP 服务（守护线程）
        self.http_port = config.get("http_port")
        if self.http_port:
            threading.Thread(target=self._run_http_server, daemon=True).start()
    
    def _build_ui(self):
        """构建界面"""
        self.title(self.base_title)
        
        # 顶部栏：左侧两行（状态 + 统计），右侧图标组（垂直居中）
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=12, pady=10)

        right_box = ctk.CTkFrame(self.header, fg_color="transparent")
        right_box.pack(side="right")

        _left_stack = ctk.CTkFrame(self.header, fg_color="transparent")
        _left_stack.pack(side="left", fill="x", expand=True)

        _ICON_HOVER = "#4b5563"
        top_icons = ctk.CTkFrame(right_box, fg_color="transparent", corner_radius=6)
        top_icons.pack(side="right")

        def _make_top_icon(text, cmd):
            return ctk.CTkButton(
                top_icons, text=text, command=cmd, width=36, height=30,
                fg_color="transparent", hover_color=_ICON_HOVER,
                text_color=Theme.TEXT, font=(FONT_NORMAL[0], 16, "bold"),
                corner_radius=4, border_width=0,
            )

        self.btn_top_theme = _make_top_icon("🌗", self._show_theme_menu)
        self.btn_top_play = _make_top_icon("▶", self._resume_all)
        self.btn_top_pause = _make_top_icon("‖", self._pause_all)
        self.btn_top_clear = _make_top_icon("✕", self._clear_all)
        self.btn_top_retry = _make_top_icon("↻", self._retry_all)
        self.btn_top_add = _make_top_icon("⊕", self._open_config_gui)
        self.btn_top_add.configure(width=42, height=36, font=(FONT_NORMAL[0], 22))
        if self.config.get("no_add"):
            self.btn_top_add.configure(state="disabled", text_color=Theme.MUTED)
        self.btn_top_theme.pack(side="right")
        self.btn_top_retry.pack(side="right")
        self.btn_top_clear.pack(side="right")
        self.btn_top_pause.pack(side="right")
        self.btn_top_play.pack(side="right")
        self.btn_top_add.pack(side="right")

        self._bind_tooltip(self.btn_top_add, "添加任务")
        self._bind_tooltip(self.btn_top_play, "继续选中")
        self._bind_tooltip(self.btn_top_pause, "暂停选中")
        self._bind_tooltip(self.btn_top_clear, "清除已完成")
        self._bind_tooltip(self.btn_top_retry, "重试失败")
        self._bind_tooltip(self.btn_top_theme, "切换皮肤")

        _header_line2 = ctk.CTkFrame(_left_stack, fg_color="transparent")
        _header_line2.pack(fill="x")

        self.lbl_global_stats = ctk.CTkLabel(
            _header_line2, text="", font=FONT_SMALL,
            text_color=Theme.SEMI_MUTED, height=16
        )
        self.lbl_global_stats.pack(side="left")
        
        # 任务容器
        self.task_container = ctk.CTkFrame(self, fg_color="transparent")
        # self.task_container.pack(fill="both", expand=True, padx=5)
        self.task_container.pack(fill="x", expand=False, anchor="n", padx=5)
        
        # 底部控制区 (仅占位，如果有需要可以放全局按钮)
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        # self.footer.pack(fill="x", padx=12, pady=5)
        
        self.protocol("WM_DELETE_WINDOW", self._try_close_window)
        self._update_layout()
        # 仅当配置要求显示 GUI 时才取消隐藏
        if self.config.get("show_gui", True):
            self.deiconify()
            try:
                self.update_idletasks()
            except Exception:
                pass
            self._reapply_position()
            try:
                self.attributes("-alpha", 1.0)
            except Exception:
                pass
        if not getattr(self, "_tick_started", False):
            self._tick_started = True
            self.after(500, self._ui_refresh_loop)
            self.after(100, self._marquee_tick)
            self.bind_all("<B1-Motion>", self._on_mouse_motion, add="+")
            self.bind_all("<ButtonRelease-1>", self._on_mouse_release, add="+")
        self.bind("<FocusOut>", self._on_focus_out_cancel_drag, add="+")

    def _reapply_position(self):
        g = getattr(self, "_last_geo", None)
        if not g:
            return
        try:
            self.geometry(g)
            self.update_idletasks()
        except Exception:
            pass

    def _update_layout(self):
        """动态更新窗口高度（按卡片实测高度累加）"""
        with self.tasks_lock:
            tasks_snapshot = list(self.tasks.values())

        # 先强制刷新布局，确保 winfo_reqheight 拿到真值
        try:
            self.update_idletasks()
        except Exception:
            pass

        # 获取 DPI 缩放，用于物理像素 → 逻辑像素换算
        sc = 1.0
        try:
            import customtkinter as _ctk
            _s = _ctk.ScalingTracker.get_window_scaling(self)
            if _s and _s > 0:
                sc = _s
        except Exception:
            sc = 1.0

        # 基础高度：Header 实测 + 边距
        try:
            self.header.update_idletasks()
            total_h = self.header.winfo_reqheight()
        except Exception:
            total_h = 60
        total_h = int(total_h / sc) if sc > 0 else total_h
        # 卡间距 5（上下各 2+3），末卡底边距 N=15
        total_h += 30
        CARD_GAP = 5

        for task in tasks_snapshot:
            ui = task.get("ui", {})
            frame = ui.get("frame")
            card_h = None
            if frame is not None:
                try:
                    if frame.winfo_exists():
                        frame.update_idletasks()
                        card_h = frame.winfo_reqheight() / sc
                except Exception:
                    card_h = None
            if card_h is None:
                card_h = 130 if task.get("task_title") else 100
            if task.get("error_visible"):
                lbl = ui.get("lbl_error")
                if lbl is not None:
                    try:
                        if lbl.winfo_exists():
                            text = lbl.cget("text") or ""
                            nlines = text.count("\n") + 1
                            card_h += nlines * 20 + 4
                    except Exception:
                        pass
            total_h += card_h + CARD_GAP

        target_h = max(160, total_h)
        target_h = min(1200, target_h)
        target_w = 640

        if not self.is_position_set:
            wx0, wy0, ww, wh, _sc2 = get_work_area_and_scaling(self)
            phys_w = int(target_w * _sc2)
            phys_h = int(target_h * _sc2)
            x = wx0 + (ww - phys_w) // 2
            y = wy0 + (wh - phys_h) // 2
            if self.position_offset:
                x += self.position_offset[0]
                y += self.position_offset[1]
            _geo = f"{target_w}x{target_h}+{x}+{y}"
            self.geometry(_geo)
            self._last_geo = _geo
            self.is_position_set = True
        else:
            _geo = f"{target_w}x{target_h}"
            self.geometry(_geo)
            self._last_geo = _geo

    def _ipc_handler(self, args):
        """IPC消息处理（在监听线程中同步调用），返回要发送给客户端的字节或 None"""
        # 如果是显示界面命令，异步处理，不返回数据
        if args == ['__SHOW_UI__']:
            self.after(0, self._bring_to_front)
            return None
        
        # 杀死任务命令：args 为 ['KILL', gid] 格式
        if len(args) == 2 and args[0] == 'KILL':
            gid = args[1]
            try:
                # 从 aria2 强制移除任务
                self.rpc.force_remove(gid)
                self.rpc.remove_download_result(gid)
                # 销毁对应的 UI 卡片（如果存在）
                with self.tasks_lock:
                    _local_exists = gid in self.tasks
                if _local_exists:
                    def _kill_cleanup():
                        # 主线程中执行 UI 清理，避免跨线程冲突
                        if gid not in self.tasks:
                            return
                        task = self.tasks[gid]
                        if task.get("retry_dialog"):
                            try:
                                task["retry_dialog"].destroy()
                            except Exception:
                                pass
                        task["ui"]["frame"].destroy()
                        del self.tasks[gid]
                        self._update_layout()
                        if len(self.tasks) == 0:
                            self._on_close()
                    self.after(0, _kill_cleanup)
                import json
                return json.dumps({"status": "success", "message": "task killed"}).encode("utf-8") + b"\n"
            except Exception as e:
                return json.dumps({"status": "failed", "message": str(e)}).encode("utf-8") + b"\n"
                
        # 查询命令：args 为 ['QUERY', gid] 格式
        if len(args) == 2 and args[0] == 'QUERY':
            gid = args[1]
            try:
                res = self.rpc.tell_status(gid, [
                    "status", "totalLength", "completedLength",
                    "downloadSpeed", "errorMessage", "files"
                ])
            except Exception:
                res = None
            import json
            if res and "result" in res:
                result = res["result"]
                # 补充下载就绪检查（同 _handle_query）
                complete = (
                    result.get("status") == "complete" and
                    int(result.get("totalLength", 0)) > 0 and
                    int(result.get("completedLength", 0)) == int(result.get("totalLength", 0))
                )
                if complete:
                    try:
                        file_path = ""
                        if "files" in result and result["files"]:
                            file_path = result["files"][0].get("path", "")
                        if file_path and os.path.exists(file_path + ".aria2"):
                            complete = False
                    except:
                        pass
                result["downloadReady"] = complete
                return json.dumps({"status": "success", "data": result}, ensure_ascii=False).encode("utf-8") + b"\n"
            else:
                with self.tasks_lock:
                    task = self.tasks.get(gid)
                if not task:
                    return b'{"status": "failed", "message": "task initializing or not found, retry later"}\n'
                fb = {
                    "status": task.get("status", "unknown"),
                    "totalLength": str(task.get("frozen_total", 0)) or "0",
                    "completedLength": str(task.get("frozen_done", 0)) or "0",
                    "downloadSpeed": "0",
                    "errorMessage": "",
                    "downloadReady": (task.get("status") == "complete")
                }
                return json.dumps({"status": "success", "data": fb}, ensure_ascii=False).encode("utf-8") + b"\n"
        
        # 默认当作任务参数处理：同步添加任务，立即返回 GID（不等待验证）
        try:
            gid = self._add_task_sync(args)
            if gid:
                import json
                return json.dumps({"status": "success", "GID": gid}).encode("utf-8") + b"\n"
            else:
                return b'{"status": "failed", "message": "failed to add task"}\n'
        except Exception as e:
            return f'{{"status": "failed", "message": "{str(e)}"}}\n'.encode("utf-8")

    def _bring_to_front(self):
        self.deiconify()
        self.state('normal')
        self.update() 
        self.lift()
        self.focus_force()
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))

    def _run_http_server(self):
        """启动 HTTP API 服务（委托给 http_server 模块）"""
        from http_server import run_http_server
        run_http_server(self, self.http_port, self.log_file)

    def _on_fetch_progress(self, stage, done, total):
        """aria2c 按需下载时的进度回调：写日志 + 状态栏提示"""
        from utils import log_write
        log_write(self.log_file, f"aria2c fetch: {stage} {done}/{total}")
        if stage == "downloading":
            try:
                self.after(0, self._show_fetch_status)
            except Exception:
                pass

    def _show_fetch_status(self):
        try:
            if self.winfo_exists():
                self.title(f"{self.base_title} -- 正在下载 aria2c.exe...")
        except Exception:
            pass

    def _start_aria2_and_first_task(self, args):
        try:
            from config import resolve_aria2_path
            from aria2_fetcher import fetch_aria2c
            from utils import log_write
            _cli = self.config.get("aria2c_path")
            _errs = []
            _ap = resolve_aria2_path(
                cli_path=_cli,
                on_progress=self._on_fetch_progress,
                on_need_manual=None,
                log_path=self.log_file,
                err_out=_errs,
            )
            if not _ap:
                _det = chr(10).join(_errs) if _errs else "无详细信息"
                _msg = "无法获取 aria2c.exe，请用 -a 指定路径或检查网络。" + chr(10) + chr(10) + "详细：" + chr(10) + _det
                self.after(0, self._on_error, _msg)
                return
            self.aria2_proc, ready, stderr = start_aria2c(args, _ap, self.log_file)
            if not ready:
                err = stderr.decode("utf-8", errors="ignore").strip() if stderr else "未知错误"
                log_write(self.log_file, f"first start failed: {err}; retrying after force refetch")
                from aria2_fetcher import default_target_dir
                _dir = default_target_dir()
                _ap2 = fetch_aria2c(target_dir=_dir, force=True)
                if _ap2:
                    self.aria2_proc, ready, stderr = start_aria2c(args, _ap2, self.log_file)
            if not ready:
                err = stderr.decode("utf-8", errors="ignore").strip() if stderr else "未知错误"
                self.after(0, self._on_error, f"Aria2c进程无法启动。\n\n{err}")
                return
            t = self.config.get("title")
            info = self.config.get("info_text")
            title = f"{t}: {info}" if info and (t and t != "下载") else (t if t != "下载" else None)
            self.after(0, self._add_task_from_args, args, title)
        except Exception as e:
            self.after(0, self._on_error, f"启动错误:\n{e}")

    def _wait_for_total_length(self, gid, timeout=10):
        """轮询直到获取到 totalLength 或任务出错/超时，返回 (success, totalLength, error_msg)"""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self.rpc.tell_status(gid, ["status", "totalLength", "errorMessage"])
            if res and "result" in res:
                st = res["result"].get("status", "")
                total = int(res["result"].get("totalLength", 0))
                err = res["result"].get("errorMessage", "")
                # 成功获取到长度（>0）或任务已完成/出错
                if total > 0 or st in ("complete", "removed"):
                    return True, total, err
                if st == "error":
                    return False, 0, err
            time.sleep(0.5)
        # 超时：返回最后一次已知状态
        return False, 0, "timeout waiting for totalLength"

    def _prepare_task(self, args_list, explicit_title=None):
        """统一解析任务参数，返回 dict 或 None"""
        urls, out_name = extract_urls_and_out(args_list)
        b64_metalinks = self._extract_metalink_b64(args_list)
        if not urls and not b64_metalinks:
            return None
        task_no_cancel = "--no-cancel" in args_list
        opts = get_task_options(args_list)
        task_countdown, _global_cd = self._parse_countdown_args(args_list)
        if task_countdown is None:
            task_countdown = self.config.get("countdown")
        task_title = explicit_title
        if not task_title:
            for i, arg in enumerate(args_list):
                if (arg == "--title" or arg.startswith("--title=")) and i + 1 < len(args_list):
                    t, info = parse_custom_t_arg(args_list[i + 1] if arg == "--title" else arg.split("=", 1)[1])
                    task_title = f"{t}: {info}" if info else t
                    break
        save_dir = opts.get("dir", os.getcwd())
        try:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)
            opts["dir"] = get_long_path_win32(save_dir)
        except Exception:
            opts["dir"] = save_dir
        if "file-allocation" not in opts:
            opts["file-allocation"] = "none"
        torrents, metalinks, magnets, http_mirrors = [], [], [], []
        for u in urls:
            low = u.lower()
            if low.endswith(".torrent") and os.path.isfile(u):
                torrents.append(u)
            elif (low.endswith(".meta4") or low.endswith(".metalink")) and os.path.isfile(u):
                metalinks.append(u)
            elif low.startswith("magnet:"):
                magnets.append(u)
            else:
                http_mirrors.append(u)
        return {
            "urls": urls,
            "b64_metalinks": b64_metalinks,
            "torrents": torrents,
            "metalinks": metalinks,
            "magnets": magnets,
            "http_mirrors": http_mirrors,
            "opts": opts,
            "task_no_cancel": task_no_cancel,
            "task_title": task_title,
            "task_countdown": task_countdown,
            "_global_cd": _global_cd,
        }

    def _rpc_add_torrent(self, t_path, opts):
        """添加 torrent，返回 gid 或 None"""
        try:
            with open(t_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")
            res = self.rpc.add_torrent(content, [], opts)
            if res and "result" in res:
                return res["result"]
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"add_torrent failed: {t_path}: {e}")
        return None

    def _rpc_add_metalink_file(self, m_path, opts):
        """添加 metalink 文件，返回 dict 或 None"""
        try:
            with open(m_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")
            res = self.rpc.add_metalink(content, opts)
            if res and "result" in res:
                mh_map = parse_metalink_hashes(m_path)
                file_names = list(mh_map.keys())
                gids = res["result"]
                if isinstance(gids, str):
                    gids = [gids]
                return {"gids": gids, "mh_map": mh_map, "file_names": file_names}
            if res and "error" in res:
                msg = res["error"].get("message", "未知错误")
                self.after(0, self._show_metalink_error, m_path, msg)
        except Exception as e:
            self.after(0, self._show_metalink_error, m_path, str(e))
        return None

    def _show_metalink_error(self, m_path, msg):
        try:
            messagebox.showerror("Metalink 错误", f"{os.path.basename(m_path)}\n{msg}")
        except Exception:
            pass

    def _rpc_add_magnet(self, m, opts):
        """添加 magnet，返回 gid 或 None"""
        try:
            res = self.rpc.add_uri([m], opts)
            if res and "result" in res:
                return res["result"]
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"add_magnet failed: {e}")
        return None

    def _rpc_add_http_mirrors(self, http_mirrors, opts):
        """添加 HTTP 多源，返回 gid 或 None"""
        try:
            res = self.rpc.add_uri(http_mirrors, opts)
            if res and "result" in res:
                return res["result"]
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"add_http_mirrors failed: {e}")
        return None

    def _add_task_sync(self, args_list, explicit_title=None):
        """统一添加任务入口：全量添加 + 类型累加。返回首个成功 gid 或 None。
        非主线程可调用，UI 注册通过 after(0, ...) 调度。"""
        p = self._prepare_task(args_list, explicit_title)
        if p is None:
            return None
        if p["_global_cd"] is not None:
            self.after(0, self._apply_global_countdown, p["_global_cd"])
        opts = p["opts"]
        no_cancel = p["task_no_cancel"]
        title = p["task_title"]
        cd = p["task_countdown"]
        first_gid = None

        for b64 in p["b64_metalinks"]:
            g = self._register_metalink_task(b64, "Metalink 任务", no_cancel, title, cd, opts)
            if g and first_gid is None:
                first_gid = g

        for t_path in p["torrents"]:
            gid = self._rpc_add_torrent(t_path, opts)
            if gid:
                if first_gid is None:
                    first_gid = gid
                n = os.path.basename(t_path)
                self.after(0, lambda g=gid, nm=n, nc=no_cancel, tt=title, c=cd:
                           self._register_task(g, nm, nc, task_title=tt, countdown=c))

        for m_path in p["metalinks"]:
            r = self._rpc_add_metalink_file(m_path, opts)
            if r is None:
                continue
            gids = r["gids"]
            mh_map = r["mh_map"]
            file_names = r["file_names"]
            if title:
                initial_name = title
            elif file_names:
                initial_name = file_names[0]
            else:
                initial_name = os.path.basename(m_path)
            if first_gid is None:
                first_gid = gids[0]
            def _reg(gs=gids, n=initial_name, mm=mh_map, nc=no_cancel, tt=title, fn=file_names, c=cd):
                self._register_task(gs[0], n, nc,
                                    task_title=tt, meta_hash_map=mm,
                                    group_gids=gs, group_files=fn,
                                    placeholder_name=(not fn),
                                    countdown=c)
            self.after(0, _reg)

        for m in p["magnets"]:
            gid = self._rpc_add_magnet(m, opts)
            if gid:
                if first_gid is None:
                    first_gid = gid
                self.after(0, lambda g=gid, mm=m, oo=opts, nc=no_cancel, tt=title, c=cd:
                           self._register_task(g, "Magnet 任务", nc, [mm], oo, 0, tt,
                                               placeholder_name=True, countdown=c))

        if p["http_mirrors"]:
            gid = self._rpc_add_http_mirrors(p["http_mirrors"], opts)
            if gid:
                if first_gid is None:
                    first_gid = gid
                if opts.get("out"):
                    nm = opts["out"]
                    _ph = False
                else:
                    nm = "下载任务"
                    _ph = True
                hm = p["http_mirrors"]
                self.after(0, lambda g=gid, n=nm, hm2=hm, oo=opts, nc=no_cancel, tt=title, c=cd, ph=_ph:
                           self._register_task(g, n, nc, hm2, oo, 0, tt,
                                               placeholder_name=ph, countdown=c))

        return first_gid

    def _add_task_from_args(self, args_list, explicit_title=None):
        """薄壳：主实例首次启动调用，忽略返回值。"""
        self._add_task_sync(args_list, explicit_title)

    def _register_task(self, gid, name, no_cancel=False, raw_uris=None, raw_opts=None, retry_count=0, task_title=None, meta_hash=None, meta_hash_map=None, placeholder_name=False, group_gids=None, group_files=None, countdown=None):
        with self.tasks_lock:
            self.tasks[gid] = {
                "name": name, "status": "active", "completed": False, "no_cancel": no_cancel,
                "start_time": time.time(), "raw_uris": raw_uris, "raw_opts": raw_opts,
                "retry_count": retry_count, "task_title": task_title,
                "error_retries": 0,
                "ui": self._create_task_row(gid, name, no_cancel, task_title),
                "error_visible": False,
                "meta_hash": meta_hash,
                "meta_hash_map": meta_hash_map,
                "placeholder_name": placeholder_name,
                "group_gids": group_gids or [gid],
                "group_files": group_files or [],
                "marquee_index": 0,
                "marquee_last_switch": time.time(),
                "scroll_offset": 0,
                "verify_state": None,
                "verify_expected": None,
                "verify_actual": None,
                "countdown": countdown if countdown is not None else (self.global_countdown if self.global_countdown is not None else -1),
                "countdown_pinned": countdown is not None,
                "countdown_start": None,
            }
        self._update_layout()
        try:
            from utils import log_write
            _hdr_n = 0
            _proxy = ""
            if raw_opts:
                _h = raw_opts.get("header")
                if isinstance(_h, list):
                    _hdr_n = len(_h)
                elif _h:
                    _hdr_n = 1
                _proxy = raw_opts.get("all-proxy", "")
            log_write(self.log_file, f"task added: gid={gid} name={name} headers={_hdr_n} proxy={_proxy}")
        except Exception:
            pass
        callback_port = self.config.get("callback_port")
        if callback_port:
            import json
            from main import send_result_via_callback
            result_json = json.dumps({"status": "success", "GID": gid})
            send_result_via_callback(callback_port, result_json)
            # 仅发送一次，清除配置防止重复
            self.config["callback_port"] = None
            
    def _create_task_row(self, gid, name, no_cancel, task_title):
        frame = ctk.CTkFrame(self.task_container, fg_color=Theme.CARD, corner_radius=8,
                             border_width=1, border_color=Theme.CARD)
        frame.pack(fill="x", pady=(2, 3))
        _is_cyber = (getattr(Theme, "STYLE", "flat") == "cyber")
        if _is_cyber:
            stripe = ctk.CTkFrame(frame, fg_color=Theme.ACCENT, width=4,
                                   height=1, corner_radius=0)
            stripe.pack(side="left", fill="y")
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=(18, 14), pady=10)
        else:
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=14, pady=10)
        
        _title_lbl = None
        if task_title:
            line0 = ctk.CTkFrame(inner, fg_color="transparent")
            line0.pack(fill="x", pady=(0, 2))
            _title_lbl = ctk.CTkLabel(line0, text=task_title, text_color="#ffd700",
                                      font=(FONT_NORMAL[0], 11, "bold"))
            _title_lbl.pack(side="left")
        
        line1 = ctk.CTkFrame(inner, fg_color="transparent")
        line1.pack(fill="x")
        _ICON_HOVER = "#4b5563"
        icons_frame = ctk.CTkFrame(line1, fg_color="transparent", corner_radius=0, border_width=0)
        icons_frame.pack(side="right")
        lbl_name = ctk.CTkLabel(line1, text=name, text_color=Theme.TEXT,
                                font=(FONT_NORMAL[0], 12, "bold"), anchor="w")
        lbl_name.pack(side="left", fill="x", expand=True)
        
        def _make_icon(text, cmd):
            return ctk.CTkButton(
                icons_frame, text=text, command=cmd, width=36, height=30,
                fg_color="transparent", hover_color=_ICON_HOVER,
                text_color=Theme.TEXT, font=(FONT_NORMAL[0], 16, "bold"),
                corner_radius=4, border_width=0,
            )
        
        btn_pause = _make_icon("‖", lambda: self._toggle_pause(gid))
        btn_pause.pack(side="left")
        btn_cancel = _make_icon("✕", lambda: self._remove_task(gid))
        if no_cancel:
            btn_cancel.configure(state="disabled")
        btn_cancel.pack(side="left")
        btn_open = _make_icon("▤", lambda: self._open_folder(gid))
        btn_open.pack(side="left")
        btn_info = _make_icon("ⓘ", None)
        btn_info.pack(side="left")
        self._bind_tooltip(btn_pause, "暂停 / 继续")
        self._bind_tooltip(btn_cancel, "删除任务")
        self._bind_tooltip(btn_open, "打开文件夹")
        
        # 图标组 hover 退化为按钮自带 hover（CTkFrame 圆角在含按钮时失效）
        btn_info.bind("<Enter>", lambda e, g=gid: self.info.schedule_show(g), add="+")
        btn_info.bind("<Leave>", lambda e, g=gid: self.info.schedule_hide(), add="+")
        
        if _is_cyber:
            _glow = ctk.CTkFrame(inner, fg_color="#0a1e2e", corner_radius=5)
            _glow.pack(fill="x", pady=(6, 4))
            bar = ctk.CTkProgressBar(_glow, height=6, corner_radius=3,
                                      progress_color=Theme.ACCENT)
            bar.set(0)
            bar.pack(fill="x", padx=2, pady=2)
        else:
            bar = ctk.CTkProgressBar(inner, height=6, corner_radius=3,
                                      progress_color=Theme.ACCENT)
            bar.set(0)
            bar.pack(fill="x", pady=(8, 6))
        
        line3 = ctk.CTkFrame(inner, fg_color="transparent")
        line3.pack(fill="x")
        
        lbl_pct = ctk.CTkLabel(line3, text="  0.0%", text_color=Theme.SEMI_MUTED,
                               font=FONT_SMALL, anchor="w")
        lbl_pct.pack(side="left")
        
        lbl_state = ctk.CTkLabel(line3, text="", text_color=Theme.ACCENT,
                                 font=FONT_SMALL, anchor="w")
        lbl_state.pack(side="left", padx=(8, 0))
        
        lbl_stats = ctk.CTkLabel(line3, text="", text_color=Theme.SEMI_MUTED,
                                 font=FONT_SMALL, anchor="e")
        lbl_stats.pack(side="right")
        
        line_error = ctk.CTkFrame(inner, fg_color="transparent")
        lbl_error = ctk.CTkLabel(line_error, text="", text_color=Theme.ERROR,
                                 font=FONT_SMALL, anchor="w", justify="left")
        lbl_error.pack(side="left")
        line_error.pack(fill="x", after=line3)
        line_error.pack_forget()
        
        def _press_handler(_e, _g=gid):
            self._on_mouse_press(_g, _e)
        _click_targets = [frame, inner, lbl_name, line3, lbl_pct, lbl_state, lbl_stats, icons_frame]
        if _title_lbl is not None:
            _click_targets.append(_title_lbl)
        for _w in _click_targets:
            try:
                _w.bind("<ButtonPress-1>", _press_handler, add="+")
            except Exception:
                pass
        
        return {
            "frame": frame, "lbl_name": lbl_name, "lbl_state": lbl_state,
            "bar": bar, "lbl_stats": lbl_stats, "lbl_pct": lbl_pct,
            "btn_pause": btn_pause, "btn_cancel": btn_cancel,
            "btn_open": btn_open, "btn_info": btn_info,
            "line_error": line_error, "lbl_error": lbl_error,
        }

    def _toggle_pause(self, gid):
        with self.tasks_lock:
            task = self.tasks.get(gid)
        if not task:
            return
        group_gids = task.get("group_gids") or [gid]
        res = self.rpc.tell_status(group_gids[0], ["status"])
        if res and "result" in res:
            status = res["result"]["status"]
            if status == "paused":
                for g in group_gids:
                    self.rpc.unpause(g)
            elif status in ("active", "waiting"):
                for g in group_gids:
                    self.rpc.pause(g)

    def _remove_task(self, gid):
        task = self.tasks.get(gid)
        if not task:
            return

        # 关闭可能残留的弹窗
        if task.get("retry_dialog"):
            try:
                task["retry_dialog"].destroy()
            except:
                pass

        is_completed = bool(task.get("completed"))

        # 未完成任务才弹窗确认
        if not is_completed:
            if len(self.tasks) == 1:
                msg = f"这是最后一个任务。\n\n{task['name']}\n\n删除后将退出程序，确定吗？"
            else:
                msg = f"删除任务?\n\n{task['name']}\n\n文件将被删除。"
            if not messagebox.askyesno("确认", msg):
                return

        group_gids = task.get("group_gids") or [gid]

        if is_completed:
            # 完成任务：只清 aria2 结果，不删磁盘文件
            for g in group_gids:
                try:
                    self.rpc.remove_download_result(g)
                except Exception:
                    pass
        else:
            # 未完成任务：取文件路径，从 aria2 移除，删磁盘文件
            file_paths = []
            for g in group_gids:
                try:
                    res = self.rpc.tell_status(g, ["files"])
                    if res and "result" in res and res["result"].get("files"):
                        fp = res["result"]["files"][0].get("path", "")
                        if fp:
                            file_paths.append(fp)
                except Exception:
                    pass
            for g in group_gids:
                try:
                    self.rpc.force_remove(g)
                    self.rpc.remove_download_result(g)
                except Exception:
                    pass
            for fp in file_paths:
                if fp and os.path.exists(fp):
                    try:
                        os.remove(fp)
                        if os.path.exists(fp + ".aria2"):
                            os.remove(fp + ".aria2")
                    except Exception:
                        pass

        if self.info.is_showing(gid):
            self.info.hide()
        # 销毁任务卡片并移除字典条目
        task["ui"]["frame"].destroy()
        with self.tasks_lock:
            if gid in self.tasks:
                del self.tasks[gid]
        self.selected_gids.discard(gid)
        self._update_layout()

        # 如果是最后一个任务，则关闭窗口
        if len(self.tasks) == 0:
            self._on_close()

    def _on_mouse_press(self, gid, event):
        self._drag_start = (event.x_root, event.y_root)
        self._drag_source_gid = gid
        self._drag_ctrl = bool(event.state & 0x0004)
        self._drag_active = False

    def _on_mouse_motion(self, event):
        if self._drag_start is None:
            return
        sx, sy = self._drag_start
        cx, cy = event.x_root, event.y_root
        if not self._drag_active:
            if max(abs(cx - sx), abs(cy - sy)) < 5:
                return
            self._drag_active = True
            self._show_drag_rect()
        self._update_drag_rect(sx, sy, cx, cy)
        self._update_drag_selection(sx, sy, cx, cy)

    def _on_mouse_release(self, event):
        if self._drag_start is None and not self._drag_active:
            return
        was_active = self._drag_active
        src = self._drag_source_gid
        ctrl = self._drag_ctrl
        self._drag_start = None
        self._drag_active = False
        self._drag_source_gid = None
        self._drag_ctrl = False
        if was_active:
            self._hide_drag_rect()
            return
        if src is not None:
            class _FakeEvent:
                pass
            fake = _FakeEvent()
            fake.state = 0x0004 if ctrl else 0
            self._on_card_click(src, fake)
        else:
            if self.selected_gids:
                self.selected_gids = set()
                self._update_card_selection()

    def _on_focus_out_cancel_drag(self, _e=None):
        if self._drag_active:
            self._cancel_drag()

    def _cancel_drag(self):
        self._drag_start = None
        self._drag_active = False
        self._drag_source_gid = None
        self._drag_ctrl = False
        self._hide_drag_rect()

    def _show_drag_rect(self):
        if self._drag_rect_win is not None:
            return
        try:
            top = tk.Toplevel(self)
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.25)
            top.configure(bg=Theme.ACCENT)
            self._drag_rect_win = top
        except Exception:
            self._drag_rect_win = None

    def _hide_drag_rect(self):
        if self._drag_rect_win is not None:
            try:
                self._drag_rect_win.destroy()
            except Exception:
                pass
            self._drag_rect_win = None

    def _update_drag_rect(self, x1, y1, x2, y2):
        if self._drag_rect_win is None:
            return
        x0 = min(x1, x2)
        y0 = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        try:
            self._drag_rect_win.geometry(f"{w}x{h}+{x0}+{y0}")
        except Exception:
            pass

    def _update_drag_selection(self, x1, y1, x2, y2):
        x0 = min(x1, x2)
        y0 = min(y1, y2)
        x1b = max(x1, x2)
        y1b = max(y1, y2)
        new_sel = set()
        with self.tasks_lock:
            tasks_snapshot = list(self.tasks.items())
        for _gid, _task in tasks_snapshot:
            _frame = _task.get("ui", {}).get("frame")
            if _frame is None:
                continue
            try:
                fx = _frame.winfo_rootx()
                fy = _frame.winfo_rooty()
                fw = _frame.winfo_width()
                fh = _frame.winfo_height()
            except Exception:
                continue
            if fx + fw < x0 or fx > x1b:
                continue
            if fy + fh < y0 or fy > y1b:
                continue
            new_sel.add(_gid)
        if new_sel != self.selected_gids:
            self.selected_gids = new_sel
            self._update_card_selection()

    def _on_card_click(self, gid, event):
        """卡片单击：单击单选，Ctrl+单击切换选中"""
        try:
            ctrl = bool(event.state & 0x0004)
        except Exception:
            ctrl = False
        with self.tasks_lock:
            if gid not in self.tasks:
                return
        if ctrl:
            if gid in self.selected_gids:
                self.selected_gids.discard(gid)
            else:
                self.selected_gids.add(gid)
        else:
            if self.selected_gids == {gid}:
                self.selected_gids = set()
            else:
                self.selected_gids = {gid}
        self._update_card_selection()

    def _update_card_selection(self):
        with self.tasks_lock:
            tasks_snapshot = list(self.tasks.items())
        for _gid, _task in tasks_snapshot:
            _frame = _task.get("ui", {}).get("frame")
            if _frame is None:
                continue
            try:
                if _gid in self.selected_gids:
                    _frame.configure(border_color=Theme.ACCENT)
                else:
                    _frame.configure(border_color=Theme.CARD)
            except Exception:
                pass

    def _get_target_gids(self):
        """返回操作目标 gids：仅返回当前选中的 gids，未选中则返回空"""
        if not self.selected_gids:
            return []
        with self.tasks_lock:
            all_gids = list(self.tasks.keys())
        return [g for g in all_gids if g in self.selected_gids]

    def _extract_metalink_b64(self, args_list):
        """从参数列表提取 --metalink 的 base64 内容（支持多个）"""
        result = []
        i = 0
        while i < len(args_list):
            a = args_list[i]
            if a == "--metalink" and i + 1 < len(args_list):
                result.append(args_list[i + 1])
                i += 2
            elif a.startswith("--metalink="):
                result.append(a.split("=", 1)[1])
                i += 1
            else:
                i += 1
        return result

    def _register_metalink_task(self, b64_content, display_name, no_cancel, task_title, task_countdown, opts=None):
        """新增 metalink 任务，成功返回组长 GID，失败返回 None"""
        try:
            res = self.rpc.add_metalink(b64_content, opts)
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"add_metalink failed: {e}")
            return None
        if not res or "result" not in res:
            return None
        gids = res["result"]
        if isinstance(gids, str):
            gids = [gids]
        if not gids:
            return None
        mh_map = parse_metalink_hashes_from_b64(b64_content)
        file_names = list(mh_map.keys())
        if task_title:
            initial_name = task_title
        elif file_names:
            initial_name = file_names[0]
        else:
            initial_name = display_name or "Metalink 任务"
        _leader = gids[0]
        _nc = no_cancel
        _tt = task_title
        _cd = task_countdown
        _mm = mh_map
        _fn = file_names
        _pn = (not file_names)
        self.after(0, lambda: self._register_task(
            _leader, initial_name, _nc,
            task_title=_tt, meta_hash_map=_mm,
            group_gids=gids, group_files=_fn,
            placeholder_name=_pn,
            countdown=_cd,
        ))
        return _leader

    def _parse_countdown_args(self, args_list):
        """从参数列表解析 --countdown 与 --global-countdown，返回 (task_cd, global_cd)"""
        task_cd = None
        global_cd = None
        i = 0
        while i < len(args_list):
            a = args_list[i]
            if a == "--countdown" and i + 1 < len(args_list):
                try:
                    task_cd = int(args_list[i + 1])
                except Exception:
                    pass
                i += 2
            elif a.startswith("--countdown="):
                try:
                    task_cd = int(a.split("=", 1)[1])
                except Exception:
                    pass
                i += 1
            elif a == "--global-countdown" and i + 1 < len(args_list):
                try:
                    global_cd = int(args_list[i + 1])
                except Exception:
                    pass
                i += 2
            elif a.startswith("--global-countdown="):
                try:
                    global_cd = int(a.split("=", 1)[1])
                except Exception:
                    pass
                i += 1
            else:
                i += 1
        return task_cd, global_cd

    def _apply_global_countdown(self, value):
        """设置全局倒计时，覆盖所有未钉死任务（重置已完成任务的倒计时起点）"""
        self.global_countdown = value
        with self.tasks_lock:
            items = list(self.tasks.items())
        for _gid, task in items:
            if task.get("countdown_pinned"):
                continue
            task["countdown"] = value
            if task.get("frozen"):
                task["countdown_start"] = time.time()

    def _tick_task_countdown(self):
        """检查所有已完成任务的倒计时，到点即删卡；无任务则关窗"""
        now = time.time()
        to_remove = []
        with self.tasks_lock:
            items = list(self.tasks.items())
        for _gid, task in items:
            if not task.get("frozen"):
                continue
            if task.get("countdown_start") is None:
                task["countdown_start"] = now
                continue
            cd = task.get("countdown", -1)
            if cd is None or cd < 0:
                continue
            start = task.get("countdown_start")
            if now - start >= cd:
                to_remove.append(_gid)
        if not to_remove:
            return
        for _gid in to_remove:
            if self.info.is_showing(_gid):
                self.info.hide()
            with self.tasks_lock:
                task = self.tasks.pop(_gid, None)
            if not task:
                continue
            try:
                task["ui"]["frame"].destroy()
            except Exception:
                pass
            self.selected_gids.discard(_gid)
        self._update_layout()
        with self.tasks_lock:
            empty = len(self.tasks) == 0
        if empty:
            self._on_close()

    def _bind_tooltip(self, widget, text):
        state = {"id": None, "win": None}

        def _show():
            state["id"] = None
            if state["win"] is not None:
                return
            try:
                win = tk.Toplevel(self)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.configure(bg="#1f2937")
                box = ctk.CTkFrame(
                    win, fg_color="#1f2937",
                    border_width=1, border_color="#4b5563",
                    corner_radius=6
                )
                box.pack(fill="both", expand=True)
                lbl = ctk.CTkLabel(
                    box, text=text, font=FONT_SMALL,
                    text_color=Theme.TEXT, fg_color="transparent"
                )
                lbl.pack(padx=8, pady=4)
                win.update_idletasks()
                wx = widget.winfo_rootx()
                wy = widget.winfo_rooty()
                ww = widget.winfo_width()
                wh = widget.winfo_height()
                tw = win.winfo_reqwidth()
                th = win.winfo_reqheight()
                x = wx + (ww - tw) // 2
                y = wy + wh + 6
                win.geometry(f"{tw}x{th}+{x}+{y}")
                state["win"] = win
                self._active_tooltip = win
            except Exception:
                state["win"] = None

        def _hide(_e=None):
            if state["id"]:
                try:
                    self.after_cancel(state["id"])
                except Exception:
                    pass
                state["id"] = None
            if state["win"] is not None:
                try:
                    state["win"].destroy()
                except Exception:
                    pass
                state["win"] = None
                if self._active_tooltip is not None:
                    self._active_tooltip = None

        def _enter(_e=None):
            _hide()
            state["id"] = self.after(200, _show)

        widget.bind("<Enter>", _enter, add="+")
        widget.bind("<Leave>", _hide, add="+")
        widget.bind("<ButtonPress>", _hide, add="+")

    def _open_config_gui(self):
        try:
            from ui_config import Aria2ConfigGUI
            dlg = Aria2ConfigGUI(self, is_master=True, on_submit=self._on_config_submit,
                                  initial_log_file=self.log_file)
            try:
                dlg.grab_set()
            except Exception:
                pass
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"open config gui failed: {e}")

    def _on_config_submit(self, aria2_args, title, log_file=None):
        if log_file:
            self.log_file = log_file
        try:
            self._add_task_from_args(aria2_args, explicit_title=title)
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"config submit failed: {e}")

    def _show_theme_menu(self):
        if getattr(self, "_theme_menu_win", None) is not None:
            self._close_theme_menu()
            return
        try:
            from config import THEMES
        except Exception:
            return
        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg="#1f2937")
        box = ctk.CTkFrame(top, fg_color=Theme.CARD, corner_radius=6,
                            border_width=1, border_color=Theme.MUTED)
        box.pack(fill="both", expand=True)

        def _pick(name):
            self._close_theme_menu()
            self._switch_theme(name)

        from config import theme_display_name
        for name in list(THEMES.keys()):
            is_cur = (name == getattr(self, "_current_theme", ""))
            label = ("\u2713 " if is_cur else "   ") + theme_display_name(name)
            ctk.CTkButton(
                box, text=label, anchor="w", width=150, height=28,
                fg_color="transparent", hover_color="#4b5563",
                text_color=(Theme.ACCENT if is_cur else Theme.TEXT),
                font=FONT_SMALL, corner_radius=4, border_width=0,
                command=lambda n=name: _pick(n),
            ).pack(fill="x", padx=4, pady=1)

        top.update_idletasks()
        w = top.winfo_reqwidth()
        h = top.winfo_reqheight()
        try:
            bx = self.btn_top_theme.winfo_rootx()
            by = self.btn_top_theme.winfo_rooty()
            bw = self.btn_top_theme.winfo_width()
            bh = self.btn_top_theme.winfo_height()
            x = bx + bw - w
            y = by + bh + 4
            top.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass
        self._theme_menu_win = top
        if getattr(self, "_theme_fg_id", None):
            try:
                self.after_cancel(self._theme_fg_id)
            except Exception:
                pass
        self._theme_fg_id = self.after(300, self._poll_theme_fg)

    def _poll_theme_fg(self):
        self._theme_fg_id = None
        if getattr(self, "_theme_menu_win", None) is None:
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != os.getpid():
                self._close_theme_menu()
                return
        except Exception:
            pass
        self._theme_fg_id = self.after(300, self._poll_theme_fg)

    def _close_theme_menu(self):
        if getattr(self, "_theme_fg_id", None):
            try:
                self.after_cancel(self._theme_fg_id)
            except Exception:
                pass
            self._theme_fg_id = None
        w = getattr(self, "_theme_menu_win", None)
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
            self._theme_menu_win = None

    def _switch_theme(self, name):
        try:
            from config import apply_theme, load_config, save_config
            apply_theme(name)
            self._current_theme = name
            cfg = load_config()
            cfg["theme"] = name
            save_config(cfg)
        except Exception as e:
            from utils import log_write
            log_write(self.log_file, f"switch theme failed: {e}")
        self._rebuild_ui()

    def _rebuild_ui(self):
        try:
            x = self.winfo_x()
            y = self.winfo_y()
        except Exception:
            x = y = None
        try:
            self._close_theme_menu()
        except Exception:
            pass
        try:
            self.info.hide()
        except Exception:
            pass
        self._active_tooltip = None
        for attr in ("header", "task_container", "footer"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
        with self.tasks_lock:
            items = list(self.tasks.items())
        for _gid, _task in items:
            _task["ui"] = {}
        try:
            self.configure(fg_color=Theme.BG)
        except Exception:
            pass
        self._build_ui()
        for gid, task in items:
            try:
                task["ui"] = self._create_task_row(
                    gid, task.get("name", ""),
                    task.get("no_cancel", False),
                    task.get("task_title"),
                )
            except Exception:
                pass
            if task.get("frozen"):
                try:
                    _ui = task["ui"]
                    _t = task.get("frozen_total", 0) or 0
                    _d = task.get("frozen_done", 0) or 0
                    _pct = (_d / _t * 100) if _t > 0 else 0
                    _elapsed = time.time() - task.get("start_time", time.time())
                    _ui["bar"].set(_pct / 100)
                    _ui["lbl_pct"].configure(text=f"{_pct:>5.1f}%")
                    _ui["lbl_state"].configure(text="", text_color=Theme.SUCCESS)
                    _ui["lbl_stats"].configure(text=(
                        f"{nice_duration(_elapsed):>7}→{nice_duration(0):<7}"
                        f"  {nice_size(_d):>9}/{nice_size(_t):<9}"
                        f"  {nice_size(0):>9}/s"
                    ))
                except Exception:
                    pass
        if x is not None and y is not None:
            try:
                self.geometry(f"+{x}+{y}")
            except Exception:
                pass
        self._update_layout()

    def _pause_all(self):
        for gid in self._get_target_gids():
            with self.tasks_lock:
                task = self.tasks.get(gid)
            if not task:
                continue
            for g in (task.get("group_gids") or [gid]):
                try:
                    self.rpc.pause(g)
                except Exception:
                    pass

    def _resume_all(self):
        for gid in self._get_target_gids():
            with self.tasks_lock:
                task = self.tasks.get(gid)
            if not task:
                continue
            if task.get("status") != "paused":
                continue
            for g in (task.get("group_gids") or [gid]):
                try:
                    self.rpc.unpause(g)
                except Exception:
                    pass

    def _retry_all(self):
        for gid in self._get_target_gids():
            with self.tasks_lock:
                task = self.tasks.get(gid)
            if not task:
                continue
            if task.get("status") == "error":
                self._retry_task(gid)

    def _clear_all(self):
        with self.tasks_lock:
            completed = [gid for gid, t in self.tasks.items() if t.get("completed")]
        for gid in completed:
            with self.tasks_lock:
                task = self.tasks.get(gid)
            if not task:
                continue
            try:
                task["ui"]["frame"].destroy()
            except Exception:
                pass
            with self.tasks_lock:
                self.tasks.pop(gid, None)
            self.selected_gids.discard(gid)
        self._update_layout()
        if len(self.tasks) == 0:
            self._on_close()

    def _open_folder(self, gid):
        with self.tasks_lock:
            task = self.tasks.get(gid)
        if not task:
            return
        cached = task.get("last_file_path")
        if cached:
            folder = os.path.dirname(cached)
            if folder and os.path.isdir(folder):
                try:
                    os.startfile(folder)
                    return
                except Exception:
                    pass
        group_gids = task.get("group_gids") or [gid]
        try:
            res = self.rpc.tell_status(group_gids[0], ["files", "dir"])
            if res and "result" in res:
                files = res["result"].get("files", [])
                if files:
                    fp = files[0].get("path", "")
                    if fp:
                        folder = os.path.dirname(fp)
                        if folder and os.path.isdir(folder):
                            os.startfile(folder)
                            return
                d = res["result"].get("dir", "")
                if d and os.path.isdir(d):
                    os.startfile(d)
        except Exception:
            pass

    def _retry_task(self, gid):
        """重试失败任务：调用 rpc.retry 获取新 GID，重建卡片并保留重试累积次数"""
        task = self.tasks.get(gid)
        if not task:
            return

        # ① 保存重置前需要保留的状态（error_retries）
        saved_error_retries = task.get("error_retries", 0)

        # ② 清理旧状态，并将标志位重置（重试后任务将进入 active/waiting，这些标志无需保留）
        task["retry_exhausted_dialog_shown"] = False
        task["retry_pending"] = False
        task["retry_after_id"] = None

        if task.get("retry_dialog"):
            try:
                task["retry_dialog"].destroy()
            except:
                pass

        # ③ 记录重建任务时需要的原始信息
        name = task.get("name", "")
        no_cancel = task.get("no_cancel", False)
        raw_uris = task.get("raw_uris", [])
        raw_opts = task.get("raw_opts", {})
        task_title = task.get("task_title")
        start_time = task.get("start_time", time.time())   # 保持累计耗时

        def _do_retry_thread():
            retry_opts = dict(raw_opts) if raw_opts else {}
            retry_opts.pop("gid", None)
            res = self.rpc.retry(gid, raw_uris, retry_opts)
            if res and "result" in res:
                new_gid = res["result"]
                def _update_ui():
                    # 销毁旧卡片
                    with self.tasks_lock:
                        old_task = self.tasks.pop(gid, None)
                        if old_task:
                            try:
                                old_task["ui"]["frame"].destroy()
                            except Exception:
                                pass
                    # 重建新卡片（按钮会自动绑定 new_gid）
                    self._register_task(
                        new_gid, name, no_cancel,
                        raw_uris, raw_opts,
                        task_title=task_title
                    )
                    # 将累积的重试次数写入新任务
                    with self.tasks_lock:
                        if new_gid in self.tasks:
                            new_task = self.tasks[new_gid]
                            new_task["error_retries"] = saved_error_retries
                            new_task["start_time"] = start_time  # 保持耗时连续性
                    self._update_layout()
                self.after(0, _update_ui)

        threading.Thread(target=_do_retry_thread, daemon=True).start()
        
    def _ui_refresh_loop(self):
        if not self.winfo_exists():
            return
        if not self.is_running:
            return

        def _fetch():
            results = {}
            with self.tasks_lock:
                gids = list(self.tasks.keys())
                all_gids = set(gids)
                for gid in gids:
                    t = self.tasks.get(gid)
                    if t and t.get("group_gids"):
                        all_gids.update(t["group_gids"])
            for gid in all_gids:
                res = self.rpc.tell_status(gid, [
                    "status", "totalLength", "completedLength", "downloadSpeed",
                    "files", "followedBy", "bittorrent", "errorMessage"
                ])
                results[gid] = res
            return results

        def _apply(results):
            if not self.is_running or not self.winfo_exists():
                return
            try:
                self._aggregate_group_results(results)
                active, g_total, g_done, g_speed = 0, 0, 0, 0
                for gid, res in list(results.items()):
                    handled, t, d, s, a = self._refresh_one_task(gid, res)
                    if handled:
                        g_total += t
                        g_done += d
                        g_speed += s
                        active += a
                self._update_global_stats(g_total, g_done, g_speed, active)
                self._handle_auto_shutdown(active)
                self._tick_task_countdown()
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                self._refresh_after_id = self.after(500, self._ui_refresh_loop)

        def _thread():
            results = _fetch()
            if self.is_running and self.winfo_exists():
                self.after(0, _apply, results)

        threading.Thread(target=_thread, daemon=True).start()

    def _aggregate_group_results(self, results):
        """把分组任务（组内多 GID）的 total/done/speed/files 聚合到组长条目上"""
        for _lg in list(self.tasks.keys()):
            with self.tasks_lock:
                _lt = self.tasks.get(_lg)
            if not _lt:
                continue
            _gg = _lt.get("group_gids") or [_lg]
            if len(_gg) <= 1:
                continue
            _agg_total, _agg_done, _agg_speed = 0, 0, 0
            _agg_error = ""
            _agg_files = []
            _statuses = []
            _valid = False
            for _g in _gg:
                _r = results.get(_g)
                if not _r or not isinstance(_r, dict) or "result" not in _r:
                    continue
                _rs = _r["result"]
                _valid = True
                _statuses.append(_rs.get("status", "unknown"))
                _agg_total += int(_rs.get("totalLength", 0))
                _agg_done += int(_rs.get("completedLength", 0))
                _agg_speed += int(_rs.get("downloadSpeed", 0))
                _agg_files.extend(_rs.get("files", []))
                if _rs.get("status") == "error" and not _agg_error:
                    _agg_error = _rs.get("errorMessage", "")
            if not _valid:
                continue
            _st_set = set(_statuses)
            if _st_set == {"complete"}:
                _agg_status = "complete"
            elif "error" in _st_set:
                _agg_status = "error"
            elif "active" in _st_set:
                _agg_status = "active"
            elif "waiting" in _st_set:
                _agg_status = "waiting"
            elif "paused" in _st_set:
                _agg_status = "paused"
            elif "removed" in _st_set:
                _agg_status = "removed"
            else:
                _agg_status = _statuses[0] if _statuses else "unknown"
            results[_lg] = {
                "result": {
                    "status": _agg_status,
                    "totalLength": str(_agg_total),
                    "completedLength": str(_agg_done),
                    "downloadSpeed": str(_agg_speed),
                    "errorMessage": _agg_error,
                    "files": _agg_files,
                }
            }

    def _refresh_one_task(self, gid, res):
        """刷新单任务 UI。返回 (handled, total, done, speed, active_delta)。
        handled=False 表示本任务不计入本轮全局统计。"""
        with self.tasks_lock:
            task = self.tasks.get(gid)
        if not task:
            return (False, 0, 0, 0, 0)

        if task.get("frozen"):
            self._update_task_ui(task["ui"], task, "complete",
                                 task["frozen_total"], task["frozen_done"], 0, None, gid)
            return (False, 0, 0, 0, 0)

        ui = task["ui"]
        if not res or not isinstance(res, dict) or "result" not in res:
            from utils import log_write
            log_write(self.log_file, f"[RPC-ABNORMAL] gid={gid} res={res} task_status={task.get('status')}")
            if task.get("status") in ("active", "waiting"):
                elapsed = int(time.time() - task["start_time"])
                try:
                    ui["lbl_stats"].configure(
                        text=f"{nice_duration(elapsed):>7}→异常暂停  0 B/s",
                        text_color=Theme.WARNING
                    )
                except Exception:
                    pass
                return (True, task.get("cached_total", 0), task.get("cached_done", 0), 0, 1)
            ui["frame"].destroy()
            with self.tasks_lock:
                self.tasks.pop(gid, None)
            self._update_layout()
            return (False, 0, 0, 0, 0)

        stat = res["result"]
        _f = stat.get("files", [])
        if _f:
            task["last_files"] = _f
            _fp = _f[0].get("path", "")
            if _fp:
                task["last_file_path"] = _fp
                task["last_dir"] = os.path.dirname(_fp)
        st = stat["status"]
        total = int(stat.get("totalLength", 0))
        done = int(stat.get("completedLength", 0))
        speed = int(stat.get("downloadSpeed", 0))

        if st == "removed":
            ui["frame"].destroy()
            with self.tasks_lock:
                self.tasks.pop(gid, None)
            self._update_layout()
            return (False, 0, 0, 0, 0)

        if st == "complete" and stat.get("followedBy"):
            new_gid = stat["followedBy"][0]
            ui["frame"].destroy()
            with self.tasks_lock:
                self.tasks.pop(gid, None)
            self._register_task(new_gid, task["name"], task.get("no_cancel", False))
            return (False, 0, 0, 0, 0)

        if task.get("placeholder_name") and stat.get("files"):
            try:
                new_name = os.path.basename(stat["files"][0].get("path", ""))
                if new_name and new_name != task["name"]:
                    ui["lbl_name"].configure(text=new_name)
                    task["name"] = new_name
                    task["placeholder_name"] = False
            except Exception:
                pass

        if not task.get("meta_hash") and task.get("meta_hash_map") and stat.get("files"):
            try:
                new_name = os.path.basename(stat["files"][0].get("path", ""))
                hlist = task["meta_hash_map"].get(new_name, [])
                if hlist:
                    task["meta_hash"] = {"algo": hlist[0][0], "hex": hlist[0][1], "file_name": new_name}
            except Exception:
                pass

        error_msg = stat.get("errorMessage", "")
        self._update_task_ui(ui, task, st, total, done, speed, error_msg, gid)
        _active = 1 if st in ("active", "waiting", "paused") else 0
        return (True, total, done, speed, _active)

    def _update_task_ui(self, ui, task, st, total, done, speed, error_msg=None, gid=None):
        
        if task.get("frozen"):
            # 冻结的任务不再更新状态，直接返回
            return

        if st == "complete" and not (total > 0 and done == total):
            st = "active"

        # 保存当前状态到任务字典
        task["status"] = st

        # ---------- 内部辅助函数 ----------
        def _is_retryable(msg):
            """判断错误消息是否属于可自动重试的类型"""
            if not msg:
                return False
            retryable_keywords = [
                "Name resolution", "Connection timed out",
                "Connection refused", "Could not connect",
                "SSL", "TLS", "handshake", "socket",
                "network", "timeout", "reset", "unreachable"
            ]
            return any(kw.lower() in msg.lower() for kw in retryable_keywords)

        def _show_final_error(ui, error_msg):
            """显示最终错误信息（不可重试或放弃重试）"""
            if error_msg:
                ui["lbl_error"].configure(text=f"❌ {error_msg}")
                def _do_translate():
                    translated = translate_error_online(error_msg)
                    display = translated if translated else error_msg
                    self.after(0, lambda: ui["lbl_error"].configure(text=f"❌ {display}"))
                threading.Thread(target=_do_translate, daemon=True).start()
            else:
                ui["lbl_error"].configure(text="❌ 未知错误")
            ui["line_error"].pack(after=ui["lbl_stats"].master, fill="x")
            if not task.get("error_visible"):
                task["error_visible"] = True
                self._update_layout()

        # ---------- 状态映射与通用更新 ----------
        state_text_map = {
            "error": ("[错误]", Theme.ERROR),
            "complete": ("", Theme.SUCCESS),
            "paused": ("", Theme.WARNING),
            "waiting": ("", Theme.WARNING),
            "active": ("", Theme.ACCENT),
        }
        st_text, st_color = state_text_map.get(st, ("", Theme.MUTED))
        if st == "active" and total == 0:
            st_text = "[元数据]"
            st_color = Theme.ACCENT
        ui["lbl_state"].configure(text=st_text, text_color=st_color)
        if st == "paused":
            tgt_pause_text, tgt_pause_state = "▶", "normal"
        elif st in ("active", "waiting"):
            tgt_pause_text, tgt_pause_state = "‖", "normal"
        else:
            tgt_pause_text, tgt_pause_state = None, "disabled"
        if (task.get("_btn_pause_text") != tgt_pause_text
                or task.get("_btn_pause_state") != tgt_pause_state):
            if tgt_pause_text is None:
                ui["btn_pause"].configure(state=tgt_pause_state)
            else:
                ui["btn_pause"].configure(text=tgt_pause_text, state=tgt_pause_state)
            task["_btn_pause_text"] = tgt_pause_text
            task["_btn_pause_state"] = tgt_pause_state
        tgt_cancel_state = "disabled" if (task.get("no_cancel") and st != "complete") else "normal"
        if task.get("_btn_cancel_state") != tgt_cancel_state:
            ui["btn_cancel"].configure(state=tgt_cancel_state)
            task["_btn_cancel_state"] = tgt_cancel_state
        # ===== 走马灯 =====
        _gf = task.get("group_files") or []
        if len(_gf) > 1 and (self.config.get("marquee_mode") or "scroll") == "switch":
            _interval = self.config.get("marquee_interval", 1.5) or 1.5
            _now = time.time()
            _last = task.get("marquee_last_switch", 0)
            if _now - _last >= _interval:
                task["marquee_index"] = (task.get("marquee_index", 0) + 1) % len(_gf)
                task["marquee_last_switch"] = _now
            _idx = task.get("marquee_index", 0)
            try:
                ui["lbl_name"].configure(text=_gf[_idx])
            except Exception:
                pass
        elapsed = time.time() - task["start_time"]
        eta = (total - done) / speed if speed > 0 and total > 0 else (0 if st == "complete" else -1)
        pct = (done / total * 100) if total > 0 else 0
        stats_text = (
            f"{nice_duration(elapsed):>7}→{nice_duration(eta):<7}"
            f"  {nice_size(done):>9}/{nice_size(total):<9}"
            f"  {nice_size(speed):>9}/s"
        )
        ui["lbl_stats"].configure(text=stats_text)
        ui["lbl_pct"].configure(text=f"{pct:>5.1f}%")
        ui["bar"].set(pct / 100)
        # 缓存本次进度，供 RPC 异常时用于全局统计
        task["cached_total"] = total
        task["cached_done"] = done

        # ---------- 错误状态特殊处理 ----------
        # 预处理错误消息：去除换行，避免 UI 显示错乱
        if error_msg:
            error_msg = error_msg.replace('\n', ' ').strip()
            
        if st == "error":
            retryable = _is_retryable(error_msg)
            should_retry = (
                retryable and
                task["error_retries"] < self.retry_count
            )

            if should_retry:
                # 防止在 aria2 切换状态的间隙里重复挂重试
                if not task.get("retry_pending"):
                    task["retry_pending"] = True
                    task["error_retries"] += 1
                    def do_retry(task_gid):
                        t = self.tasks.get(task_gid)
                        if t:
                            t["retry_pending"] = False  # 重试发出后清除标志
                            t["retry_after_id"] = None
                        self._retry_task(task_gid)
                    # 保存 after ID
                    task["retry_after_id"] = self.after(int(self.retry_interval * 1000), do_retry, gid)
                    # self.after(int(self.retry_interval * 1000), do_retry, gid)
                brief = error_msg[:60] + ("..." if len(error_msg) > 60 else "") if error_msg else ""
                ui["lbl_error"].configure(
                    text=f"⚠️ 正在重试 ({task['error_retries']}/{self.retry_count}) {brief}"
                )
                ui["line_error"].pack(after=ui["lbl_stats"].master, fill="x")
                if not task.get("error_visible"):
                    task["error_visible"] = True
                    self._update_layout()
            else:
                # 未进入 should_retry：不可重试错误，或者可重试但次数用尽
                if retryable and task["error_retries"] >= self.retry_count:
                    # 可重试错误，但次数已耗尽
                    if not task.get("retry_exhausted_dialog_shown"):
                        # 取消还在队列里的 do_retry 回调
                        if task.get("retry_after_id"):
                            try:
                                self.after_cancel(task["retry_after_id"])
                            except Exception:
                                pass
                            task["retry_after_id"] = None
                        task["retry_exhausted_dialog_shown"] = True
                        self._show_retry_exhausted_dialog(gid)
                        # 弹窗期间不显示其他错误文本，保持等待状态
                        ui["lbl_error"].configure(text="⏳ 等待重试确认...")
                        ui["line_error"].pack(after=ui["lbl_stats"].master, fill="x")
                    else:
                        # 用户已放弃，显示最终错误信息
                        _show_final_error(ui, error_msg)
        else:
            # 非错误状态：隐藏错误行，恢复按钮，清除相关标志
            if task.get("error_visible"):
                task["error_visible"] = False
                self._update_layout()
            ui["line_error"].pack_forget()
            # 重置重试及弹窗状态（离开错误状态时）
            task["retry_exhausted_dialog_shown"] = False
            task["retry_pending"] = False 
            task["retry_after_id"] = None  
            # 如果有残留对话框则关闭
            # 关闭可能残留的弹窗
            if task.get("retry_dialog"):
                try:
                    task["retry_dialog"].destroy()
                except:
                    pass

            # res = self.rpc.retry(gid)
            # if res and "result" in res:
                # new_gid = res["result"]
                # task_data = self.tasks.pop(gid)
                # 关键：不重置 error_retries，保留计数
                # task_data["status"] = "waiting"
                # task_data["start_time"] = time.time()
                # task_data["retry_pending"] = False
                # task_data["retry_after_id"] = None
                # self.tasks[new_gid] = task_data

        if st == "complete":
            if total > 0 and done == total:
                mh = task.get("meta_hash")
                if mh:
                    vs = task.get("verify_state")
                    if vs is None:
                        task["verify_state"] = "running"
                        task["verify_expected"] = mh.get("hex", "")
                        ui["lbl_state"].configure(text="[校验中]", text_color=Theme.WARNING)
                        threading.Thread(target=self._verify_hash_thread, args=(gid,), daemon=True).start()
                    elif vs == "running":
                        ui["lbl_state"].configure(text="[校验中]", text_color=Theme.WARNING)
                    elif vs == "ok":
                        if not task.get("frozen"):
                            try:
                                self.rpc.remove_download_result(gid)
                            except Exception:
                                pass
                            task["error_retries"] = 0
                            task["completed"] = True
                            task["frozen"] = True
                            task["frozen_total"] = total
                            task["frozen_done"] = done
                    elif vs == "failed":
                        ui["lbl_state"].configure(text="[校验失败]", text_color=Theme.ERROR)
                        ui["lbl_error"].configure(text=f"❌ Hash 不匹配: 期望 {task.get('verify_expected','')}, 实际 {task.get('verify_actual','')}")
                        if not task.get("error_visible"):
                            task["error_visible"] = True
                            ui["line_error"].pack(after=ui["lbl_stats"].master, fill="x")
                            self._update_layout()
                else:
                    if not task.get("frozen"):
                        # 真正完成：移除下载结果，删除 .aria2，冻结卡片
                        try:
                            self.rpc.remove_download_result(gid)
                        except Exception:
                            pass
                        task["error_retries"] = 0
                        task["completed"] = True
                        task["frozen"] = True
                        task["frozen_total"] = total
                        task["frozen_done"] = done
            
    def _verify_hash_thread(self, gid):
        with self.tasks_lock:
            task = self.tasks.get(gid)
        if not task:
            return
        mh = task.get("meta_hash")
        if not mh:
            return
        file_path = None
        try:
            res = self.rpc.tell_status(gid, ["files"])
            if res and "result" in res and res["result"].get("files"):
                file_path = res["result"]["files"][0].get("path", "")
        except Exception:
            pass
        if not file_path or not os.path.exists(file_path):
            self.after(0, self._verify_hash_done, gid, "failed", "", "文件不存在")
            return
        try:
            ok, actual = HashVerifier.verify(file_path, mh.get("hex", ""), mh.get("algo", "md5"))
            if ok:
                self.after(0, self._verify_hash_done, gid, "ok", actual, "")
            else:
                self.after(0, self._verify_hash_done, gid, "failed", actual, "")
        except Exception as e:
            self.after(0, self._verify_hash_done, gid, "failed", "", str(e))

    def _verify_hash_done(self, gid, state, actual, err):
        with self.tasks_lock:
            task = self.tasks.get(gid)
        if not task:
            return
        task["verify_state"] = state
        task["verify_actual"] = actual if not err else f"错误: {err}"
        if task.get("cached_total") is not None:
            self._update_task_ui(
                task["ui"], task, "complete",
                task.get("cached_total", 0),
                task.get("cached_done", 0),
                0, None, gid
            )

    def _marquee_tick(self):
        """走马灯定时器：scroll 模式下逐帧滚动多文件名"""
        if not self.is_running or not self.winfo_exists():
            return
        mode = self.config.get("marquee_mode") or "scroll"
        if mode != "scroll":
            self.after(200, self._marquee_tick)
            return
        speed = self.config.get("marquee_speed", 0.06) or 0.06
        try:
            frame_ms = max(20, int(float(speed) * 1000))
        except Exception:
            frame_ms = 60
        with self.tasks_lock:
            gids = list(self.tasks.keys())
        for gid in gids:
            with self.tasks_lock:
                task = self.tasks.get(gid)
            if not task or task.get("frozen"):
                continue
            gf = task.get("group_files") or []
            if len(gf) <= 1:
                continue
            full = " · ".join(gf) + " · "
            _WINDOW = 56
            _repeats = (_WINDOW // max(len(full), 1)) + 2
            _doubled = full * _repeats
            offset = task.get("scroll_offset", 0) % len(full)
            text = _doubled[offset:offset + _WINDOW]
            try:
                task["ui"]["lbl_name"].configure(text=text)
            except Exception:
                pass
            task["scroll_offset"] = (offset + 1) % len(full)
        self.after(frame_ms, self._marquee_tick)

    def _update_global_stats(self, total, done, speed, active):
        if len(self.tasks) > 0:
            elapsed = time.time() - self.app_start_time
            eta = (total - done) / speed if speed > 0 else (0 if active == 0 else -1)
            pct = (done / total * 100) if total > 0 else 0
            self.lbl_global_stats.configure(
                text=f"[{nice_size(speed)}/s] [{nice_duration(elapsed)} | {nice_duration(eta)}] "
                     f"[{nice_size(done)}/{nice_size(total)}] {pct:.1f}%"
            )
        else:
            self.lbl_global_stats.configure(text="")

    def _handle_auto_shutdown(self, active):
        with self.tasks_lock:
            tasks_snapshot = list(self.tasks.values())
        if not tasks_snapshot:
            self.title(f"{self.base_title} -- 等待...")
            return
        total = len(tasks_snapshot)
        completed = sum(1 for t in tasks_snapshot if t.get("completed") or t.get("status") == "complete")
        paused = sum(1 for t in tasks_snapshot if t.get("status") == "paused" and not t.get("completed"))
        errored = sum(1 for t in tasks_snapshot if t.get("status") == "error")
        downloading = max(0, total - completed - paused - errored)
        locked = any(not t.get("completed") and t.get("no_cancel") for t in tasks_snapshot)
        text = f"{total}个任务（{completed}个已完成/{downloading}个下载中/{paused}个暂停"
        if errored:
            text += f"/{errored}个失败"
        text += "）"
        if locked:
            text += " · 锁定"
        if errored:
            color = Theme.ERROR
        elif completed == total:
            color = Theme.SUCCESS
        else:
            color = Theme.ACCENT
        self.title(f"{self.base_title} -- {text}")

    def _try_close_window(self):
        with self.tasks_lock:
            locked = [t for t in self.tasks.values() if not t.get("completed") and t.get("no_cancel")]
        if locked:
            # 有锁定的未完成任务，完全禁止关闭（不弹窗）
            return
        running = [t for t in self.tasks.values() if not t.get("completed")]
        if running and not messagebox.askyesno("退出", f"有{len(running)}个任务,确定退出?"):
            return
        self._on_close()

    def _on_error(self, msg):
        if not self.is_running:
            return
        self.is_running = False
        if self.aria2_proc:
            stop_aria2c(self.aria2_proc, self.log_file)
        messagebox.showerror("错误", msg)
        self._on_close()

    def _on_close(self):
        if self.is_running:
            self.is_running = False
            try:
                self._close_theme_menu()
            except Exception:
                pass
            try:
                self._do_hide_info()
            except Exception:
                pass
            # 取消 UI 刷新
            if self._refresh_after_id:
                self.after_cancel(self._refresh_after_id)
                self._refresh_after_id = None
            # 尝试通过 RPC 优雅关闭
            try:
                self.rpc.shutdown()
                time.sleep(0.5)
            except:
                pass
            # 如果有进程对象，强制终止
            if self.aria2_proc:
                stop_aria2c(self.aria2_proc, self.log_file)
            else:
                # 兜底：通过进程名强制终止所有 aria2c
                import subprocess, sys
                if sys.platform == 'win32':
                    subprocess.run('taskkill /f /im aria2c.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.master.quit()
        self.master.destroy()

    def _show_retry_exhausted_dialog(self, gid):
        """重试次数用尽后的确认对话框（带倒计时），加固版"""
        task = self.tasks.get(gid)
        if not task:
            return
    
        # ui = task["ui"]
        # 安全禁用按钮
        try:
            self._disable_task_buttons(gid)
        except Exception:
            pass

        dialog = ctk.CTkToplevel(self)
        dialog.title("重试确认")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.attributes("-topmost", True)
        # 强制更新，确保窗口完全创建
        dialog.update_idletasks()

        name = task.get("task_title") or task["name"]
        dialog.title(f"重试确认 - {name}")
        timeout = getattr(self, 'retry_exhausted_timeout', 10) or 10
        remaining = timeout

        lbl = ctk.CTkLabel(dialog,
                           text=f"「{name}」重试次数已用尽\n自动重试倒计时 {remaining} 秒",
                           font=FONT_SMALL, justify="left")
        lbl.pack(padx=10, pady=(10, 5))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=5)

        countdown_id = None

        def cancel_countdown():
            nonlocal countdown_id
            if countdown_id is not None:
                try:
                    self.after_cancel(countdown_id)
                except Exception:
                    pass
                countdown_id = None

        def do_retry():
            cancel_countdown()
            try:
                dialog.destroy()
            except Exception:
                pass
            task["error_retries"] = 0
            task["retry_exhausted_dialog_shown"] = False
            # 恢复按钮状态
            self._restore_task_buttons(gid)
            self._retry_task(gid)

        def do_abort():
                cancel_countdown()
                try:
                    dialog.destroy()
                except Exception:
                    pass
                # 标记已放弃
                task["retry_exhausted_dialog_shown"] = True
                # 按钮状态恢复（虽然后面会销毁，但保险）
                self._restore_task_buttons(gid)
                # 从 aria2 移除任务并删除卡片（不弹确认框，不删除文件）
                try:
                    self.rpc.force_remove(gid)
                    self.rpc.remove_download_result(gid)
                except Exception:
                    pass
                # 销毁 UI 卡片
                try:
                    task["ui"]["frame"].destroy()
                except Exception:
                    pass
                # 从任务字典中移除
                if gid in self.tasks:
                    del self.tasks[gid]
                self._update_layout()
                # 如果所有任务都被删除了，关闭窗口
                if len(self.tasks) == 0:
                    self._on_close()
                # 页面更新交给下次 _update_task_ui 完成

        btn_retry_now = create_button(btn_frame, text="立即重试", width=90, style="primary", command=do_retry)
        btn_retry_now.pack(side="left", padx=5)
        btn_abort = create_button(btn_frame, text="放弃", width=90, style="secondary", command=do_abort)
        btn_abort.pack(side="left", padx=5)

        def update_countdown(count):
            nonlocal countdown_id
            if count <= 0:
                do_retry()
                return
            try:
                if lbl.winfo_exists():
                    lbl.configure(text=f"「{name}」重试次数已用尽\n自动重试倒计时 {count} 秒")
                    countdown_id = self.after(1000, update_countdown, count - 1)
                # 如果标签已消失，不再继续
            except Exception:
                pass

        # 延迟 200ms 开始倒计时，确保窗口完全映射
        self.after(200, update_countdown, remaining)

        dialog.protocol("WM_DELETE_WINDOW", do_abort)

        # 保存对话框引用，以便任务删除时清理
        task["retry_dialog"] = dialog
        
    def _disable_task_buttons(self, gid):
        """禁用指定任务的暂停/取消按钮（用于弹窗期间）"""
        task = self.tasks.get(gid)
        if not task:
            return
        ui = task["ui"]
        ui["btn_pause"].configure(state="disabled")
        ui["btn_cancel"].configure(state="disabled")
        

    def _restore_task_buttons(self, gid):
        """恢复指定任务按钮的正常状态"""
        task = self.tasks.get(gid)
        if not task:
            return
        ui = task["ui"]
        # 根据任务当前状态重新设置按钮
        st = task.get("status", "error")
        if st in ("active", "waiting"):
            ui["btn_pause"].configure(text="‖", state="normal")
        elif st == "paused":
            ui["btn_pause"].configure(text="▶", state="normal")
        else:
            ui["btn_pause"].configure(state="disabled")
        if task.get("no_cancel") and st != "complete":
            ui["btn_cancel"].configure(state="disabled")
        else:
            ui["btn_cancel"].configure(state="normal")