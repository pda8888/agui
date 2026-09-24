#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aria2进程管理和防火墙规则"""
import os
import sys
import time
import subprocess
from config import ARIA2_PATH, get_default_aria2_args, TASK_ARGS_BLACKLIST, UI_ARG_PREFIXES
from utils import log_write

# === Windows进程管理 ===
g_job_handle = None

if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]
        
        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", ctypes.c_void_p),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]
        
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
    except (ImportError, AttributeError):
        pass

def setup_job_object():
    """创建Windows Job Object"""
    if sys.platform != "win32":
        return
    global g_job_handle
    g_job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ctypes.windll.kernel32.SetInformationJobObject(
        g_job_handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )

def assign_process_to_job(proc_pid):
    """将进程分配到Job Object"""
    if sys.platform != "win32" or g_job_handle is None:
        return
    h_process = ctypes.windll.kernel32.OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc_pid
    )
    if h_process:
        ctypes.windll.kernel32.AssignProcessToJobObject(g_job_handle, h_process)
        ctypes.windll.kernel32.CloseHandle(h_process)

# === 防火墙管理 ===
def update_firewall_rules(aria2_path=None):
    """添加防火墙规则。返回 True 表示成功或不需要，False 表示失败/权限不足
    aria2_path: None 时用 config.ARIA2_PATH（兼容旧调用）"""
    if sys.platform != "win32":
        return True
    
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return False
    except Exception:
        return False
    
    try:
        rule_name = "aria2c_for_agui"
        _ap = aria2_path if aria2_path else ARIA2_PATH
        exe_path = os.path.abspath(_ap).lower().replace("/", "\\")
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # 删除旧规则
        cmd_del = f'netsh advfirewall firewall delete rule name="{rule_name}"'
        subprocess.run(cmd_del, shell=True, stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, startupinfo=startupinfo, timeout=5)
        
        # 添加入站规则
        cmd_in = (f'netsh advfirewall firewall add rule name="{rule_name}" '
                 f'dir=in action=allow program="{exe_path}" enable=yes '
                 f'profile=any protocol=any edge=yes')
        subprocess.run(cmd_in, shell=True, capture_output=True, 
                      startupinfo=startupinfo, timeout=5)
        
        # 添加出站规则
        cmd_out = (f'netsh advfirewall firewall add rule name="{rule_name}" '
                  f'dir=out action=allow program="{exe_path}" enable=yes '
                  f'profile=any protocol=any')
        subprocess.run(cmd_out, shell=True, capture_output=True, 
                      startupinfo=startupinfo, timeout=5)
        return True
    except Exception:
        return False

def cleanup_firewall_rules():
    """清理防火墙规则"""
    if sys.platform != "win32":
        return
    
    try:
        rule_name = "aria2c_for_agui"
        cmd = f'netsh advfirewall firewall delete rule name="{rule_name}"'
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, startupinfo=startupinfo)
    except Exception:
        pass

# === Aria2进程管理 ===
def build_aria2_command(aria2_args, aria2_path=None, logpath=None):
    """构建aria2c启动命令"""
    _ap = aria2_path if aria2_path else ARIA2_PATH
    if not os.path.exists(_ap):
        raise FileNotFoundError(f"aria2c not found at {_ap}")
    
    base_path = os.path.dirname(_ap)
    defaults = get_default_aria2_args(base_path)
    
    # 收集用户参数
    user_arg_keys = set()
    i = 0
    while i < len(aria2_args):
        key = aria2_args[i].split("=", 1)[0]
        user_arg_keys.add(key)
        if aria2_args[i].startswith("--") and "=" not in aria2_args[i]:
            if i + 1 < len(aria2_args) and not aria2_args[i + 1].startswith("-"):
                i += 2
                continue
        i += 1
    
    # 构建命令
    cmd = [_ap]
    for key, value in defaults.items():
        if key not in user_arg_keys:
            cmd.append(f"{key}={value}")
    
        # 过滤用户参数
    skip_next = False
    for i, arg in enumerate(aria2_args):
        if skip_next:
            skip_next = False
            continue
        
        low_arg = arg.lower()
        
        # 跳过URL/Magnet/Torrent/Metalink
        if ("://" in low_arg
                or low_arg.startswith("magnet:")
                or low_arg.endswith(".torrent")
                or low_arg.endswith(".meta4")
                or low_arg.endswith(".metalink")):
            continue
        
        # 跳过UI参数
        is_ui_arg = arg == "--no-cancel"
        if not is_ui_arg:
            for prefix in UI_ARG_PREFIXES:
                if low_arg == prefix or low_arg.startswith(prefix + "="):
                    is_ui_arg = True
                    if low_arg == prefix and i + 1 < len(aria2_args):
                        if not aria2_args[i + 1].startswith("--"):
                            skip_next = True
                    break
        
        if is_ui_arg:
            continue
        
        # 跳过任务级参数
        is_task_arg = False
        for bad_key in TASK_ARGS_BLACKLIST:
            if low_arg.startswith(bad_key + "=") or low_arg == bad_key:
                is_task_arg = True
                if low_arg == bad_key and i + 1 < len(aria2_args):
                    if not aria2_args[i + 1].startswith("--"):
                        skip_next = True
                break
        
        if not is_task_arg:
            cmd.append(arg)
    
    log_write(logpath, f"Starting aria2c: {' '.join(cmd)}")
    return cmd

def start_aria2c(aria2_args, aria2_path=None, logpath=None):
    # import time as _time
    """启动aria2c进程"""
    from rpc_client import rpc_request
    from config import RPC_STARTUP_WAIT, RPC_STARTUP_RETRIES
    
    cmd = build_aria2_command(aria2_args, aria2_path, logpath)
    
    proc, stderr_output = None, b""
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, 
                               stderr=subprocess.PIPE, creationflags=creationflags)
        if proc and proc.pid:
            assign_process_to_job(proc.pid)
    except Exception as e:
        log_write(logpath, f"Failed to start aria2c: {e}")
        raise
    
    # 等待RPC就绪
    # ready = False
    # time.sleep(0.5)
    
    # 等待RPC就绪
    ready = False
    # _t_sleep_start = _time.time()
    time.sleep(0.5)
    # _t_rpc_loop_start = _time.time()
    
    if proc.poll() is not None:
        _, stderr_output = proc.communicate()
    else:
        for _ in range(RPC_STARTUP_RETRIES):
            if proc.poll() is not None:
                _, stderr_output = proc.communicate()
                break
            if rpc_request("aria2.getVersion"):
                ready = True
                break
            time.sleep(RPC_STARTUP_WAIT)
    
    return proc, ready, stderr_output

def stop_aria2c(proc, logpath=None):
    """停止aria2c进程并清理"""
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            log_write(logpath, "aria2c stopped")
        except Exception as e:
            log_write(logpath, f"Failed to stop aria2c: {e}")
    
    cleanup_firewall_rules()