#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帮助信息窗口 (CustomTkinter版)"""
import os
import sys
import customtkinter as ctk
from config import APP_TITLE, Theme
from ui_styles import create_button, center_window, FONT_SMALL

def get_help_text():
    """获取帮助文本"""
    prog_name = (
        os.path.basename(sys.executable)
        if getattr(sys, "frozen", False)
        else "python agui.py"
    )
    
    return f"""
{APP_TITLE}

用法:
    {prog_name} [自定义选项] <URL | Magnet | Torrent文件>

自定义选项:
    --title "标题|信息"     设置窗口标题和说明文本。
    --countdown <秒数>      下载完成后自动关闭的倒计时 (默认: 30)。
    --no-cancel            强制下载模式 (下载过程中禁止取消或关闭窗口)。
    --log-to <路径>        将运行时日志写入指定文件。
    -h, --help, /?         显示此帮助信息并退出。

其他选项:
    所有非上述选项 (如 --split=10, --dir=D:\\Downloads) 均直接传递给 aria2c 内核。
    支持 HTTP/FTP/Magnet 链接及本地 .torrent 文件路径。
"""

class HelpWindow(ctk.CTkToplevel):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} - 帮助")
        self.configure(fg_color=Theme.BG)
        self.resizable(False, False)
        
        self._build_ui()
        
        # 居中
        center_window(self, 640, 480)
        
        # 绑定ESC关闭
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _build_ui(self):
        # 文本框
        text_area = ctk.CTkTextbox(
            self,
            font=FONT_SMALL,
            wrap="word",
            fg_color="#2d3748",
            text_color=Theme.TEXT,
            corner_radius=8
        )
        text_area.insert("1.0", get_help_text())
        text_area.configure(state="disabled") # 只读
        text_area.pack(fill="both", expand=True, padx=15, pady=15)
        
        # 关闭按钮
        create_button(self, text="关闭", command=self.destroy, width=100, style="secondary").pack(pady=(0, 15))

def show_help():
    """显示帮助窗口"""
    if not getattr(sys, "frozen", False):
        # 脚本模式：如果没有主窗口，直接print也行，但为了统一体验还是弹窗
        # 如果是命令行调用 -h，通常期望在控制台看到，这里保留print逻辑
        if len(sys.argv) > 1 and any(x in sys.argv for x in ["-h", "--help", "/?"]):
             print(get_help_text())
             return

    # 创建一个临时的root来承载Toplevel，如果主程序还没运行
    app = ctk.CTk()
    app.withdraw() # 隐藏主窗口
    
    help_win = HelpWindow()
    
    # 当帮助窗口关闭时，退出程序
    help_win.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), sys.exit(0)))
    
    app.mainloop()