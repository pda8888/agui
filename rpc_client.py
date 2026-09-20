#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aria2 RPC客户端封装"""
import json
import urllib.request
# import time

# 全局RPC URL (由main.py设置)
RPC_URL = None

def set_rpc_url(url):
    """设置RPC URL"""
    global RPC_URL
    RPC_URL = url

def rpc_request(method, params=None, timeout=2):
    """发送RPC请求"""
    if not RPC_URL:
        return None
    
    payload = {
        "jsonrpc": "2.0",
        "id": "agui",
        "method": method,
        "params": params or []
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL, data=data, 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except:
        return None

class Aria2RPC:
    """Aria2 RPC操作封装"""
    
    def __init__(self, secret=None):
        self.secret = secret
    
    def _call(self, method, params=None):
        """带token的RPC调用"""
        if self.secret:
            params = [f"token:{self.secret}"] + (params or [])
        return rpc_request(method, params)
    
    def get_version(self):
        """获取aria2版本"""
        return self._call("aria2.getVersion")
    
    def tell_status(self, gid, keys=None):
        """查询任务状态"""
        params = [gid]
        if keys:
            params.append(keys)
        return self._call("aria2.tellStatus", params)
    
    def pause(self, gid):
        """暂停任务"""
        return self._call("aria2.pause", [gid])
    
    def force_pause(self, gid):
        """强制暂停任务"""
        return self._call("aria2.forcePause", [gid])
    
    def unpause(self, gid):
        """恢复任务"""
        return self._call("aria2.unpause", [gid])
    
    def remove(self, gid):
        """移除任务"""
        return self._call("aria2.remove", [gid])
    
    def force_remove(self, gid):
        """强制移除任务"""
        return self._call("aria2.forceRemove", [gid])
    
    def remove_download_result(self, gid):
        """移除下载结果"""
        return self._call("aria2.removeDownloadResult", [gid])
    
    def add_uri(self, uris, options=None):
        """添加URI下载"""
        params = [uris]
        if options:
            params.append(options)
        return self._call("aria2.addUri", params)
    
    def add_torrent(self, torrent_base64, uris=None, options=None):
        """添加种子下载"""
        params = [torrent_base64]
        if uris:
            params.append(uris)
        else:
            params.append([])
        if options:
            params.append(options)
        return self._call("aria2.addTorrent", params)

    def add_metalink(self, metalink_base64, options=None):
        """添加 Metalink 下载（本地 .meta4 / .metalink 文件，base64 编码）"""
        params = [metalink_base64]
        if options:
            params.append(options)
        return self._call("aria2.addMetalink", params)
    
    def shutdown(self):
        return self._call("aria2.shutdown")
        
    def retry(self, gid, uris=None, options=None):
        if uris is not None:
            nr = self.add_uri(uris, options)
            if not nr or "result" not in nr:
                return None
            self.force_remove(gid)
            self.remove_download_result(gid)
            return nr
        res = self.tell_status(gid, ["files", "dir"])
        if not res or "result" not in res:
            return None
        result = res["result"]
        files = result.get("files", [])
        if not files:
            return None
        uris = []
        for f in files:
            for u in f.get("uris", []):
                uri = u.get("uri", "")
                if uri:
                    uris.append(uri)
        if not uris:
            return None
        opts = {"dir": result["dir"]} if result.get("dir") else {}
        new_res = self.add_uri(uris, opts if opts else None)
        if not new_res or "result" not in new_res:
            return None
        self.force_remove(gid)
        self.remove_download_result(gid)
        return new_res