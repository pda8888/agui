#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI样式统一管理 (支持对齐修正版)"""
import customtkinter as ctk
from config import Theme
# import tkinter as tk

# 字体配置
FONT_NORMAL = ("Segoe UI", 12)
FONT_BOLD = ("Segoe UI", 12, "bold")
FONT_SMALL = ("Consolas", 11)

# 【新增】全局变量，用于记录当前打开的菜单
_current_menu = None

# === 自定义深色右键菜单类 (全局监听版) ===
class ContextMenu(ctk.CTkToplevel):
    def __init__(self, widget, event):
        global _current_menu
        
        # 1. 清理旧菜单
        if _current_menu:
            try:
                _current_menu.destroy()
            except:
                pass
        _current_menu = self

        super().__init__()
        self.widget = widget
        # 获取主窗口 (root)，用于绑定全局点击
        self.root = self.widget.winfo_toplevel()
        
        # 2. 窗口属性
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # 3. 样式
        bg_color = "#1f2937"
        hover_color = "#374151"
        text_color = "#f3f4f6"
        border_color = "#4b5563"
        
        # 4. 布局
        self.frame = ctk.CTkFrame(self, corner_radius=6, fg_color=bg_color, 
                                  border_width=1, border_color=border_color)
        self.frame.pack(fill="both", expand=True)
        
        # 5. 生成菜单项
        def create_item(text, command):
            btn = ctk.CTkButton(
                self.frame, 
                text=text, 
                command=lambda: self._exec(command),
                width=120, 
                height=28, 
                corner_radius=4,
                fg_color="transparent", 
                hover_color=hover_color, 
                text_color=text_color,
                anchor="w",
                font=("Segoe UI", 12)
            )
            btn.pack(padx=4, pady=2, fill="x")

        create_item("复制  (Ctrl+C)", lambda: self._perform("<<Copy>>"))
        create_item("粘贴  (Ctrl+V)", lambda: self._perform("<<Paste>>"))
        create_item("剪切  (Ctrl+X)", lambda: self._perform("<<Cut>>"))
        
        div = ctk.CTkFrame(self.frame, height=1, fg_color=border_color)
        div.pack(fill="x", padx=4, pady=2)
        
        create_item("全选  (Ctrl+A)", self._select_all)

        # 6. 定位
        x = event.x_root + 1
        y = event.y_root + 1
        self.geometry(f"140x150+{x}+{y}")
        
        self.deiconify()
        
        # 【核心修改】
        # 不使用 grab_set，而是监听主窗口的点击事件
        # 只要主窗口内发生点击，就会触发 _check_click_outside
        # 改为：
        self.bindings = [
            ("<Button-1>", self.root.bind("<Button-1>", self._check_click_outside, add="+")),
            ("<Button-2>", self.root.bind("<Button-2>", self._check_click_outside, add="+")),
            ("<Button-3>", self.root.bind("<Button-3>", self._check_click_outside, add="+"))
        ]
        
        # 监听自身的 FocusOut (处理点击软件外部的情况，如切换窗口)
        self.after(100, lambda: self.bind("<FocusOut>", lambda e: self.destroy()))

    def _check_click_outside(self, event):
        """检查点击是否发生在菜单外部"""
        try:
            # 改用坐标判断，而非控件名称判断
            menu_x = self.winfo_x()
            menu_y = self.winfo_y()
            menu_w = self.winfo_width()
            menu_h = self.winfo_height()
            
            click_x = event.x_root
            click_y = event.y_root
            
            # 如果点击在菜单矩形区域内，不处理
            if (menu_x <= click_x <= menu_x + menu_w and 
                menu_y <= click_y <= menu_y + menu_h):
                return
            
            # 点击在外部，销毁菜单
            self.destroy()
        except:
            self.destroy()

    def _exec(self, func):
        try:
            func()
        except:
            pass
        self.destroy()

    def destroy(self):
        global _current_menu
        if _current_menu == self:
            _current_menu = None
            
        # 解除主窗口的绑定，防止内存泄漏或报错
        try:
            if hasattr(self, 'bindings'):
                for sequence, bind_id in self.bindings:
                    self.root.unbind(sequence, bind_id)
        except:
            pass
            
        super().destroy()

    def _get_target(self):
        if hasattr(self.widget, "_textbox"):
            return self.widget._textbox
        if hasattr(self.widget, "_entry"):
            return self.widget._entry
        return self.widget

    def _perform(self, event_key):
        try:
            target = self._get_target()
            target.event_generate(event_key)
        except:
            pass

    def _select_all(self):
        try:
            target = self._get_target()
            target.focus_set()
            if hasattr(target, "select_range"):
                target.select_range(0, 'end')
            elif hasattr(target, "tag_add"):
                target.tag_add("sel", "1.0", "end")
        except:
            pass

 
def add_context_menu(widget):
    """为控件绑定右键菜单"""
    def show(event):
        # 安全检查控件状态
        # CTkEntry 支持 cget("state")，但 CTkTextbox 不支持并会报错
        try:
            state = widget.cget("state")
        except ValueError:
            # 如果控件不支持查询状态(如CTkTextbox)，默认视为可用
            state = "normal"
        except AttributeError:
            state = "normal"
            
        # 只有在非禁用状态下才显示菜单
        if state != "disabled":
            widget.focus_set()
            ContextMenu(widget, event)
            
    widget.bind("<Button-3>", show)
    
def create_label(parent, text, bold=False, color=None, font_size=12, width=None, anchor="w"):
    """
    创建标准标签
    新增 width 和 anchor 参数，用于实现表格化对齐
    """
    font = (FONT_NORMAL[0], font_size, "bold" if bold else "normal")
    
    # 组装参数
    kwargs = {
        "text": text,
        "text_color": color or Theme.TEXT,
        "font": font,
        "anchor": anchor
    }
    if width is not None:
        kwargs["width"] = width

    return ctk.CTkLabel(parent, **kwargs)

def create_entry(parent, textvariable=None, width=None):
    """创建标准输入框"""
    entry = ctk.CTkEntry(
        parent,
        textvariable=textvariable,
        font=FONT_SMALL,
        fg_color="#2d3748",
        text_color=Theme.TEXT,
        border_color=Theme.MUTED,
        height=28,
        corner_radius=6
    )
    if width:
        entry.configure(width=width)
    # 【新增】这里必须调用，否则标题、路径等输入框就没有菜单
    add_context_menu(entry)
    return entry

def create_spinbox(parent, from_=1, to=16, initial=None, width=80):
    """使用Entry模拟Spinbox"""
    spinbox = ctk.CTkEntry(
        parent,
        font=FONT_SMALL,
        fg_color="#2d3748",
        text_color=Theme.TEXT,
        border_color=Theme.MUTED,
        width=width,
        height=28,
        corner_radius=6
    )
    if initial is not None:
        spinbox.insert(0, str(initial))
    # 【新增】这里也要调用
    add_context_menu(spinbox)
    return spinbox

def create_checkbox(parent, text, variable):
    """创建标准复选框"""
    return ctk.CTkCheckBox(
        parent,
        text=text,
        variable=variable,
        text_color=Theme.TEXT,
        font=FONT_NORMAL,
        fg_color=Theme.ACCENT,
        hover_color=Theme.ACCENT_LIGHT,
        corner_radius=4,
        border_width=2,
        checkbox_width=20,
        checkbox_height=20
    )

def create_button(parent, text, command, width=120, state="normal", style="primary"):
    """创建按钮"""
    if style == "secondary":
        fg_color = "transparent"
        border_color = Theme.SEMI_MUTED
        border_width = 1
        hover_color = "#374151"
        text_color = Theme.TEXT
    else:
        # primary
        fg_color = "#0ea5e9" # Sky Blue
        border_color = "#0ea5e9"
        border_width = 0
        hover_color = "#0284c7"
        text_color = "white"

    btn = ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=width,
        height=28,
        corner_radius=6,
        font=("Segoe UI", 12, "bold"),
        state=state,
        fg_color=fg_color,
        border_color=border_color,
        border_width=border_width,
        hover_color=hover_color,
        text_color=text_color
    )
    return btn

def get_work_area_and_scaling(window):
    """返回 Windows 工作区物理尺寸与 CTk 缩放因子
    返回: (work_x0, work_y0, work_w, work_h, scaling)
    """
    work_x0 = 0
    work_y0 = 0
    work_w = window.winfo_screenwidth()
    work_h = window.winfo_screenheight()
    try:
        import ctypes
        from ctypes import wintypes
        SPI_GETWORKAREA = 0x0030
        wa = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETWORKAREA, 0, ctypes.byref(wa), 0
        )
        if wa.right > wa.left and wa.bottom > wa.top:
            work_x0 = wa.left
            work_y0 = wa.top
            work_w = wa.right - wa.left
            work_h = wa.bottom - wa.top
    except Exception:
        pass
    try:
        scaling = ctk.ScalingTracker.get_window_scaling(window)
    except Exception:
        scaling = 1.0
    return work_x0, work_y0, work_w, work_h, scaling


def center_window(window, width, height):
    window.update_idletasks()
    wx0, wy0, ww, wh, sc = get_work_area_and_scaling(window)
    phys_w = int(width * sc)
    phys_h = int(height * sc)
    x = wx0 + (ww - phys_w) // 2
    y = wy0 + (wh - phys_h) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")