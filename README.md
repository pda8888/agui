# 老王的小拖船

一个基于 aria2c 的超轻量下载器。Windows 优先，内存 < 30 MB，启动 < 1 秒，无 Electron，无浏览器内核。

## 特性

- **超轻量**：Python + CustomTkinter + aria2c sidecar
- **多协议**：HTTP / FTP / Magnet / BT / Metalink 4.0
- **多文件 Metalink**：单卡片聚合展示，走马灯循环显示全部文件名
- **任务级参数**：`--countdown` 完成后自动删卡、`--global-countdown` 全局覆盖
- **双 hash 校验**：aria2c 内置 + Python 二次独立校验（md5 / sha-1 / sha-256 / sha-512）
- **Motrix 风格 UI**：卡片式布局、右上图标组、悬停 tooltip、框选多选
- **info 悬停浮层**：一级目录聚合 + 全展开 + 滚动 + 剪贴板
- **单实例 IPC**：多次启动自动转发到主实例
- **命令行 / HTTP API / 回调端口**：三套对外接口，方便主程序集成
- **深色主题**：跟随系统 DPI，工作区居中

## 环境要求

- Windows 10 / 11（主要目标）
- Python 3.9+
- [aria2c](https://github.com/aria2/aria2/releases)（用户自行下载，放到项目根目录）
- Python 依赖：
pip install customtkinter requests

## 快速开始

1. 克隆仓库：
git clone https://github.com/<你的用户名>/<仓库名>.git
cd <仓库名>

2. 下载 aria2c.exe 到项目根目录（[下载地址](https://github.com/aria2/aria2/releases)）

3. 安装依赖：
pip install customtkinter requests


4. 启动：
python main.py


## 使用

### GUI 模式

无参数启动，弹出配置界面，填写 URL 与保存路径，点击提交。

### 命令行模式
python main.py "https://example.com/file.zip"

python main.py --countdown=5 "https://example.com/file.zip"

python main.py --title "批次1|测试" "magnet:?xt=urn:btih:..."


### Metalink 模式

python main.py path\to\file.meta4

python main.py --metalink="<base64编码的meta4内容>"

### 更多

完整的命令行参数、HTTP API、回调协议、IPC 机制说明见 [docs/CLI.md](docs/CLI.md)。

---
## 项目结构
.
- `main.py` — 入口
- `config.py` — 常量与主题
- `arg_parser.py` — 命令行解析
- `rpc_client.py` — aria2 JSON-RPC 封装
- `process_manager.py` — aria2c 进程与防火墙
- `ipc_server.py` — 单实例 IPC
- `utils.py` — 工具函数
- `ui_config.py` — 配置界面
- `ui_download.py` — 下载监控主界面
- `ui_styles.py` — UI 样式工厂
- `ui_help.py` — 帮助窗口
- `docs/CLI.md` — CLI / API 调用手册
- `LICENSE`
- `README.md`

## 键盘与鼠标

- **单击卡片**：选中
- **Ctrl + 单击**：多选切换
- **拖动**：框选
- **悬停图标**：显示 tooltip
- **悬停 ⓘ**：显示任务详情浮层
- **顶栏图标**：仅对选中任务生效（无选中时无效）

## 已知限制

- **Windows 优先**：部分功能（Job Object、防火墙、`os.startfile`）依赖 Windows API，Linux/macOS 未测试
- **`--query` / `--kill` 依赖主实例**：需先启动一个主实例，再从另一终端查询
- **HTTP API 的 countdown 参数暂未生效**：请走命令行方式
- **`--gid` 参数未实现**：写入被忽略

详见 [docs/CLI.md 已知坑](docs/CLI.md)。

## 架构要点

- **单实例 + IPC**：第一个启动的进程占用 `IPC_PORT=19811` 成为主实例，后续启动的进程自动转发命令行后退出
- **aria2c sidecar**：每个实例启动一个 aria2c 子进程，绑定到随机可用端口，通过 JSON-RPC 通信
- **进程保护**：Windows Job Object，父进程退出时子进程随之终止
- **双 hash 校验**：aria2c 下载完成后由内核校验，Python 独立重算，双保险

## License

[MIT](LICENSE)

## 致谢

- [aria2](https://github.com/aria2/aria2)：下载内核
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)：深色主题 UI
- [Motrix](https://github.com/agalwood/motrix)：V1.8 卡片布局的视觉参考

## 免责声明

本项目仅作为 aria2c 的图形界面封装。使用者应遵守所在地法律法规，不得用于下载盗版、色情或其他违法内容。项目作者不对使用者的行为承担任何责任。
