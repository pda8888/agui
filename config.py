#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置常量和默认参数"""
import sys
import os


# === 版本信息 ===
APP_TITLE = "老王的小拖船 V1.4"
APP_VERSION = "1.4.0"

# === 网络配置 ===
RPC_HOST = "127.0.0.1"
RPC_PORT = 16800  # 动态分配
IPC_PORT = 19811  # 进程间通信
RPC_STARTUP_WAIT = 0.25
RPC_STARTUP_RETRIES = 20

# === 文件路径 ===
ARIA2_FILENAME = "aria2c.exe"

def get_aria2c_path():
    """获取aria2c可执行文件路径"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        temp_path = os.path.join(sys._MEIPASS, ARIA2_FILENAME)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        fixed_path = os.path.join(exe_dir, ARIA2_FILENAME)
        
        if not os.path.exists(fixed_path) or os.path.getmtime(temp_path) > os.path.getmtime(fixed_path):
            try:
                import shutil
                shutil.copy2(temp_path, fixed_path)
            except:
                pass
        
        return fixed_path if os.path.exists(fixed_path) else temp_path
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), ARIA2_FILENAME)

ARIA2_PATH = get_aria2c_path()

# === UI 颜色主题 ===
class Theme:
    BG = "#1f2937"
    CARD = "#374151"
    ACCENT = "#22d3ee"
    ACCENT_LIGHT = "#4b5563"
    TEXT = "#f9fafb"
    MUTED = "#9ca3af"
    SEMI_MUTED = "#d1d5db"
    ERROR = "#ef4444"
    SUCCESS = "#34d399"
    WARNING = "#fbbf24"

# === Aria2 默认配置 ===
def get_default_aria2_args(base_path):
    """返回aria2c默认启动参数"""
    dht_dat = os.path.join(base_path, "dht.dat")
    dht6_dat = os.path.join(base_path, "dht6.dat")
    
    return {
        "--enable-rpc": "true",
        "--check-integrity": "true",
        "--rpc-listen-port": str(RPC_PORT),
        "--rpc-listen-all": "false",
        "--rpc-allow-origin-all": "true",
        "--continue": "true",
        "--summary-interval": "1",
        "--check-certificate": "false",
        "--save-session-interval": "60",
        "--min-split-size": "1M",
        "--max-connection-per-server": "16",
        "--max-overall-upload-limit": "1K",
        "--listen-port": "6881-6999",
        "--bt-enable-hook-after-hash-check": "true",
        "--bt-enable-lpd": "true",
        "--bt-exclude-tracker": "",
        "--bt-hash-check-seed": "true",
        "--bt-load-saved-metadata": "true",
        "--bt-metadata-only": "false",
        "--bt-max-peers": "100",
        "--bt-request-peer-speed-limit": "200K",
        "--seed-ratio": "0.0",
        "--seed-time": "0",
        "--bt-save-metadata": "true",
        "--bt-seed-unverified": "false",
        "--bt-stop-timeout": "0",
        "--bt-tracker-connect-timeout": "60",
        "--bt-tracker-interval": "0",
        "--bt-tracker-timeout": "60",
        "--enable-dht": "true",
        "--enable-dht6": "true",
        "--dht-listen-port": "6881-6999",
        "--dht-entry-point": "router.bittorrent.com:6881",
        "--dht-entry-point6": "router.bittorrent.com:6881",
        "--dht-file-path": dht_dat,
        "--dht-file-path6": dht6_dat,
        "--enable-peer-exchange": "true",
        "--disable-ipv6": "false",
        "--bt-force-encryption": "false",
        "--bt-require-crypto": "false",
        "--bt-min-crypto-level": "plain",
        "--max-tries": "3",
        "--retry-wait": "5",
        "--timeout": "10",
        "--connect-timeout": "10",        
    }

# === 任务级参数黑名单 ===
TASK_ARGS_BLACKLIST = [
    "--dir", "-d",
    "--out", "-o",
    "--split", "-s",
    "--max-connection-per-server", "-x",
    "--max-download-limit",
    "--min-split-size",
    "--referer",
    "--user-agent",
    "--file-allocation",
    "--header",
    "--all-proxy",
]

# === UI专用参数 ===
UI_ARG_PREFIXES = (
    "--title",
    "--countdown",
    "--log-to",
    "--retry-countdown",
    "--position",
    "--auto-referer",
    "--retry",
    "--retry-interval",
    "--retry-exhausted-timeout",
    "--query",
    "--kill",
    "--gid",
    "--callback-port",
    "--http-port",
    "-silent",
    "--metalink",
    "--verify-hash",
    "--marquee-interval",
    "--marquee-mode",
    "--marquee-speed",
)

# === RPC选项映射 ===
RPC_OPTION_MAPPING = {
    "--dir": "dir",
    "-d": "dir",
    "--out": "out",
    "-o": "out",
    "--split": "split",
    "-s": "split",
    "--max-connection-per-server": "max-connection-per-server",
    "-x": "max-connection-per-server",
    "--max-download-limit": "max-download-limit",
    "--min-split-size": "min-split-size",
    "--check-certificate": "check-certificate",
    "--referer": "referer",
    "--user-agent": "user-agent",
    "--file-allocation": "file-allocation",
    "--header": "header",
    "--all-proxy": "all-proxy",
    "--bt-max-peers": "bt-max-peers",
}

# === 默认User-Agent ===
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"