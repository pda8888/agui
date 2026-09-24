#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置常量和默认参数"""
import sys
import os
import json


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
    """获取aria2c可执行文件路径；不存在返回 None（slim 包场景）"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        temp_path = os.path.join(sys._MEIPASS, ARIA2_FILENAME)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        fixed_path = os.path.join(exe_dir, ARIA2_FILENAME)

        temp_exists = os.path.exists(temp_path)
        fixed_exists = os.path.exists(fixed_path)

        if temp_exists:
            try:
                need_copy = (not fixed_exists) or os.path.getmtime(temp_path) > os.path.getmtime(fixed_path)
            except Exception:
                need_copy = False
            if need_copy:
                try:
                    import shutil
                    shutil.copy2(temp_path, fixed_path)
                    fixed_exists = True
                except Exception:
                    pass

        if fixed_exists:
            return fixed_path
        if temp_exists:
            return temp_path
        return None
    else:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ARIA2_FILENAME)
        return _p if os.path.exists(_p) else None

ARIA2_PATH = get_aria2c_path()


def resolve_aria2_path(cli_path=None, on_progress=None, on_need_manual=None, log_path=None):
    """按决策链解析 aria2c 路径（仅解析/下载，不做启动验证）。
    1. cli_path 指定且存在 → 返回该路径
    2. %TEMP%\aria2c.exe 存在 → 返回
    3. 用 aria2_fetcher 下载到 %TEMP% → 成功返回
    4. 下载失败 → 调 on_need_manual() 让上层弹窗选手选；返回手选路径或 None
    启动失败后的重试由调用方处理。
    """
    if cli_path:
        _cp = os.path.abspath(cli_path)
        if os.path.isfile(_cp):
            return _cp
    from aria2_fetcher import fetch_aria2c, default_target_dir
    _dir = default_target_dir()
    _temp_exe = os.path.join(_dir, ARIA2_FILENAME)
    if os.path.isfile(_temp_exe):
        return _temp_exe
    _got = fetch_aria2c(target_dir=_dir, progress_cb=on_progress)
    if _got:
        return _got
    if on_need_manual:
        try:
            _manual = on_need_manual()
        except Exception:
            _manual = None
        if _manual and os.path.isfile(_manual):
            return _manual
    return None


def get_asset_path(name):
    """获取 assets/ 下资源文件路径，兼容 PyInstaller 打包"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)

# === UI 颜色主题 ===
THEMES = {
    "midnight": {
        "BG": "#1f2937",
        "CARD": "#374151",
        "ACCENT": "#22d3ee",
        "ACCENT_LIGHT": "#4b5563",
        "TEXT": "#f9fafb",
        "MUTED": "#9ca3af",
        "SEMI_MUTED": "#d1d5db",
        "ERROR": "#ef4444",
        "SUCCESS": "#34d399",
        "WARNING": "#fbbf24",
        "_style": "flat",
    },
    "cp1": {
        "BG": "#0D1117",
        "CARD": "#161B22",
        "ACCENT": "#00E5FF",
        "ACCENT_LIGHT": "#58A6FF",
        "TEXT": "#C9D1D9",
        "MUTED": "#8B949E",
        "SEMI_MUTED": "#79C0FF",
        "ERROR": "#F43F5E",
        "SUCCESS": "#3FB950",
        "WARNING": "#F59E0B",
        "_style": "cyber",
    },
    "cp2": {
        "BG": "#0d0221",
        "CARD": "#1a0b2e",
        "ACCENT": "#f72585",
        "ACCENT_LIGHT": "#7209b7",
        "TEXT": "#f0e9ff",
        "MUTED": "#7b6d9c",
        "SEMI_MUTED": "#b8a9d9",
        "ERROR": "#ff0054",
        "SUCCESS": "#00f5d4",
        "WARNING": "#fee440",
        "_style": "cyber",
    },
    "neon_dreams": {
        "BG": "#0B0D17",
        "CARD": "#161A2B",
        "ACCENT": "#00FFFF",
        "ACCENT_LIGHT": "#FF007A",
        "TEXT": "#F5F5F5",
        "MUTED": "#6B7394",
        "SEMI_MUTED": "#A6ACCF",
        "ERROR": "#FF007A",
        "SUCCESS": "#00FF9F",
        "WARNING": "#FFD600",
        "_style": "cyber",
    },
    "tech_noir": {
        "BG": "#1A1A1A",
        "CARD": "#2C2C2E",
        "ACCENT": "#39FF14",
        "ACCENT_LIGHT": "#FF3D00",
        "TEXT": "#E5E5E5",
        "MUTED": "#6E6E70",
        "SEMI_MUTED": "#A8A8AA",
        "ERROR": "#FF3D00",
        "SUCCESS": "#39FF14",
        "WARNING": "#00BFAE",
        "_style": "cyber",
    },
    "synthwave": {
        "BG": "#070F34",
        "CARD": "#141A48",
        "ACCENT": "#FF1493",
        "ACCENT_LIGHT": "#6F00FF",
        "TEXT": "#F0E9FF",
        "MUTED": "#5A6288",
        "SEMI_MUTED": "#9DA4C8",
        "ERROR": "#FF1493",
        "SUCCESS": "#00BFFF",
        "WARNING": "#FF6700",
        "_style": "cyber",
    },
    "cyber_ui": {
        "BG": "#000000",
        "CARD": "#141414",
        "ACCENT": "#FCEE0C",
        "ACCENT_LIGHT": "#C5003C",
        "TEXT": "#F5F5F5",
        "MUTED": "#6B6B6B",
        "SEMI_MUTED": "#B0B0B0",
        "ERROR": "#C5003C",
        "SUCCESS": "#00FF9F",
        "WARNING": "#FCEE0C",
        "_style": "cyber",
    },
    "chrome": {
        "BG": "#2A3038",
        "CARD": "#4A5568",
        "ACCENT": "#7DF9FF",
        "ACCENT_LIGHT": "#BD00FF",
        "TEXT": "#F0F4F8",
        "MUTED": "#8A95A5",
        "SEMI_MUTED": "#C4CCD8",
        "ERROR": "#BD00FF",
        "SUCCESS": "#7DF9FF",
        "WARNING": "#F6FF75",
        "_style": "cyber",
    },
}

DEFAULT_THEME = "midnight"

# 旧主题名 → 新主题名映射（用于兼容旧配置文件）
THEME_ALIASES = {
    "cyberpunk": "cp1",
    "cyberpunk_v1": "cp2",
}

# 主题内部名 → 菜单显示名
THEME_DISPLAY = {
    "midnight": "午夜蓝调",
    "cp1": "极夜青",
    "cp2": "夜幕残阳",
    "neon_dreams": "霓虹之梦",
    "tech_noir": "科技暗夜",
    "synthwave": "合成器之夜",
    "cyber_ui": "绚丽极客",
    "chrome": "机械全息",
}


def theme_display_name(name):
    """主题内部名转显示名，无映射则返回原名"""
    return THEME_DISPLAY.get(name, name)


class Theme:
    BG = THEMES[DEFAULT_THEME]["BG"]
    CARD = THEMES[DEFAULT_THEME]["CARD"]
    ACCENT = THEMES[DEFAULT_THEME]["ACCENT"]
    ACCENT_LIGHT = THEMES[DEFAULT_THEME]["ACCENT_LIGHT"]
    TEXT = THEMES[DEFAULT_THEME]["TEXT"]
    MUTED = THEMES[DEFAULT_THEME]["MUTED"]
    SEMI_MUTED = THEMES[DEFAULT_THEME]["SEMI_MUTED"]
    ERROR = THEMES[DEFAULT_THEME]["ERROR"]
    SUCCESS = THEMES[DEFAULT_THEME]["SUCCESS"]
    WARNING = THEMES[DEFAULT_THEME]["WARNING"]
    STYLE = THEMES[DEFAULT_THEME].get("_style", "flat")


def apply_theme(name):
    """将指定主题色值应用到 Theme 类属性"""
    name = THEME_ALIASES.get(name, name)
    t = THEMES.get(name) or THEMES[DEFAULT_THEME]
    for k, v in t.items():
        if k.startswith("_"):
            continue
        setattr(Theme, k, v)
    setattr(Theme, "STYLE", t.get("_style", "flat"))


AGUI_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".agui")
AGUI_CONFIG_PATH = os.path.join(AGUI_CONFIG_DIR, "agui_config.json")
LEGACY_HISTORY_PATH = os.path.join(AGUI_CONFIG_DIR, "save_paths.json")


def load_config():
    """读取 agui_config.json，首次自动迁移旧 save_paths.json"""
    try:
        if os.path.exists(AGUI_CONFIG_PATH):
            with open(AGUI_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _t = data.get("theme")
                if isinstance(_t, str) and _t in THEME_ALIASES:
                    data["theme"] = THEME_ALIASES[_t]
                    try:
                        with open(AGUI_CONFIG_PATH, "w", encoding="utf-8", newline="") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                return data
    except Exception:
        pass
    result = {"theme": DEFAULT_THEME, "save_paths": {"recent": [], "starred": []}}
    try:
        if os.path.exists(LEGACY_HISTORY_PATH):
            with open(LEGACY_HISTORY_PATH, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict):
                result["save_paths"] = {
                    "recent": list(old.get("recent", []))[:20],
                    "starred": list(old.get("starred", [])),
                }
    except Exception:
        pass
    return result


def save_config(cfg):
    """写入 agui_config.json"""
    try:
        os.makedirs(AGUI_CONFIG_DIR, exist_ok=True)
        with open(AGUI_CONFIG_PATH, "w", encoding="utf-8", newline="") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        sys.stderr.write("[agui] save_config failed: " + str(e) + chr(10))


DEFAULT_PREFERENCES = {
    "split": 5,
    "path": "",
    "ua": "",
    "referer": "",
    "auto_referer": False,
    "max_conn": 16,
    "file_allocation": "falloc",
    "rpc_port": 16800,
    "min_split_size": "1M",
    "speed_limit": "0",
    "log_enabled": True,
    "log_path": "",
    "advanced": False,
}


def load_preferences():
    """读取 preferences 子键，缺失字段用默认值补齐"""
    try:
        cfg = load_config()
        prefs = cfg.get("preferences") or {}
        result = dict(DEFAULT_PREFERENCES)
        if isinstance(prefs, dict):
            for k, v in prefs.items():
                if k in result:
                    result[k] = v
        return result
    except Exception:
        return dict(DEFAULT_PREFERENCES)


def save_preferences(prefs):
    """写 preferences 到 agui_config.json，保留其他键"""
    try:
        cfg = load_config()
        cfg["preferences"] = dict(prefs) if isinstance(prefs, dict) else {}
        save_config(cfg)
    except Exception as e:
        sys.stderr.write("[agui] save_preferences failed: " + str(e) + chr(10))

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
    "--callback-port",
    "--http-port",
    "-silent",
    "--silent",
    "--metalink",
    "--no-add",
    "-a",
    "--aria2c-path",
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