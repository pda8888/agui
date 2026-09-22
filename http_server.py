#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP API 服务（从 ui_download.py 剥离）"""
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

from utils import log_write


def make_handler(gui):
    """生成绑定 gui 引用的 APIHandler 类"""

    class APIHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/api":
                self.send_error(404)
                return
            try:
                content_length = int(self.headers["Content-Length"])
                body = self.rfile.read(content_length)
                data = json.loads(body)
                method = data.get("method")
                params = data.get("params", {})

                if method == "add":
                    self._handle_add(params)
                elif method == "query":
                    self._handle_query(params)
                elif method == "kill":
                    self._handle_kill(params)
                else:
                    self._send_json({"status": "failed", "message": "unknown method"})
            except Exception as e:
                self._send_json({"status": "failed", "message": str(e)})

        def _handle_add(self, params):
            if not isinstance(params, dict):
                self._send_json({"status": "failed", "message": "params must be a JSON object"})
                return

            metalink_b64 = params.get("metalink")
            urls = params.get("urls")
            has_urls = isinstance(urls, list) and len(urls) > 0
            has_url = isinstance(params.get("url"), str) and bool(params["url"].strip())
            has_metalink = isinstance(metalink_b64, str) and bool(metalink_b64.strip())
            if has_urls:
                pass
            elif has_url:
                urls = [params["url"]]
            else:
                urls = []
            if not has_urls and not has_url and not has_metalink:
                self._send_json({"status": "failed", "message": "url, urls or metalink is required"})
                return

            global_keys = {
                "log-to": ("log_file", str),
                "retry": ("retry_count", int),
                "retry-interval": ("retry_interval", int),
                "retry-exhausted-timeout": ("retry_exhausted_timeout", int),
                "position": ("position_offset", str),
            }
            for key, value in params.items():
                if key in global_keys:
                    attr_name, _type = global_keys[key]
                    try:
                        if value is not None:
                            setattr(gui, attr_name, _type(value))
                    except Exception:
                        pass

            cmd_args = []
            task_keys_map = {
                "title": "--title",
                "out": "--out",
                "dir": "--dir",
                "auto-referer": "--auto-referer",
                "no-cancel": "--no-cancel",
            }
            for key, flag in task_keys_map.items():
                value = params.get(key)
                if value is not None:
                    if isinstance(value, bool) and value:
                        cmd_args.append(flag)
                    elif value != "":
                        cmd_args.append(flag)
                        cmd_args.append(str(value))

            _cd = params.get("countdown")
            if _cd is not None and _cd != "":
                cmd_args.append("--countdown=" + str(_cd))
            _gcd = params.get("global-countdown")
            if _gcd is not None and _gcd != "":
                cmd_args.append("--global-countdown=" + str(_gcd))

            if has_metalink:
                cmd_args.append("--metalink=" + metalink_b64.strip())

            aria2_opts = params.get("aria2_opts", {})
            if isinstance(aria2_opts, dict):
                for k, v in aria2_opts.items():
                    if v is not None and v != "":
                        cmd_args.append("--" + k)
                        cmd_args.append(str(v))

            for u in urls:
                cmd_args.append(u)

            gid = gui._add_task_sync(cmd_args)
            if gid:
                self._send_json({"status": "success", "GID": gid})
            else:
                self._send_json({"status": "failed", "message": "failed to add task"})

        def _handle_query(self, params):
            gid = params.get("gid") if isinstance(params, dict) else None
            if not gid:
                self._send_json({"status": "failed", "message": "gid required"})
                return
            try:
                res = gui.rpc.tell_status(gid, [
                    "status", "totalLength", "completedLength",
                    "downloadSpeed", "errorMessage", "files"
                ])
            except Exception:
                with gui.tasks_lock:
                    task = gui.tasks.get(gid)
                if task:
                    self._send_json({
                        "status": "success",
                        "data": self._build_fallback_status(task)
                    })
                else:
                    self._send_json({
                        "status": "failed",
                        "message": "task initializing or aria2 not ready, retry later"
                    })
                return

            if res and "result" in res:
                result = res["result"]
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
                    except Exception:
                        pass
                result["downloadReady"] = complete
                self._send_json({"status": "success", "data": result})
            else:
                with gui.tasks_lock:
                    task = gui.tasks.get(gid)
                if task:
                    self._send_json({
                        "status": "success",
                        "data": self._build_fallback_status(task)
                    })
                else:
                    self._send_json({
                        "status": "failed",
                        "message": "task initializing or not found, retry later"
                    })

        @staticmethod
        def _build_fallback_status(task):
            st = task.get("status", "unknown")
            total = str(task.get("frozen_total", 0)) or "0"
            completed = str(task.get("frozen_done", 0)) or "0"
            return {
                "status": st,
                "totalLength": total,
                "completedLength": completed,
                "downloadSpeed": "0",
                "errorMessage": "",
                "downloadReady": (st == "complete")
            }

        def _handle_kill(self, params):
            gid = params.get("gid") if isinstance(params, dict) else None
            if not gid:
                self._send_json({"status": "failed", "message": "gid required"})
                return
            exists = False
            with gui.tasks_lock:
                _local_exists = gid in gui.tasks
            if _local_exists:
                exists = True
            else:
                res = gui.rpc.tell_status(gid, ["status"])
                if res and "result" in res:
                    exists = True
            if not exists:
                self._send_json({"status": "failed", "message": "gid not found"})
                return
            try:
                gui.rpc.force_remove(gid)
                gui.rpc.remove_download_result(gid)
                gui.after(0, lambda g=gid: self._cleanup_ui(g))
                self._send_json({"status": "success", "message": "task killed"})
            except Exception as e:
                self._send_json({"status": "failed", "message": str(e)})

        def _cleanup_ui(self, gid):
            if gid in gui.tasks:
                task = gui.tasks[gid]
                if task.get("retry_dialog"):
                    try:
                        task["retry_dialog"].destroy()
                    except Exception:
                        pass
                task["ui"]["frame"].destroy()
                del gui.tasks[gid]
                gui._update_layout()
                if len(gui.tasks) == 0:
                    gui._on_close()

        def _send_json(self, data):
            response = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(response))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    return APIHandler


def run_http_server(gui, port, log_file):
    """启动 HTTP API 服务（阻塞运行，应在守护线程中调用）"""
    if not log_file:
        gui.log_file = "agui.log"
        log_file = "agui.log"
    handler_cls = make_handler(gui)
    try:
        server = HTTPServer(("127.0.0.1", port), handler_cls)
    except OSError as e:
        log_write(log_file, f"HTTP 端口 {port} 被占用: {e}")
        gui.after(0, gui._on_close)
        return
    try:
        server.serve_forever()
    except Exception as e:
        log_write(log_file, f"HTTP server crashed: {e}")
