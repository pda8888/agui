# Aria2 GUI 重构方案

## 模块划分

### 1. config.py - 配置与常量
- 全局配置项 (路径、端口、颜色主题)
- DHT节点列表
- Tracker列表
- 默认aria2参数

### 2. utils.py - 工具函数
- 文件大小格式化 (nice_size)
- 时间格式化 (nice_duration, nice_time)
- 路径处理 (get_long_path_win32, get_aria2c_path)
- 端口查找 (find_free_port)
- URL解析 (extract_urls_and_out, parse_custom_t_arg)

### 3. process_manager.py - 进程管理
- Windows Job Object管理
- aria2c进程启动/停止
- 防火墙规则管理

### 4. rpc_client.py - RPC通信
- RPC请求封装
- 任务操作方法 (pause/resume/remove)
- 状态查询

### 5. ipc_server.py - 进程间通信
- 单实例检测
- 任务转发
- Socket服务器

### 6. ui_config.py - 配置界面
- Aria2ConfigGUI类
- 参数输入表单
- 验证逻辑

### 7. ui_download.py - 下载界面
- Aria2GUI类
- 任务列表UI
- 进度更新
- 全局统计

### 8. main.py - 程序入口
- UAC提权
- 参数解析
- 流程控制

## 优化点

### 代码压缩
1. **合并重复的样式定义** - Dark.TButton在多处定义
2. **统一对话框逻辑** - messagebox和自定义对话框可以封装
3. **简化参数解析** - parse_args中有大量重复的if-elif结构
4. **合并UI创建代码** - 输入框、标签创建有固定模式

### 功能精简
1. **移除调试打印** - 保留关键日志，删除临时调试代码
2. **统一错误处理** - 用装饰器或上下文管理器
3. **简化状态管理** - 任务状态可以用枚举类

### 性能优化
1. **减少RPC调用频率** - 批量查询多个任务
2. **UI更新节流** - 避免高频重绘
3. **延迟加载** - 模块按需导入

## 文件结构
```
aria2_gui/
├── __init__.py
├── main.py           (150行)
├── config.py         (100行)
├── utils.py          (200行)
├── process_manager.py (250行)
├── rpc_client.py     (150行)
├── ipc_server.py     (150行)
├── ui_config.py      (400行)
├── ui_download.py    (600行)
└── resources/
    └── aria2c.exe
```

总代码量预计: ~2000行 (减少25%)
