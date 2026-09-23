#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命令行参数解析"""
from config import RPC_OPTION_MAPPING
from utils import parse_custom_t_arg

def parse_args(argv):
    """解析命令行参数"""
    title, info_text, log_file = "下载", "", None
    countdown = None
    global_countdown = None
    position = None
    retry_count = 3           # 默认重试次数
    retry_interval = 2        # 默认重试间隔（秒）
    retry_exhausted_timeout = 10
    query_gid = None
    kill_gid = None
    callback_port = None
    http_port = None
    silent = False
    no_add = False
    verify_hash = None
    marquee_interval = 1.5
    marquee_mode = "scroll"
    marquee_speed = 0.06
    aria2_args = []
    auto_referer = False
    
    i = 0
    while i < len(argv):
        a = argv[i]
        
        if a == "--title" and i + 1 < len(argv):
            title, info_text = parse_custom_t_arg(argv[i + 1])
            i += 2
        elif a.startswith("--title="):
            title, info_text = parse_custom_t_arg(a.split("=", 1)[1])
            i += 1
        
        elif a == "--countdown" and i + 1 < len(argv):
            try:
                countdown = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--countdown="):
            try:
                countdown = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--global-countdown" and i + 1 < len(argv):
            try:
                global_countdown = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--global-countdown="):
            try:
                global_countdown = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        
        elif a == "--log-to" and i + 1 < len(argv):
            log_file = argv[i + 1]
            i += 2
        elif a.startswith("--log-to="):
            log_file = a.split("=", 1)[1]
            i += 1
        
        
        elif a == "--position" and i + 1 < len(argv):
            val = argv[i + 1]
            try:
                parts = val.split(",")
                if len(parts) == 2:
                    position = (int(parts[0]), int(parts[1]))
            except:
                pass
            i += 2
        elif a.startswith("--position="):
            val = a.split("=", 1)[1]
            try:
                parts = val.split(",")
                if len(parts) == 2:
                    position = (int(parts[0]), int(parts[1]))
            except:
                pass
            i += 1
        
        elif a == "--auto-referer":
            auto_referer = True
            i += 1
            
        elif a == "--retry" and i + 1 < len(argv):
            try:
                retry_count = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--retry="):
            try:
                retry_count = int(a.split("=", 1)[1])
            except:
                pass
            i += 1

        elif a == "--retry-interval" and i + 1 < len(argv):
            try:
                retry_interval = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--retry-interval="):
            try:
                retry_interval = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--retry-exhausted-timeout" and i + 1 < len(argv):
            try:
                retry_exhausted_timeout = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--retry-exhausted-timeout="):
            try:
                retry_exhausted_timeout = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--query" and i + 1 < len(argv):
            query_gid = argv[i + 1]
            i += 2
        elif a.startswith("--query="):
            query_gid = a.split("=", 1)[1]
            i += 1
        elif a == "--kill" and i + 1 < len(argv):
            kill_gid = argv[i + 1]
            i += 2
        elif a.startswith("--kill="):
            kill_gid = a.split("=", 1)[1]
            i += 1
        elif a == "--callback-port" and i + 1 < len(argv):
            try:
                callback_port = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--callback-port="):
            try:
                callback_port = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--http-port" and i + 1 < len(argv):
            try:
                http_port = int(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--http-port="):
            try:
                http_port = int(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--marquee-mode" and i + 1 < len(argv):
            marquee_mode = argv[i + 1].strip().lower()
            i += 2
        elif a.startswith("--marquee-mode="):
            marquee_mode = a.split("=", 1)[1].strip().lower()
            i += 1
        elif a == "--marquee-speed" and i + 1 < len(argv):
            try:
                marquee_speed = float(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--marquee-speed="):
            try:
                marquee_speed = float(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--marquee-interval" and i + 1 < len(argv):
            try:
                marquee_interval = float(argv[i + 1])
            except:
                pass
            i += 2
        elif a.startswith("--marquee-interval="):
            try:
                marquee_interval = float(a.split("=", 1)[1])
            except:
                pass
            i += 1
        elif a == "--verify-hash" and i + 1 < len(argv):
            verify_hash = argv[i + 1]
            i += 2
        elif a.startswith("--verify-hash="):
            verify_hash = a.split("=", 1)[1]
            i += 1
        elif a in ("-silent", "--silent"):
            silent = True
            i += 1
        elif a == "--no-add":
            no_add = True
            i += 1
            
        else:
            aria2_args.append(a)
            i += 1
    
    return {
        "title": title,
        "info_text": info_text,
        "countdown": countdown,
        "global_countdown": global_countdown,
        "log_file": log_file,
        "aria2_args": aria2_args,
        "position": position,
        "auto_referer": auto_referer,
        "retry_count": retry_count,
        "retry_interval": retry_interval,
        "retry_exhausted_timeout": retry_exhausted_timeout,
        "query_gid": query_gid,
        "kill_gid": kill_gid,
        "callback_port": callback_port,
        "http_port": http_port,
        "silent": silent,
        "no_add": no_add,
        "verify_hash": verify_hash,
        "marquee_interval": marquee_interval,
        "marquee_mode": marquee_mode,
        "marquee_speed": marquee_speed,
    }

def get_task_options(args_list):
    """从命令行参数中提取RPC选项"""
    opts = {}
    
    skip_next = False
    for i, arg in enumerate(args_list):
        if skip_next:
            skip_next = False
            continue
        
        key = None
        val = None
        
        if "=" in arg:
            k, v = arg.split("=", 1)
            if k in RPC_OPTION_MAPPING:
                key = RPC_OPTION_MAPPING[k]
                val = v
        else:
            if arg in RPC_OPTION_MAPPING:
                if i + 1 < len(args_list):
                    key = RPC_OPTION_MAPPING[arg]
                    val = args_list[i + 1]
                    skip_next = True
        
        if key and val:
            _v = val.strip().strip('"').strip("'")
            if key == "header":
                if not isinstance(opts.get("header"), list):
                    opts["header"] = []
                opts["header"].append(_v)
            else:
                opts[key] = _v
    
    return opts
