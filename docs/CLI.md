# 老王的小拖船 V1.4 CLI 调用手册

## 一、概览

agui 提供 3 种对外接口，主程序推荐使用命令行 + 回调端口。

| 接口 | 适用 | 是否需要主程序监听端口 | 调用复杂度 |
|---|---|---|---|
| 命令行 + --callback-port | 主程序同步调用 | 是（本机 TCP） | 低 |
| HTTP API（--http-port） | 主程序长连 | 否 | 中 |
| IPC 内部转发 | 用户手动启动多次 | — | 不对外，自动 |

单实例机制：第一次启动的进程占用 IPC 端口成为主实例；后续启动的进程自动把命令行转发给主实例，自己退出。所以主程序可以放心每次 subprocess.Popen 一个 agui。

---

## 二、命令行参数表

### 2.1 自定义参数（agui 消费，不传给 aria2c）

| 参数 | 类型 | 说明 |
|---|---|---|
| --title "标题\|说明" | string | 窗口标题和卡片上方黄字标题。`\|` 后为说明文本 |
| --countdown N | int | 任务级倒计时。完成后 N 秒删卡。-1 永久保留（默认），0 立即删卡 |
| --global-countdown N | int | 全局倒计时。设置后覆盖所有未钉死任务。任务自带 --countdown 时优先级更高 |
| --metalink=<b64> | string | metalink 4.0 / 3.0 内容 base64 编码。可与 URL / magnet / 本地种子路径混用，各建独立任务 |
| --log-to <path> | string | 日志文件路径 |
| --position X,Y | string | 窗口初始位置（物理像素偏移） |
| --auto-referer | flag | 自动从 URL 提取 Referer |
| --retry N | int | 错误自动重试次数（默认 3） |
| --retry-interval N | int | 重试间隔秒（默认 2） |
| --retry-exhausted-timeout N | int | 重试耗尽后弹窗倒计时秒（默认 10） |
| --no-cancel | flag | 禁止取消/关闭。任务级互锁 |
| --verify-hash algo:hex | string | HTTP 任务二次 hash 校验，algo 为 md5/sha-1/sha-256/sha-512 |
| --marquee-mode scroll\|switch | string | 多文件走马灯模式（默认 scroll） |
| --marquee-speed F | float | scroll 模式步进秒（默认 0.06） |
| --marquee-interval F | float | switch 模式切换秒（默认 1.5） |
| --callback-port N | int | 结果回调端口。见第四节 |
| --http-port N | int | 启动 HTTP API 服务。见第五节 |
| -silent | flag | 不显示 GUI。常与 --http-port 组合 |

--metalink 长度限制：Windows 命令行 32767 字符，base64 膨胀 1.33 倍，原 XML 上限约 24 KB。超出时改用 HTTP 模式。

--metalink 与 --callback-port 配合：返回 {"status":"success","GID":"<组长GID>"}。多文件时 GID 为组长 GID。

--metalink hash 校验：metalink 内若含 <verification><hash>，自动启用二次校验。

### 2.2 命令式参数

| 参数 | 说明 |
|---|---|
| --query GID | 查询任务状态。必须带 --callback-port |
| --kill GID | 强制移除任务。必须带 --callback-port |
| -h / --help / /? | 帮助 |
| --rpc-listen-port N | 指定 aria2c RPC 端口（一般不需要） |

### 2.3 透传参数

除上表外，其他 --xxx=yyy 或 --xxx yyy 一律透传给 aria2c，例如：

    --dir=D:\Downloads
    --max-connection-per-server=16
    --split=10
    --user-agent=...
    --referer=...

被任务级黑名单过滤的参数（--out、--split、--max-download-limit 等）会从 aria2c 全局启动参数中剔除，但仍作为 RPC options 传给单个任务。

**--all-proxy**：所有任务的 HTTP/HTTPS 代理，如 `--all-proxy=http://127.0.0.1:7890`。任务级参数，随 addUri 传给单任务。

**--header**：可多次传入，如 `--header="Authorization: Bearer xxx" --header="Cookie: sess=abc"`。内部收集为数组传给 aria2 RPC，单次传入也按数组处理。

---
## 三、典型调用场景

### 3.1 简单下载

    agui.exe "https://example.com/file.zip"

### 3.2 同步拿 GID（推荐）

    import socket
    import json
    import subprocess
    import threading


    def recv_once(port, timeout=10):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        srv.settimeout(timeout)
        conn, _ = srv.accept()
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        conn.close()
        srv.close()
        return json.loads(data.decode("utf-8").strip())


    cb_port = 39111
    result_box = {}


    def wait():
        result_box["r"] = recv_once(cb_port)


    t = threading.Thread(target=wait)
    t.start()

    subprocess.Popen([
        "agui.exe",
        f"--callback-port={cb_port}",
        "--countdown=-1",
        "https://example.com/file.zip",
    ])
    t.join()
    print(result_box["r"])

### 3.3 命令行传 metalink

    agui.exe --metalink="<base64编码的meta4内容>" --countdown=-1

生成 b64：

    import base64
    b64 = base64.b64encode(open("test.meta4", "rb").read()).decode()
    subprocess.Popen(["agui.exe", f"--metalink={b64}", "--callback-port=39111"])

### 3.4 查询任务

    agui.exe --query abc123 --callback-port=39111

收到：

    {"status": "success", "data": {
        "status": "active",
        "totalLength": "10485760",
        "completedLength": "5242880",
        "downloadSpeed": "1048576",
        "errorMessage": "",
        "files": [],
        "downloadReady": false
    }}

downloadReady 为 true 表示文件已完整落盘。

### 3.5 杀掉任务

    agui.exe --kill abc123 --callback-port=39111

### 3.6 静默后台 HTTP 模式

    agui.exe --http-port=18999 -silent --countdown=-1

启动后无窗口，主程序通过 HTTP 通信。

---

## 四、回调协议

触发条件：命令行带 --callback-port=N。

agui 行为：把结果 JSON 字符串 + 一个换行符，通过 TCP 发到 127.0.0.1:N，发送后立即关闭连接。

主程序要求：

- 在调用前先 bind 并 listen 该端口
- 一次调用只收一条以换行结尾的 JSON
- 收到后立即释放端口

JSON 格式（全部 UTF-8）：

| 场景 | 返回 |
|---|---|
| 添加任务成功 | {"status":"success","GID":"<16位十六进制>"} |
| 添加任务失败 | {"status":"failed","message":"<原因>"} |
| 查询成功 | {"status":"success","data":{...}} |
| 查询无结果 | {"status":"failed","message":"task initializing or not found, retry later"} |
| 杀掉成功 | {"status":"success","message":"task killed"} |
| 杀掉失败 | {"status":"failed","message":"<原因>"} |

若主程序不监听该端口：agui 写日志"回调发送失败"后正常退出，不重试。

超时：agui 侧 3 秒，连接不上直接放弃。

---
## 五、HTTP API

启动方式：

    agui.exe --http-port=18999 -silent --countdown=-1

端点：POST http://127.0.0.1:18999/api

请求体：

    {
      "method": "add",
      "params": {}
    }

method 取值为 add / query / kill。

### 5.1 add

方式一：URL

    {
      "method": "add",
      "params": {
        "urls": ["https://a.com/x.zip", "https://a.com/y.zip"],
        "title": "批次1",
        "dir": "D:\\Downloads",
        "out": "自定义文件名.zip",
        "auto-referer": true,
        "no-cancel": false,
        "aria2_opts": {
          "max-connection-per-server": "16",
          "split": "10"
        },
        "log-to": "agui.log",
        "retry": "5"
      }
    }

支持 url（单字符串）或 urls（数组）。

方式二：metalink

    {
      "method": "add",
      "params": {
        "metalink": "<base64 编码的 metalink 内容>",
        "title": "批次1",
        "dir": "D:\\Downloads",
        "aria2_opts": {}
      }
    }

三者关系：urls / url / metalink 可同时提供，各建独立任务。三者都不提供时返回：

    {"status": "failed", "message": "url, urls or metalink is required"}

编码：metalink 必须 base64，不接受原始 XML。与命令行 --metalink= 一致。

响应：

    {"status": "success", "GID": "<组长GID>"}

### 5.2 query

    {"method": "query", "params": {"gid": "abc..."}}

返回格式同第四节"查询成功"。

### 5.3 kill

    {"method": "kill", "params": {"gid": "abc..."}}

返回同第四节"杀掉成功"。

### 5.4 HTTP countdown

`add` 请求的 `params` 支持 `countdown` 与 `global-countdown` 两个字段，语义与命令行 `--countdown` / `--global-countdown` 一致：

- `countdown`：任务级倒计时，本任务完成后 N 秒删卡
- `global-countdown`：全局倒计时，覆盖所有未钉死任务

```json
{
  "method": "add",
  "params": {
    "urls": ["https://a.com/x.zip"],
    "countdown": 30,
    "global-countdown": 60
  }
}
```

---

## 六、单实例与 IPC

端口：config.IPC_PORT = 19811。

启动流程：

1. 每个 agui 进程启动时尝试 bind 19811
2. bind 成功 → 主实例，启动 IPCServer 监听
3. bind 失败 → 从实例，把 raw_args 通过 TCP 发给主实例，主实例把 raw_args 交给 _add_task_sync 添加任务，结果原路返回

从实例转发规则：

- 带 --query 或 --kill 不转发，走独立分支直接调 IPC
- 其他带 URL 的情况全部转发
- 转发时 --countdown / --global-countdown / --metalink 会被主实例识别

主程序注意：

- 主程序只需要 subprocess.Popen agui，无需关心自己是不是第一个
- 无论主从，--callback-port 都会在任务注册后被调用

---
## 七、日志

### 7.1 --log-to 指定日志路径

```
agui.exe --log-to=D:\logs\my.log https://example.com/file.zip
```

日志文件**启动即创建**（空文件），事件发生时追加。

### 7.2 默认日志（无参数启动）

无参数启动且未指定 --log-to 时，主实例在**当前工作目录**生成时间戳文件：

```
agui-YYYY-MM-DD-HH-MM.log
```

同一分钟内重复启动会追加 -1、-2 后缀避免覆盖：`agui-2026-09-20-09-31-1.log`。

配置界面高级选项内有「记录日志」勾选框（默认勾选），可指定文件名或绝对路径。取消勾选后本次任务不写日志，已生成的空文件保留。

### 7.3 日志内容

日志包含两类行：

- 进程级：`Starting aria2c: ...`、`aria2c stopped`、防火墙警告等
- 任务级：`task added: gid=xxx name=xxx headers=N proxy=xxx`

注意：任务级 header / proxy 是 RPC options，**不出现**在 aria2c 启动命令行里，只在 `task added:` 行中可见。

---

## 八、配置文件

### 8.1 路径

```
~/.agui/agui_config.json
```

Windows 下即 `C:\\Users\\<用户名>\\.agui\\agui_config.json`。

### 8.2 结构

```json
{
  "theme": "midnight",
  "save_paths": {"recent": [], "starred": []},
  "preferences": {
    "split": 5, "path": "",
    "ua": "", "referer": "", "auto_referer": false,
    "max_conn": 16, "file_allocation": "falloc",
    "rpc_port": 16800, "min_split_size": "1M",
    "speed_limit": "0", "log_enabled": true,
    "log_path": "", "advanced": false
  }
}
```

### 8.3 字段

- `theme`：当前主题，取值 `midnight` / `cyberpunk` / `cyberpunk_v1`
- `save_paths.recent`：最近使用过的保存路径，最多 20 条，倒序
- `save_paths.starred`：收藏的保存路径
- `preferences`：配置界面各字段的持久化值，仅在无参数启动 GUI 时读写
- 敏感字段不持久化：Authorization / Cookie / 代理 不写入此文件

### 8.4 迁移

首次启动若检测到旧文件 `~/.agui/save_paths.json`，自动迁移到 `agui_config.json` 的 `save_paths` 子键。旧文件保留作备份。

---

## 九、进程生命周期

| 触发 | 效果 |
|---|---|
| 全部任务完成 + --countdown 计时到 | 逐卡删；最后一张删完即退出 |
| 全部任务完成 + --global-countdown | 同上 |
| 全部任务完成 + --countdown=-1 | 卡片永久保留，程序不退出，等待 --kill |
| 用户手动关窗 | 弹窗确认（--no-cancel 时禁止） |
| 收到 --kill GID | 移除该任务；若为最后一张 → 退出 |
| aria2c 启动失败 | 弹错误框后退出 |

---

## 十、已知坑

1. --query / --kill 建议只在主实例已运行时使用

   若主程序带 --query 启动第一个 agui，此时 IPC 端口还没被任何进程绑，_ipc_handler 里的 s.connect(("127.0.0.1", 19811)) 会连接失败，返回 {"status":"failed","message":"无法连接到主实例: ..."}。

   正确用法：先启动一个不带 query/kill 的主实例，再调 query/kill。

2. --title 需要 JSON 转义信息部分

   --title "标题|说明" 中说明部分若含双引号，需按 JSON 规则转义。简单场景不用管。

3. metalink 多文件任务在 UI 上只对应 1 张卡

   组内所有 GID 由一个"组长 GID"代表。--query <非组长 GID> 会正常返回，但 UI 层不展示该卡。建议主程序通过 --query <组长 GID> 查询，组长 GID 是 add 返回的那个。

4. --no-cancel 会锁死窗口

   任务未完成时无法关闭窗口、无法点卡片 X。主程序慎用。

5. 回调端口重入

   一次 agui 调用只回一次 callback。若主程序发送多个任务给同一 agui（HTTP 模式），每个 add 请求的响应走 HTTP 响应，不走 callback。

6. `-silent` / `--silent` 模式不显示任何窗口

   用于后台常驻，无 GUI。如需观察任务进度，请通过 HTTP query 或省略该参数。

7. IPC 端口冲突

   若上一轮 agui 未干净退出，19811 会被占用，新启动的进程被当作从实例转发后退出，表现为"启动无反应"。排查：

       netstat -ano | findstr :19811
       tasklist | findstr python

   清理：

       taskkill /f /pid <PID>

---

## 十一、推荐集成方式

短连接同步添加：

    每次 subprocess.Popen([
        "agui.exe",
        "--callback-port=<新端口>",
        "--countdown=-1",
        "<url>"
    ])

长连并发控制：

    首次启动:  agui.exe --http-port=18999 -silent
    后续添加:  POST /api {"method":"add",...}
    状态轮询:  POST /api {"method":"query",...}
    任务终止:  POST /api {"method":"kill",...}
    程序退出:  taskkill 或 http 侧发 kill 所有任务

日志：建议主程序给每个调用都传 --log-to=<独立路径>，便于排查。
