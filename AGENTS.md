# AGENTS.md — agui 项目协作准则

## 〇、总纲

三条不可违背的底层原则：

1. **不抢跑**：未达成逻辑共识前不输出代码。
2. **不假设**：遇歧义必须提问，不得静默选一个方向就动手。
3. **不扩散**：每次修改只针对当前指令，禁止顺手重构、清理、优化。

以下各条，均是这三条的展开。

---

## 一、编号协议

- 用户提问：`qXX`（如 `q08`）
- AI 回复：`ds-aXX-YY YYYY-MM-DD H:M:S`（如 `ds-a08-01 2026-09-21 13:14`）
- `XX` 与用户提问编号对齐，`YY` 递增
- **未给时间戳时，先提醒补时间，不作答**

---

## 二、沟通方式

- 中文
- 惜字如金，不重复无修改内容
- 不抢跑：未达成逻辑共识前不输出代码
- 有异议必须反驳，不盲从
- **列问题用字母（A1/A2/…），建议方向也用字母（A/B/C），末尾请用户回选字母**，减少往返成本
- 给出建议后附"—— 不答即默认 X"，让用户可一句话推进

---

## 三、代码修改方式

- **不用 git diff**，用 Python 字符串替换脚本
- 脚本命名 `ds-aXX-YY.py`，放 `fix/` 子目录
- **脚本文件名不得与目标文件名相同**（如补丁脚本禁止命名为 `sync_to_release.py`）
- 脚本头**必须**显式注明目标文件（本脚本为补丁，目标文件是 X）
- 脚本格式：**修改阶段 + 验证阶段**
- 失败 `sys.exit(1)`，打印 `FAILED: <具体项>`
- 成功打印 `ALL OK`
- **幂等保护**：`old not in c` 时检查 `new in c`，若在则 SKIP
- **改前先 dump 实况**：已改过的函数，`old` 必须从当前文件读取，不凭记忆写
- **小改优先用最简匹配**：能一行替换就别写带上下文的大段
- **每次脚本只做一件事**，多改动分脚本
- 用户跑脚本后，**贴输出才算验证**；AI 不得假设已通过

---

## 四、内容输出

- Python 代码中**禁止分号**
- 不引入不必要的 import
- 脚本内嵌 markdown 三反引号用 `chr(96)*3` 拼接
- f-string 里不能含反斜杠转义引号（Python 3.11 限制），用 `chr(34)` 代替
- 拒绝硬编码假设，路径、版本、文件名均从变量取

---

## 五、验证纪律（来自本会话教训）

- **涉及 UI 的改动必须真机运行验证**，py_compile 通过不等于功能正确
- **修改前先 dump 实况，不凭记忆**
- **修改后跑 `fix/smoke.py`**（4 项回归：导入 / HTTP 往返 / IPC 混合类型 / HTTP metalink）
- 修 bug 时，先**明确列出假设**（A 假设什么、需 dump 什么确认），再动手
- 连续两次尝试失败时，**停下做最小探针**（如 `fix/probe_*.py`），不再继续猜

---

## 六、同步与发布

- 主目录 `U:\python\agui-ds-1.5\`（公司机）**非 git 仓库**，仅作工作区
- `git_release/` 是**唯一 git 仓库**，remote：GitHub `pda8888/agui` + Gitee `pda8888/agui`
- 同步命令：`python fix/sync_to_release.py --commit --push`
  - 镜像语义：先清白名单外，再复制
  - 白名单在 `fix/sync_to_release.py` 的 `ROOT_FILES` / `ROOT_DIRS` / `FIX_KEEP`
  - 新增文件**必须**先加白名单，否则同步时被跳过
- 每次同步后**核对清单**，检查删除/新增是否符合预期
- 手动 push 已包含在 `--push` 中，无需 `cd git_release` 再操作

---

## 七、会话管理

- **长会话末段错误率上升**，可观测信号：记忆内容与实况不符、连续猜错方向
- 出现上述信号时，**收口归档，开新会话**
- 新会话只带**更新过的交接书** + **单一议题**
- 不要将全部聊天记录拖入新会话

---

## 八、四条 Karpathy 原则（通用行为约束）

1. **Think Before Coding**：写代码前，明确列出理解、假设、歧义点、更简方案。有歧义不自己选，提问。
2. **Simplicity First**：只写解决当前问题所需的最少代码。不为"以后可能用到"加抽象、配置、扩展点。
3. **Surgical Changes**：每行改动都可追溯到当前需求。禁止顺手重构、修无关样式、清理未用变量。
4. **Goal-Driven Execution**：把模糊指令转为可验证的成功标准。如"修 bug" → "先写复现，再让它通过"。

---

## 九、当前项目关键事实（防走回头路）

- 版本 V1.4，`config.py` 定义 `APP_TITLE` / `APP_VERSION`
- 单实例 + IPC：`IPC_PORT=19811`
- aria2c sidecar：每实例一个子进程，随机端口，JSON-RPC 通信
- 主题（8 套）：`midnight` / `cp1` / `cp2` / `neon_dreams` / `tech_noir` / `synthwave` / `cyber_ui` / `chrome`
  - 旧名 `cyberpunk`→`cp1`，`cyberpunk_v1`→`cp2`，首次启动自动迁移配置
  - 显示名对照：午夜蓝调 / 极夜青 / 夜幕残阳 / 霓虹之梦 / 科技暗夜 / 合成器之夜 / 绚丽极客 / 机械全息
- 配置文件：`~/.agui/agui_config.json`，三子键 `theme` / `save_paths` / `preferences`
- 核心文件：`main.py` / `config.py` / `arg_parser.py` / `rpc_client.py` / `process_manager.py` / `ipc_server.py` / `http_server.py` / `utils.py` / `ui_config.py` / `ui_download.py` / `ui_styles.py` / `ui_help.py` / `info_overlay.py`
- 回归脚本：`fix/smoke.py`
- 同步脚本：`fix/sync_to_release.py`

### 有意未做（不是遗漏，是被判定收益 < 风险）
- `rpc_client.rpc_request` 的 `except: return None`——高频调用，改返回结构影响面大
- `_create_task_row` 未拆（~200 行）——耦合拖选/悬停/tooltip，拆出需传大量回调
- 无 CI——`fix/smoke.py` 手工跑替代
- `cyberpunk_v1` 已删，保留 `cp1`/`cp2`

---

## 十、已知坑（防重犯）

1. `ui_download._update_layout` 用 `winfo_reqheight()` 实测，不硬编码
2. cyberpunk 左侧 stripe 必须 `height=1`，否则撑高卡片
3. `_rebuild_ui` 里必须 `self.configure(fg_color=Theme.BG)`
4. `CTkLabel` **不支持** `border_width` / `border_color`，边框用外层 `CTkFrame` 画
5. `CTkFrame` 内含按钮时 `corner_radius` 失效，整组 hover 用单按钮 hover 替代
6. 主题切换会触发刷新循环 `configure` 覆盖 hover 状态，需状态差异才重绘
7. `--no-add` 是**实例级**，从实例转发时被主实例吞掉不生效
8. `--no-cancel` 是**任务级**，随卡片记录
9. `_rpc_add_metalink_file` 等可能从 IPC/HTTP 线程进入的 UI 操作，必须 `self.after(0, ...)` 调度
10. tooltip / 主题菜单等浮层定时器挂 `self.after` 而非 `widget.after`