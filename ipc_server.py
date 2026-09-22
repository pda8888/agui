#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程间通信 - 单实例管理"""
import time
import socket
import json
# import pickle
from config import IPC_PORT

def try_send_to_main_instance(args_list, max_retries=1, retry_delay=0.2, timeout=2.0):
    """尝试将参数发送给已运行的主实例，并返回响应字符串，失败返回 None"""
    for i in range(max_retries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", IPC_PORT))
            # data = pickle.dumps(args_list)
            data = json.dumps(args_list).encode("utf-8")
            s.sendall(data)
            # 等待响应
            resp = s.recv(1024)
            s.close()
            return resp.decode("utf-8").strip()
        except ConnectionRefusedError:
            return None
        except (socket.timeout, OSError):
            time.sleep(retry_delay)
            continue
    return None

def try_bind_ipc_port():
    """尝试绑定IPC端口,判断是否为主实例"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", IPC_PORT))
        return True, sock
    except OSError:
        return False, None

class IPCServer:
    """IPC服务器,接收其他实例的任务，支持返回结果"""
    
    def __init__(self, socket_obj, handler, log_path=None):
        """
        socket_obj: 已绑定的socket对象
        handler: 数据处理函数，接收参数列表，返回 bytes 或 None
        log_path: 可选日志路径，服务器异常退出时写入
        """
        self.socket = socket_obj
        self.handler = handler
        self.running = True
        self.log_path = log_path
    
    def start(self):
        """启动监听(在独立线程中调用)"""
        if not self.socket:
            return
        
        try:
            self.socket.listen(5)
            while self.running:
                try:
                    client, _ = self.socket.accept()
                    data = client.recv(4096)
                    if data:
                        try:
                            args = json.loads(data.decode("utf-8"))
                        except Exception:
                            client.close()
                            continue
                        if self.handler:
                            reply = self.handler(args)
                            if reply:
                                client.sendall(reply)
                    client.close()
                except Exception:
                    pass
        except Exception as e:
            from utils import log_write
            log_write(self.log_path, f"IPC server stopped: {e}")
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
