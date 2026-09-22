#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ctypes
import customtkinter as ctk
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PerMonitorV2
except Exception:
    pass

"""
老王的小拖船 V1.4 - 主程序入口 (CustomTkinter版 - 修复根窗口问题)
"""
import sys
import os
# import pickle
import json
      
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gc

# 无参数启动时，立即隐藏控制台窗口，避免长时间黑屏
if sys.platform == "win32" and len(sys.argv) == 1:
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass

# 设置外观模式
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def send_result_via_callback(port, json_str):
    """将结果 JSON 发送到调用者指定的回调端口，成功返回 True，失败返回 False"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(("127.0.0.1", port))
        s.sendall((json_str + "\n").encode("utf-8"))
        s.close()
        return True
    except Exception:
        return False
        
# === 主函数 ===
def main():
    raw_args = sys.argv[1:]
            
    # 0. 检查帮助参数
    if any(arg in ("-h", "--help", "/?") for arg in raw_args):
        from ui_help import show_help
        show_help()
        sys.exit(0)
    
    
    # 2. 设置进程保护
    from process_manager import setup_job_object, update_firewall_rules
    if sys.platform == "win32":
        setup_job_object()
    
    # 3. 解析参数（提前，以便后续分支使用 cfg）
    from arg_parser import parse_args
    from utils import extract_urls_and_out
    cfg = parse_args(raw_args)
    # 决定是否显示 GUI：无参数或显式指定 -gui 时显示
    silent = cfg.get("silent", False)
    show_gui = not silent
    cfg["show_gui"] = show_gui

    # 加载用户配置并应用主题
    try:
        from config import apply_theme, load_config
        _user_cfg = load_config()
        apply_theme(_user_cfg.get("theme", "midnight"))
    except Exception:
        pass

    # 4. 检测是否为主实例
    from ipc_server import try_bind_ipc_port, try_send_to_main_instance
    from utils import log_write, ensure_log_file
    is_master, server_socket = try_bind_ipc_port()
    if not is_master:
        if raw_args and "--query" not in raw_args and "--kill" not in raw_args:
            reply = try_send_to_main_instance(raw_args)
            if reply is not None:
                callback_port = cfg.get("callback_port")
                if callback_port:
                    if not send_result_via_callback(callback_port, reply):
                        log_write(cfg.get("log_file"), f"回调发送失败: {reply}")
                else:
                    log_write(cfg.get("log_file"), f"无法返回结果，缺少回调端口：{reply}")
                sys.exit(0)
    
    if is_master and not cfg.get("log_file"):
        import time as _time
        _ts = _time.strftime("%Y-%m-%d-%H-%M")
        _base = f"agui-{_ts}"
        _fname = _base + ".log"
        _i = 1
        while os.path.exists(_fname):
            _fname = f"{_base}-{_i}.log"
            _i += 1
        cfg["log_file"] = _fname

    if cfg.get("log_file"):
        ensure_log_file(cfg["log_file"])


    if is_master:
        fw_ok = update_firewall_rules()
        if not fw_ok:
            log_write(cfg.get("log_file"), "warn: 防火墙规则未添加（非管理员或失败），BT/DHT 监听可能被系统防火墙拦截")
    
    # 杀死任务：连接主实例发送 KILL 命令，立即退出
    if cfg.get("kill_gid"):
        callback_port = cfg.get("callback_port")
        if not callback_port:
            log_write(cfg.get("log_file"), "Kill 失败：未提供 --callback-port 参数")
            sys.exit(1)
        import socket as _socket
        from ipc_server import IPC_PORT
        result_json = None
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect(("127.0.0.1", IPC_PORT))
            # req = pickle.dumps(["KILL", cfg["kill_gid"]])
            req = json.dumps(["KILL", cfg["kill_gid"]]).encode("utf-8")
            s.sendall(req)
            resp = s.recv(4096)
            if resp:
                result_json = resp.decode("utf-8").strip()
            s.close()
        except Exception as e:
            result_json = json.dumps({"status": "failed", "message": f"无法连接到主实例: {str(e)}"})
        if result_json:
            if not send_result_via_callback(callback_port, result_json):
                log_write(cfg.get("log_file"), f"回调发送失败: {result_json}")
        sys.exit(0)
        
    if cfg.get("query_gid"):
        callback_port = cfg.get("callback_port")
        if not callback_port:
            log_write(cfg.get("log_file"), "查询失败：未提供 --callback-port 参数")
            sys.exit(1)
        import socket as _socket
        from ipc_server import IPC_PORT
        result_json = None
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect(("127.0.0.1", IPC_PORT))
            # req = pickle.dumps(["QUERY", cfg["query_gid"]])
            req = json.dumps(["QUERY", cfg["query_gid"]]).encode("utf-8")
            s.sendall(req)
            resp = s.recv(4096)
            if resp:
                result_json = resp.decode("utf-8").strip()
            s.close()
        except Exception as e:
            result_json = json.dumps({"status": "failed", "message": f"无法连接到主实例: {str(e)}"})
        if result_json:
            send_result_via_callback(callback_port, result_json)
        sys.exit(0)
        
    # 【核心修改】创建一个持久的、隐藏的根窗口
    root = ctk.CTk()
    root.withdraw() # 隐藏主窗口
    
    # 5. 如果没有URL,打开配置界面 (作为 Toplevel 运行)
    # 但如果指定了 --http-port，跳过配置界面，直接进入后台下载模式
    _has_metalink = any(
        a == "--metalink" or a.startswith("--metalink=")
        for a in cfg["aria2_args"]
    )
    if (not cfg.get("http_port")
            and not extract_urls_and_out(cfg["aria2_args"])[0]
            and not _has_metalink):

        from ui_config import Aria2ConfigGUI
        
        # 传入 root 作为父窗口
        # app_config = Aria2ConfigGUI(root, is_master)
        auto_referer = cfg.get("auto_referer", False)
        app_config = Aria2ConfigGUI(root, is_master, auto_referer=auto_referer,
                                      initial_log_file=cfg.get("log_file"))
        
        # 等待配置窗口关闭 (阻塞执行)
        root.wait_window(app_config)
        
        # 检查是否有配置生成
        if hasattr(app_config, "launch_cfg") and app_config.launch_cfg:
            cfg = app_config.launch_cfg
            # 保留原始的 show_gui 设置（配置界面不应改变该行为）
            cfg["show_gui"] = show_gui
            del app_config
            gc.collect()
        else:
            # 用户直接关闭了配置窗口，没有生成配置
            root.destroy()
            return

    # 6. 初始化RPC
    from utils import find_free_port, find_user_rpc_port
    import config
    import rpc_client
    
    user_port = find_user_rpc_port(cfg["aria2_args"])
    if user_port:
        config.RPC_PORT = user_port
    else:
        config.RPC_PORT = find_free_port()
    
    rpc_url = f"http://{config.RPC_HOST}:{config.RPC_PORT}/jsonrpc"
    rpc_client.set_rpc_url(rpc_url)
    
    if cfg.get("log_file"):
        cfg["log_file"] = os.path.abspath(cfg["log_file"])
    
    # 7. 启动下载界面 (作为 Toplevel 运行)
    from ui_download import Aria2GUI # noqa: F401
    
    # 8. 启动主循环 (实际上是 root 在运行，但 root 是隐藏的)
    # 将命令行指定的 --gid 传递给下载窗口（如果提供）
    # cfg 中已包含解析结果，无需额外操作
    Aria2GUI(root, cfg, server_socket)
    root.mainloop()

if __name__ == "__main__":
    main()
