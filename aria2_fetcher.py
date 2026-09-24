#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aria2c.exe 按需下载器"""
import io
import os
import zipfile
import tempfile
import urllib.request

ARIA2_FILENAME = "aria2c.exe"

_RELEASE_URL = (
    "https://github.com/aria2/aria2/releases/download/release-1.37.0/"
    "aria2-1.37.0-win-64bit-build1.zip"
)

PROXIES = [
    "https://gh-proxy.com/",
    "https://hk.gh-proxy.com/",
    "https://cdn.gh-proxy.com/",
]


def default_target_dir():
    """返回默认目标目录：%TEMP%（Windows）或系统临时目录"""
    t = os.environ.get("TEMP") or ""
    if t and os.path.isdir(t):
        return t
    return tempfile.gettempdir()


def fetch_aria2c(target_dir=None, force=False, progress_cb=None, timeout=30):
    """下载并解压 aria2c.exe 到 target_dir。

    target_dir: 目标目录，默认 %TEMP%
    force: True 时即使已存在也重新下载覆盖
    progress_cb: 可选回调 (stage, done, total)。stage = "downloading" / "extracting"
    timeout: 单个 URL 的超时秒数

    返回 exe 路径，全部失败返回 None。
    """
    if target_dir is None:
        target_dir = default_target_dir()
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception:
        return None

    exe_path = os.path.join(target_dir, ARIA2_FILENAME)
    if os.path.exists(exe_path) and not force:
        return exe_path

    for proxy in PROXIES:
        url = proxy + _RELEASE_URL
        data = _download(url, progress_cb, timeout)
        if data is None:
            continue
        if _extract(data, exe_path, progress_cb):
            return exe_path
    return None


def _download(url, progress_cb, timeout):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AGUI/1.5"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            buf = io.BytesIO()
            done = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                if progress_cb:
                    try:
                        progress_cb("downloading", done, total)
                    except Exception:
                        pass
            return buf.getvalue()
    except Exception:
        return None


def _extract(zip_data, exe_path, progress_cb):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            target = None
            for n in z.namelist():
                if n.lower().endswith(ARIA2_FILENAME):
                    target = n
                    break
            if target is None:
                return False
            with z.open(target) as src, open(exe_path, "wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
        if progress_cb:
            try:
                progress_cb("extracting", 1, 1)
            except Exception:
                pass
        return True
    except Exception:
        return False
