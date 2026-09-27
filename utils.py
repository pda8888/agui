#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用工具函数"""
import os
import sys
import re
import json
import socket
import threading
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote
import urllib.request
import urllib.parse

# === 格式化工具 ===
def nice_size(b):
    """格式化文件大小"""
    b = int(b or 0)
    if b < 1024:
        return f"{b} B"
    if b < 1024**2:
        return f"{b / 1024:.2f} KB"
    if b < 1024**3:
        return f"{b / 1024**2:.2f} MB"
    return f"{b / 1024**3:.2f} GB"

def nice_duration(seconds):
    """格式化时长: 00d 00:00:00"""
    if seconds is None or seconds < 0:
        return "--:--"
    
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    
    if d > 0:
        return f"{d}d {h:02d}:{m:02d}:{s:02d}"
    elif h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

# === 路径工具 ===
def get_long_path_win32(path):
    """将Windows短路径转换为长路径"""
    if sys.platform != "win32":
        return os.path.abspath(path)
    
    try:
        if not os.path.exists(path):
            return os.path.abspath(path)
        
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        GetLongPathNameW = ctypes.windll.kernel32.GetLongPathNameW
        res = GetLongPathNameW(str(path), buf, 1024)
        
        if res == 0 or res > 1024:
            return os.path.abspath(path)
        return buf.value
    except:
        return os.path.abspath(path)

# === 网络工具 ===
def find_free_port(start_port=16800, max_port=17000):
    """在指定范围内寻找可用端口"""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    
    # 全部占用则返回随机端口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def find_user_rpc_port(args_list):
    """从参数列表中提取用户指定的RPC端口"""
    for i, arg in enumerate(args_list):
        if arg == "--rpc-listen-port" and i + 1 < len(args_list):
            try:
                return int(args_list[i + 1])
            except ValueError:
                return None
        if arg.startswith("--rpc-listen-port="):
            try:
                return int(arg.split("=", 1)[1])
            except (ValueError, IndexError):
                return None
    return None

# === 参数解析工具 ===
def parse_custom_t_arg(val: str):
    """解析自定义标题参数 (格式: title|info)"""
    parts = val.split("|", 1)
    title = parts[0] if parts else "下载"
    info_text = ""
    if len(parts) > 1:
        try:
            info_text = json.loads(f'"{parts[1]}"')
        except:
            info_text = parts[1]
    return title, info_text

def extract_urls_and_out(aria2_args):
    """从参数中提取URL和输出文件名"""
    urls, out_name = [], None
    url_pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", re.IGNORECASE)
    
    # 查找输出文件名
    for idx, a in enumerate(aria2_args):
        if a in ("-o", "--out") and idx + 1 < len(aria2_args):
            out_name = aria2_args[idx + 1]
            break
    
    # 提取URL
    for a in aria2_args:
        clean_a = a.strip().strip('"').strip("'")
        if not clean_a:
            continue
        
        low_a = clean_a.lower()
        if (low_a.startswith("magnet:")
                or low_a.endswith(".torrent")
                or low_a.endswith(".meta4")
                or low_a.endswith(".metalink")):
            urls.append(clean_a)
        elif url_pattern.match(clean_a):
            urls.append(clean_a)
    

    
    return urls, out_name

def extract_referer(url):
    """从URL中提取Referer"""
    try:
        parsed = urlparse(url)
        if parsed.scheme.startswith("http"):
            port = parsed.port
            if port and port not in (80, 443):
                return f"{parsed.scheme}://{parsed.hostname}:{port}"
            return f"{parsed.scheme}://{parsed.hostname}"
        return ""
    except:
        return ""

# === 日志工具 ===
def ensure_log_file(path):
    """确保日志文件存在（启动时调用，仅创建空文件）"""
    if not path:
        return
    try:
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(path):
            open(path, "a", encoding="utf-8").close()
    except Exception:
        pass


def log_write(path, text):
    """写入日志"""
    if not path:
        return
    try:
        import time
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except:
        pass

_TRANSLATE_CACHE = {}
_TRANSLATE_CACHE_LOCK = threading.Lock()
_TRANSLATE_CACHE_MAX = 512


def translate_error_online(text):
    """调用 MyMemory API 将英文翻译为中文，失败返回原文（带内存缓存）"""
    if not text or not text.strip():
        return text
    
    # 检测是否包含中文字符，如果已有中文则不翻译
    if any('\u4e00' <= ch <= '\u9fff' for ch in text):
        return text
    
    with _TRANSLATE_CACHE_LOCK:
        cached = _TRANSLATE_CACHE.get(text)
    if cached is not None:
        return cached
    
    try:
        base_url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({
            'q': text,
            'langpair': 'en|zh-CN'
        })
        url = f"{base_url}?{params}"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'AGUI/1.4'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('responseStatus') == 200:
                translated = data['responseData']['translatedText']
                with _TRANSLATE_CACHE_LOCK:
                    if len(_TRANSLATE_CACHE) >= _TRANSLATE_CACHE_MAX:
                        _TRANSLATE_CACHE.clear()
                    _TRANSLATE_CACHE[text] = translated
                return translated
    except Exception:
        pass
    
    return text  # 任何异常都返回原文


# === Hash 校验工具 ===
class HashVerifier:
    """独立 hash 校验器，用于 aria2c 之外的二次校验"""
    ALGO_MAP = {
        "md5": "md5",
        "sha-1": "sha1", "sha1": "sha1",
        "sha-256": "sha256", "sha256": "sha256",
        "sha-512": "sha512", "sha512": "sha512",
    }

    @staticmethod
    def normalize_algo(algo):
        if not algo:
            return None
        return HashVerifier.ALGO_MAP.get(str(algo).lower().strip())

    @staticmethod
    def compute(path, algo="md5", chunk_size=1024 * 1024, progress_cb=None, cancel_check=None):
        algo_norm = HashVerifier.normalize_algo(algo)
        if not algo_norm:
            raise ValueError(f"不支持的 hash 算法: {algo}")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        h = hashlib.new(algo_norm)
        total = os.path.getsize(path)
        done = 0
        with open(path, "rb") as f:
            while True:
                if cancel_check and cancel_check():
                    return None
                buf = f.read(chunk_size)
                if not buf:
                    break
                h.update(buf)
                done += len(buf)
                if progress_cb:
                    try:
                        progress_cb(done, total)
                    except Exception:
                        pass
        return h.hexdigest()

    @staticmethod
    def verify(path, expected_hex, algo="md5", **kwargs):
        if not expected_hex:
            return (False, None)
        actual = HashVerifier.compute(path, algo, **kwargs)
        if actual is None:
            return (False, None)
        return (actual.lower() == str(expected_hex).lower().strip(), actual)


_METALINK_NS = "{urn:ietf:params:xml:ns:metalink}"


def _parse_metalink_root(root):
    result = {}
    for f in root.findall(f"{_METALINK_NS}file"):
        name = f.get("name") or ""
        hashes = []
        for h in f.findall(f"{_METALINK_NS}verification/{_METALINK_NS}hash"):
            algo = h.get("type")
            hexval = (h.text or "").strip()
            if algo and hexval:
                hashes.append((algo, hexval))
        result[name] = hashes
    return result


def parse_metalink_hashes(path):
    """解析 metalink 文件，返回 {file_name: [(algo, hex), ...]}"""
    try:
        tree = ET.parse(path)
    except Exception:
        return {}
    return _parse_metalink_root(tree.getroot())


def parse_metalink_hashes_from_b64(b64_str):
    """从 base64 编码的 metalink 内容解析 hash，返回 {file_name: [(algo, hex), ...]}"""
    try:
        import base64 as _b64
        raw = _b64.b64decode(b64_str)
        root = ET.fromstring(raw)
    except Exception:
        return {}
    return _parse_metalink_root(root)

def _bdecode(data):
    """最小 bencode 解码器，返回 (value, next_pos)"""
    def _int(i):
        j = data.index(b"e", i)
        return int(data[i:j]), j + 1
    def _bytes(i):
        j = data.index(b":", i)
        n = int(data[i:j])
        s = i + (j - i) + 1
        return data[s:s + n], s + n
    def _list(i):
        i += 1
        out = []
        while data[i:i + 1] != b"e":
            v, i = _decode_at(i)
            out.append(v)
        return out, i + 1
    def _dict(i):
        i += 1
        out = {}
        while data[i:i + 1] != b"e":
            k, i = _bytes(i)
            v, i = _decode_at(i)
            out[k] = v
        return out, i + 1
    def _decode_at(i):
        ch = data[i:i + 1]
        if ch == b"i":
            return _int(i + 1)
        if ch == b"l":
            return _list(i)
        if ch == b"d":
            return _dict(i)
        return _bytes(i)
    v, _ = _decode_at(0)
    return v

def _bdec_str(b):
    """bencode 字节串转 str，UTF-8 → GBK → latin-1"""
    if isinstance(b, str):
        return b
    if not isinstance(b, (bytes, bytearray)):
        return str(b)
    for enc in ("utf-8", "gbk"):
        try:
            return bytes(b).decode(enc)
        except Exception:
            continue
    return bytes(b).decode("latin-1", errors="replace")

_DOWNLOADED_TORRENT_HASHES = set()

def register_downloaded_torrent(h):
    if h:
        _DOWNLOADED_TORRENT_HASHES.add(h)

def is_torrent_downloaded(h):
    return bool(h) and h in _DOWNLOADED_TORRENT_HASHES

def _skip_bencode_value(data, i):
    ch = data[i:i + 1]
    if ch == b"i":
        j = data.index(b"e", i)
        return j + 1
    if ch == b"l":
        i += 1
        while data[i:i + 1] != b"e":
            i = _skip_bencode_value(data, i)
        return i + 1
    if ch == b"d":
        i += 1
        while data[i:i + 1] != b"e":
            j = data.index(b":", i)
            klen = int(data[i:j])
            i = j + 1 + klen
            i = _skip_bencode_value(data, i)
        return i + 1
    j = data.index(b":", i)
    n = int(data[i:j])
    return j + 1 + n

def torrent_info_hash(path):
    """返回 .torrent 的 info 段 SHA1（40 hex）；失败返回 None"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data[0:1] != b"d":
            return None
        i = 1
        while data[i:i + 1] != b"e":
            j = data.index(b":", i)
            klen = int(data[i:j])
            k = data[j + 1:j + 1 + klen]
            i = j + 1 + klen
            v_start = i
            i = _skip_bencode_value(data, i)
            if k == b"info":
                return hashlib.sha1(data[v_start:i]).hexdigest()
        return None
    except Exception:
        return None

def parse_torrent_files(path):
    """解析 .torrent 文件，返回 {name, files:[{index,path,length}], total_length}
    单文件种子：files 只有 1 项（path=name）；多文件：path 为相对路径拼接。
    index 从 1 开始，对应 aria2 select-file 序号。
    失败返回 None。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        meta = _bdecode(data)
        if not isinstance(meta, dict):
            return None
        info = meta.get(b"info")
        if not isinstance(info, dict):
            return None
        name_raw = info.get(b"name.utf-8") or info.get(b"name") or b""
        name = _bdec_str(name_raw)
        files_field = info.get(b"files")
        out_files = []
        total = 0
        if isinstance(files_field, list):
            for idx, item in enumerate(files_field, 1):
                if not isinstance(item, dict):
                    continue
                length = int(item.get(b"length", 0) or 0)
                pth = item.get(b"path.utf-8") or item.get(b"path") or []
                parts = [_bdec_str(p) for p in pth] if isinstance(pth, list) else []
                rel = "/".join(parts) if parts else name
                out_files.append({"index": idx, "path": rel, "length": length})
                total += length
        else:
            length = int(info.get(b"length", 0) or 0)
            out_files.append({"index": 1, "path": name, "length": length})
            total = length
        return {"name": name, "files": out_files, "total_length": total}
    except Exception:
        return None

