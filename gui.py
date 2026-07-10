"""
微信群发工具 GUI 版
本软件由 淘淘数码 研发，版权归 淘淘数码 所有。
仅限于授权用户内部使用，禁止用于任何商业用途。
未经许可，禁止复制、修改、分发或转售。
解释权归 淘淘数码 所有。
"""

# ==================== 导入要用到的工具库 ====================

import os       # 操作文件和路径（拼接路径、检查文件是否存在等）
import tkinter as tk
# tkinter 是 Python 自带的图形界面库（不需要额外安装）
# 它帮你创建窗口、按钮、输入框、列表框等 GUI 元素
# 我们把它简称为 tk，后面写 tk.xxx 就能用它的功能

from tkinter import ttk, messagebox, scrolledtext
# ttk = 改进版的 tkinter 组件（更好看）
# messagebox = 弹窗（提示消息、警告、错误等）
# scrolledtext = 带滚动条的文本框（用来显示日志）

import threading
# threading = 多线程库
# 为什么需要多线程？因为 tkinter 的界面是"事件驱动"的
# 如果你在界面上点"运行"，程序开始发消息，界面就会卡住不动
# 因为 tkinter 要等你的代码执行完才能处理界面事件（刷新、按钮点击等）
# 用 threading 把发消息的代码放到另一个线程里跑，界面就不会卡了

import logging  # Python 的日志系统（打印带时间的信息）
import sys      # 系统和 Python 解释器相关（这里用来重定向 stdout）
from io import StringIO  # 内存中的"文件"，用来临时存文本

import pyautogui          # 键盘鼠标模拟（核心自动化库）
import send_wechat as sw  # 导入我们自己的核心脚本，起个简短别名 sw
import ctypes             # Windows API 调用（检测 ESC 键）


# ==================== 配置字段定义 ====================
# 这是一个"元组列表"——
# 每个元素是一个三元素的元组 (键名, 标签文字, 值类型)
# 这个列表驱动的思路：
#   只需要在这里定义配置项，下面的代码就自动生成输入框和读写逻辑
#   如果要新增一个配置项，只需要在这里加一行，不用改其他代码

CONFIG_FIELDS = [
    ("group_prefixes",       "群名前缀（逗号分隔）",          "str_list"),
    ("groups_per_prefix",    "每个前缀群数量",                "int"),
    ("send_times",           "定时时间（逗号分隔）",           "str_list"),
    ("speed_factor",         "速度倍率（0.2=极速 0.5=2倍 1.0=正常）", "float"),
    ("interval_between_groups", "前缀间隔秒数",               "int"),
    ("interval_between_files", "文件发送间隔（如 5m、30s、1h）", "str"),
    ("log_level",            "日志级别",                     "choice"),
    ("click_msg_offset",     "右键坐标 X,Y（窗口左上角偏移）",  "int_pair"),
    ("click_send_offset",    "发送坐标 X,Y（窗口左上角偏移）",  "int_pair"),
    # 值类型说明：
    #   str_list = 逗号分隔的字符串，解析成列表
    #   int      = 整数
    #   float    = 小数
    #   choice   = 下拉选择框
    #   int_pair = 两个整数，用逗号分隔（如 "1643, 811"）
    #   str      = 普通文本
]

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
# choice 类型的候选项，就是日志级别的四个选项


# ==================== 自定义日志处理器 ====================

class LogHandler(logging.Handler):
    """
    这是一个自定义的"日志处理器"（logging handler）。

    默认的 logging 会把日志打印到控制台（终端/命令行窗口）。
    但我们想让日志显示在 GUI 的文本框里，所以自定义一个处理器。

    继承关系：
      logging.Handler 是 Python 内置的日志处理器基类
      LogHandler 继承了这个基类，重写了其中的方法

    关键概念 —— 继承（Inheritance）：
      子类（LogHandler）拥有父类（logging.Handler）的所有功能
      你可以只改写需要变化的部分（这里只改了 emit 方法）
    """

    def __init__(self, text_widget):
        """
        构造函数：在创建 LogHandler 对象时自动调用。

        参数：
          text_widget: tkinter 的文本框组件（ScrolledText）
                       日志内容要显示在这个文本框里

        super().__init__() 的意思是：
          调一下父类（logging.Handler）的构造函数
          因为父类也需要初始化（比如设置日志级别、格式等）
          如果不调 super()，父类的初始化代码就不会执行

        self.text_widget = text_widget
          把传入的文本框保存为实例变量（self.xxx）
          这样其他方法（比如 emit）也能访问到这个文本框

        setFormatter 设置了日志的显示格式
        %(asctime)s  = 时间（如 2026-07-10 10:30:00）
        %(levelname)s = 日志级别（INFO、WARNING 等）
        %(message)s  = 实际的日志消息
        """
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))

    def emit(self, record):
        """
        emit 是 logging.Handler 的核心方法。
        每次有日志要输出时，系统会自动调用这个方法。

        record 参数：
          一个 LogRecord 对象，包含了所有日志信息：
          - record.levelname = "INFO"、"WARNING" 等
          - record.message   = 日志消息文本
          - record.asctime   = 格式化后的时间字符串

        处理流程：
          1. self.formatter.format(record)
              用之前设置的格式把日志对象变成字符串
              比如 "2026-07-10 10:30:00 [INFO] 你好"

          2. self.text_widget.after(0, lambda: (...))
              after 是 tkinter 的一个方法，作用是"定时执行"
              after(0, func) = 立刻执行 func（但要在 tkinter 的主循环里）
              为什么不能直接操作文本框？
                因为 tkinter 不是线程安全的
                日志可能来自任何线程（包括后台发消息的线程）
                直接操作文本框可能造成界面崩溃
                after() 把操作"排队"到 tkinter 主线程里执行，就安全了

          3. insert("end", msg + "\n")
              在文本框末尾追加新消息
              "end" = 末尾位置

          4. see("end")
              自动滚动到文本框末尾
              这样最新日志总是可见的，不需要手动滚动
        """
        # 先把日志对象（record）格式化成字符串
        msg = self.formatter.format(record)

        # 用 after(0, ...) 确保在主线程中更新 GUI
        self.text_widget.after(0, lambda: (
            self.text_widget.insert("end", msg + "\n"),
            self.text_widget.see("end"),
        ))
        # 这里用了一个元组 (insert(...), see(...))
        # after 会依次执行元组里的每个表达式


# ==================== 主应用类 ====================

class App:
    """
    这是整个 GUI 程序的"主类"。

    什么是类（class）？
      类 = 一个"蓝图"或"模板"，描述了某种对象的属性和行为
      类里有两种东西：
        1. 属性（变量）—— 描述状态（比如窗口大小、文本框内容等）
        2. 方法（函数）—— 描述行为（比如点击按钮后干什么）

    为什么用类而不用一堆函数？
      因为 GUI 程序有很多相关联的"状态"（配置、文件列表、日志等）
      用类可以把这些状态和行为组织在一起
      方便在不同方法之间共享数据（用 self.xxx 就能访问）

    约定：
      以 _ 开头的方法名（如 _build_ui）表示"内部使用，外部不该调"
      这叫"命名约定"，Python 没有真正的私有机制，全靠自觉
    """

    def __init__(self):
        """
        构造函数：创建 App 对象时自动执行。

        流程：
          1. 创建主窗口（self.root）
          2. 设置窗口标题和大小
          3. 调用 _build_ui() 构建界面元素
          4. 调用 _load_config() 把配置填入输入框
          5. 调用 _refresh_file_list() 刷新文件列表
          6. 调用 _setup_logging() 设置日志显示
        """

        # ---- 创建主窗口 ----
        # tk.Tk() 是 tkinter 的"根窗口"对象
        # 所有 GUI 程序都必须先创建一个 Tk 对象
        # 这个窗口就是你看到的那个窗口
        self.root = tk.Tk()

        # 设置窗口标题（出现在窗口顶部的标题栏）
        self.root.title("微信群发工具")

        # 设置窗口大小：宽 960 像素，高 800 像素
        # 格式是 "宽x高"，中间是字母 x 不是乘号
        self.root.geometry("960x800")

        # 设置窗口最小尺寸：宽不能小于 800，高不能小于 650
        # 拖动窗口右下角时不会小于这个尺寸
        self.root.minsize(800, 650)

        # ---- 初始化实例变量 ----
        # file_vars 用来存储文件复选框的状态
        # 但当前版本用了 Listbox，所以这个变量其实没用了
        self.file_vars = {}
        self._esc_poll_id = None  # ESC 轮询的 after ID

        # ---- 绑定全局快捷键 ----
        # 当 GUI 窗口有焦点时，按 ESC 也能触发停止
        self.root.bind("<Escape>", lambda e: self._stop())

        # ---- 构建界面 ----
        self._build_ui()

        # ---- 把配置加载到输入框 ----
        self._load_config()

        # ---- 刷新文件列表（显示目录下的 txt 文件） ----
        self._refresh_file_list()

        # ---- 设置日志系统 ----
        self._setup_logging()

    def _build_ui(self):
        """
        构建所有的界面元素。

        tkinter 的布局逻辑是"嵌套"的：
          窗口（root）
          └── main 框架 (ttk.Frame)
              ├── 配置参数区域 (ttk.LabelFrame)
              │   ├── 标签 + 输入框 (第 1 行)
              │   ├── 标签 + 输入框 (第 2 行)
              │   └── ...
              ├── 文件选择区域 (ttk.LabelFrame)
              │   ├── 全选/取消/刷新 按钮
              │   └── 文件列表框 (Listbox) + 滚动条
              ├── 按钮区域 (ttk.Frame)
              │   ├── 立即运行 / 定时模式 / 查看统计 / 保存配置 / 停止
              │   └── ...
              ├── 日志区域 (ttk.LabelFrame)
              │   └── 带滚动条的文本框
              └── right（右侧版权声明面板）

        pack() 和 grid() 是两种布局方式：
          pack()   = 按顺序"堆放"组件（从上到下或从左到右）
          grid()   = 用表格的方式来排列（行 row / 列 column）
          fill     = 填充方向（"x"=水平填充 "y"=垂直填充 "both"=双向）
          expand   = 是否在空间多余时扩展（True/False）
          padx/pady = 组件外部的间距（像素）
          sticky   = 对齐方式（"w"=靠左 "e"=靠右 "ew"=左右拉伸）
        """

        # outer = 最外层的大框架（水平布局）
        # ttk.Frame = 一个容器，用来放其他组件
        # padding=10 = 框架内部留 10 像素空白（不会紧贴边框）
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        # main = 左侧主区域（配置、文件、按钮、日志）
        main = ttk.Frame(outer)
        main.pack(side="left", fill="both", expand=True)

        # ============ 右侧版权声明面板 ============

        right = tk.LabelFrame(outer, text="版权声明", padx=15, pady=15,
                              font=("Microsoft YaHei", 10, "bold"),
                              foreground="#cc0000", bg="#fff0f0")
        right.pack(side="right", fill="y", padx=(10, 0))

        notice_text = (
            "⚠ 本软件由 淘淘数码 研发 ⚠\n\n"
            "版权归 淘淘数码 所有\n\n"
            "仅限于授权用户内部使用\n"
            "禁止用于任何商业用途\n\n"
            "未经许可，禁止复制、\n"
            "修改、分发或转售\n\n"
            "解释权归淘淘数码所有"
        )
        notice_label = tk.Label(
            right, text=notice_text,
            font=("Microsoft YaHei", 12, "bold"),
            foreground="#cc0000",
            bg="#fff0f0",
            justify="left",
            wraplength=200
        )
        notice_label.pack(pady=5)

        # ============ 1. 配置参数区域 ============

        # ttk.LabelFrame = 带标题边框的框架
        # text="配置参数" 会显示在框架的左上角
        cfg_frame = ttk.LabelFrame(main, text="配置参数", padding=10)
        cfg_frame.pack(fill="x", pady=(0, 10))  # 水平填充，下方留 10 像素间距

        # self.entries 字典：保存所有输入框的引用
        # 键 = 配置项名称（如 "group_prefixes"）
        # 值 = tkinter 的 StringVar 对象
        # StringVar 是 tkinter 的一种"变量"——
        # 当输入框内容改变时，StringVar 会自动更新
        # 反过来，修改 StringVar 的值，输入框也会自动显示新内容
        self.entries = {}

        # 用 for 循环遍历配置字段列表，自动生成输入框
        # enumerate() 的作用：同时拿到"索引"和"值"
        #   i   = 索引（0, 1, 2, ...）
        #   key, label, vtype = 从元组里解包出来的三个值
        for i, (key, label, vtype) in enumerate(CONFIG_FIELDS):
            # 创建标签（文本），放在第 i 行第 0 列，靠左对齐
            ttk.Label(cfg_frame, text=label).grid(
                row=i, column=0, sticky="w", pady=3
            )

            if vtype == "choice":
                # choice 类型 = 下拉选择框（Combobox）
                # StringVar 用来关联选择框的当前值
                var = tk.StringVar()
                # state="readonly" 表示只能选不能手动输入
                box = ttk.Combobox(
                    cfg_frame, textvariable=var,
                    values=LOG_LEVELS, width=30, state="readonly"
                )
                box.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=3)
                self.entries[key] = var
            else:
                # 其他类型 = 普通的文本输入框（Entry）
                var = tk.StringVar()
                entry = ttk.Entry(cfg_frame, textvariable=var, width=35)
                entry.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=3)
                self.entries[key] = var

        # columnconfigure(1, weight=1) 的意思是：
        #   第 1 列（输入框所在列）在窗口变宽时会自动拉伸
        #   weight=1 表示"权重为 1"，如果有多个列权重不同，按比例分配
        cfg_frame.columnconfigure(1, weight=1)

        # ============ 2. 文件选择区域 ============

        file_frame = ttk.LabelFrame(main, text="选择发送文件（可多选）", padding=10)
        file_frame.pack(fill="x", pady=(0, 10))

        # 按钮行
        top_row = ttk.Frame(file_frame)
        top_row.pack(fill="x", pady=(0, 5))
        ttk.Button(top_row, text="全选", command=self._select_all).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(top_row, text="取消全选", command=self._deselect_all).pack(
            side="left", padx=5
        )
        ttk.Button(top_row, text="刷新列表", command=self._refresh_file_list).pack(
            side="left", padx=5
        )

        # 文件列表框
        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill="x")

        # Listbox = 列表框，可以显示多个项目
        # selectmode="multiple" = 可以按住 Ctrl 多选
        # height=6 = 显示 6 行的高度
        # font=("Consolas", 10) = 等宽字体 Consolas，大小 10
        # exportselection=False = 防止选中内容被其他窗口抢走
        self.file_listbox = tk.Listbox(
            list_frame, selectmode="multiple", height=6,
            font=("Consolas", 10), exportselection=False
        )
        self.file_listbox.pack(side="left", fill="x", expand=True)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.file_listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # ============ 3. 操作按钮区域 ============

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(0, 10))

        # 每个按钮的 command 参数指定了点击时要调用的方法
        # 注意：这里传的是方法名（不带括号），不是调用结果
        # 比如 command=self._run_once 而不是 command=self._run_once()
        # 因为 tkinter 需要在点击时调用，而不是现在调用
        ttk.Button(btn_frame, text="立即运行", command=self._run_once).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(btn_frame, text="定时模式", command=self._run_daemon).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="查看统计", command=self._show_stats).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(
            side="left", padx=5
        )

        # 停止按钮特殊：默认是禁用的（灰色不可点）
        # 只有运行中才启用，防止误触
        self.stop_btn = ttk.Button(
            btn_frame, text="停止", command=self._stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)

        # ============ 4. 日志显示区域 ============

        log_frame = ttk.LabelFrame(main, text="运行日志", padding=5)
        log_frame.pack(fill="both", expand=True)  # fill="both" + expand=True = 占据剩余空间

        # ScrolledText = 带滚动条的文本框
        # height=15 = 初始显示 15 行高度
        # wrap="word" = 按单词换行（不是按字符）
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, font=("Consolas", 10),
            wrap="word", state="normal"
        )
        self.log_text.pack(fill="both", expand=True)

        # ============ 5. 底部版权声明（已移至右侧面板） ============

    # ==================== 文件列表管理 ====================

    def _refresh_file_list(self):
        """
        刷新文件列表框。
        调用 sw.get_available_txt_files() 获取所有可用的 txt 文件，
        显示在列表框中，并恢复已选中的项目。

        sw 是 send_wechat 模块的别名（写在文件顶部了）。
        """
        # 清空列表框（从第 0 项到末尾全部删除）
        self.file_listbox.delete(0, "end")

        # 获取可用文件列表
        names = sw.get_available_txt_files()

        # 获取已选中的文件列表
        selected = sw.CONFIG.get("txt_files", [])
        # 把选中文件的"文件名部分"提取出来，放到一个集合里
        # {os.path.basename(p) for p in selected} 这叫"集合推导式"
        # 相当于：
        #   result = set()
        #   for p in selected:
        #       result.add(os.path.basename(p))
        sel_basenames = {os.path.basename(p) for p in selected}

        # 重新填充列表框
        self.all_files = []
        for name in names:
            full = os.path.join(sw.SCRIPT_DIR, name)
            self.all_files.append(full)
            self.file_listbox.insert("end", name)

        # 恢复选中状态
        for i, full in enumerate(self.all_files):
            if os.path.basename(full) in sel_basenames or full in selected:
                self.file_listbox.selection_set(i)

    def _get_selected_files(self):
        """
        获取当前在列表框中选中的文件路径列表。

        curselection() 方法返回当前选中的项目的索引元组
        比如 (0, 2, 3) 表示第 0、2、3 项被选中
        """
        return [self.all_files[i] for i in self.file_listbox.curselection()]

    def _select_all(self):
        """选中列表框中的所有项目。"""
        self.file_listbox.selection_set(0, "end")  # 从第 0 项到末尾

    def _deselect_all(self):
        """取消选中所有项目。"""
        self.file_listbox.selection_clear(0, "end")

    # ==================== 配置读写 ====================

    def _load_config(self):
        """
        把 sw.CONFIG 里的配置值显示到输入框中。

        遍历配置字段列表，根据不同的值类型做不同的处理：
          str_list: 用 ", " 连接成字符串再显示
          int/float: 转换成字符串再显示
          choice: 直接设置
        """
        cfg = sw.CONFIG  # 取核心脚本的配置字典
        for key, _, vtype in CONFIG_FIELDS:
            val = cfg[key]  # 从配置字典取值
            if vtype == "str_list":
                # 列表 → 字符串：["a", "b"] → "a, b"
                self.entries[key].set(", ".join(val))
            elif vtype == "str":
                self.entries[key].set(val)
            elif vtype in ("int", "float"):
                # 数字 → 字符串：把数字转成字符串显示
                self.entries[key].set(str(val))
            elif vtype == "choice":
                self.entries[key].set(str(val))
            elif vtype == "int_pair":
                # 列表 → 字符串：[1643, 811] → "1643, 811"
                self.entries[key].set(f"{val[0]}, {val[1]}")

    def _read_config_from_ui(self):
        """
        从输入框读取用户填写的配置，转换成正确的类型。

        返回值：
          如果所有输入都合法，返回配置字典
          如果有错误（比如整数输入了字母），弹出错误提示，返回 None

        这是"输入验证"的关键步骤：
          用户在输入框里写的是字符串
          但程序需要的是列表、整数、浮点数
          所以要一个一个转换
        """
        new_cfg = {}
        for key, _, vtype in CONFIG_FIELDS:
            # .get() 获取 StringVar 的当前值
            # .strip() 去掉首尾空格
            raw = self.entries[key].get().strip()

            if vtype == "str_list":
                # 按逗号分割字符串，去掉每个元素的空格，过滤掉空字符串
                # split(",") = 按逗号分割成列表
                # s.strip()  = 去掉每个元素的空格
                # if s.strip() 过滤掉空字符串
                parts = [s.strip() for s in raw.split(",") if s.strip()]
                new_cfg[key] = parts

            elif vtype == "str":
                new_cfg[key] = raw

            elif vtype == "int":
                try:
                    # int() 把字符串转换成整数
                    # 如果用户输入了 "abc"，int("abc") 会报 ValueError
                    new_cfg[key] = int(raw)
                except ValueError:
                    # 弹出错误消息框
                    messagebox.showerror("配置错误", f"{key} 需要填写整数")
                    return None  # 返回 None 表示转换失败

            elif vtype == "float":
                try:
                    new_cfg[key] = float(raw)
                except ValueError:
                    messagebox.showerror("配置错误", f"{key} 需要填写数字")
                    return None

            elif vtype == "choice":
                # 如果用户输入的值不在选项里，用默认值 INFO
                new_cfg[key] = raw if raw in LOG_LEVELS else "INFO"

            elif vtype == "int_pair":
                # 解析 "1643, 811" → [1643, 811]
                try:
                    parts = [int(p.strip()) for p in raw.split(",") if p.strip()]
                    if len(parts) != 2:
                        raise ValueError("需要两个整数")
                    new_cfg[key] = parts
                except (ValueError, IndexError):
                    messagebox.showerror("配置错误", f"{key} 需要两个整数，用逗号分隔（如 1643, 811）")
                    return None

        # 全角冒号转半角（避免手误输入了全角符号）
        if "send_times" in new_cfg:
            new_cfg["send_times"] = [
                t.replace("：", ":") for t in new_cfg["send_times"]
            ]

        # 把文件列表框的选中状态也加入配置
        new_cfg["txt_files"] = self._get_selected_files()

        return new_cfg

    def _apply_config(self, cfg):
        """
        把配置字典应用到 sw.CONFIG 和全局设置中。

        参数：
          cfg: 从 _read_config_from_ui() 获取的配置字典
        """
        # 更新核心脚本的 CONFIG 字典
        for key, val in cfg.items():
            sw.CONFIG[key] = val

        # 更新 pyautogui 的全局停顿时间
        # PAUSE 是 pyautogui 的全局设置
        # 每次执行一个动作（点击、按键等）后自动等待这么多秒
        # 可以通过配置 "click_delay" 来调整，默认 0.05 秒
        sw.pyautogui.PAUSE = sw.CONFIG.get("click_delay", 0.05)

        # 更新全局速度倍率
        sw.SPEED_FACTOR = sw.CONFIG.get("speed_factor", 1.0)

        # 更新日志级别
        logger = logging.getLogger()  # 获取根日志器
        # getattr(logging, "INFO") = logging.INFO = 20
        # 把字符串 "INFO" 转换成 logging 模块的常量
        logger.setLevel(getattr(logging, sw.CONFIG["log_level"]))

    def _save_config(self):
        """
        保存配置按钮的回调函数。
        读取 UI 配置 → 应用 → 持久化到文件 → 提示用户。
        """
        cfg = self._read_config_from_ui()
        if cfg is None:  # 读取失败（输入有误）
            return
        self._apply_config(cfg)
        sw.save_config_to_file()  # 保存到 data/config.json
        messagebox.showinfo("已保存", "配置已保存到文件，重启后生效")

    # ==================== 运行控制 ====================

    def _enable_stop(self, enabled=True):
        """
        启用或禁用"停止"按钮。

        参数：
          enabled: True = 启用（可点击），False = 禁用（灰色）
        """
        self.stop_btn.config(state="normal" if enabled else "disabled")

    # ==================== ESC 按键轮询 ====================
    # 从 tkinter 主线程轮询 ESC 键状态（主线程有消息队列，GetAsyncKeyState 才能正常工作）
    # 即使后台自动操作时 WeChat 窗口在最前面，ESC 也能被检测到

    def _poll_esc(self):
        """每 200ms 检查一次 ESC 是否被按下"""
        if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
            sw.STOP_EVENT.set()
            sw.logger.warning("检测到 ESC 按键，紧急停止")
            self._enable_stop(False)
            self._esc_poll_id = None
            return
        self._esc_poll_id = self.root.after(200, self._poll_esc)

    def _start_esc_polling(self):
        """启动 ESC 轮询"""
        self._stop_esc_polling()
        self._esc_poll_id = self.root.after(200, self._poll_esc)

    def _stop_esc_polling(self):
        """停止 ESC 轮询"""
        if self._esc_poll_id:
            self.root.after_cancel(self._esc_poll_id)
            self._esc_poll_id = None

    def _stop(self):
        """
        停止按钮的回调函数。
        设置 STOP_EVENT 信号，通知后台线程停止运行。
        """
        sw.STOP_EVENT.set()  # 设置"停止"信号
        sw.logger.warning("已触发停止信号，等待当前操作完成后停止...")
        self._enable_stop(False)  # 禁用停止按钮（防止重复点击）
        self._stop_esc_polling()   # 停止 ESC 轮询

    def _run_once(self):
        """
        立即运行按钮的回调函数。

        涉及多线程，需要注意：

        为什么不用单线程？
          do_send() 执行时可能需要几十分钟
          如果直接在 tkinter 主线程里执行，界面会完全卡死
          用户不能点按钮、不能关窗口、看不到日志更新

        用 threading.Thread 创建新线程：
          target=task = 新线程要执行的函数
          daemon=True = 守护线程（主程序退出时自动结束）

        try/except/finally 的作用：
          try:   尝试执行 do_send()
          except: 如果出错（停止或异常），不崩溃，只记日志
          finally: 不管成功还是出错，最后都恢复停止按钮状态

        self.root.after(0, self._enable_stop, False) 的作用：
          _enable_stop 修改了 GUI 组件状态
          但这段代码在后台线程里运行
          直接操作 GUI 组件是危险的！
          after(0, func) 把操作"扔"到 tkinter 主线程去执行
        """
        sw.STOP_EVENT.clear()  # 清除之前的停止信号（重置状态）

        cfg = self._read_config_from_ui()
        if cfg is None:
            return
        self._apply_config(cfg)

        # 清空日志区域，显示新的标题
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", ">>> 立即运行中...\n")
        self._enable_stop(True)  # 启用停止按钮
        self._start_esc_polling()  # 开始轮询 ESC 键

        def task():
            """
            后台线程要执行的函数。
            这个函数定义在 _run_once 内部，叫"嵌套函数"或"闭包"。
            它可以访问外部函数的变量（如 self）。
            """
            try:
                sw.do_send()  # 执行发送
            except (SystemExit, pyautogui.FailSafeException):
                # 用户按 ESC 或点了停止按钮
                sw.logger.warning("已停止")
            except Exception as e:
                # 其他未预料到的错误
                sw.logger.error(f"发送失败: {e}")
            finally:
                # 不管怎样，最后都要把停止按钮恢复为禁用状态
                self.root.after(0, self._enable_stop, False)
                self.root.after(0, self._stop_esc_polling)

        # 创建并启动新线程
        threading.Thread(target=task, daemon=True).start()

    def _run_daemon(self):
        """
        定时模式按钮的回调函数。
        原理和 _run_once 一样，但调用的是 sw.run_daemon()。
        """
        sw.STOP_EVENT.clear()

        cfg = self._read_config_from_ui()
        if cfg is None:
            return
        self._apply_config(cfg)

        self.log_text.delete("1.0", "end")
        self.log_text.insert(
            "end",
            f">>> 定时模式启动，发送时间: {sw.CONFIG['send_times']}\n"
        )
        self._enable_stop(True)
        self._start_esc_polling()

        def task():
            try:
                sw.run_daemon()
            except (SystemExit, pyautogui.FailSafeException):
                sw.logger.warning("已停止")
            except Exception as e:
                sw.logger.error(f"定时任务出错: {e}")
            finally:
                self.root.after(0, self._enable_stop, False)
                self.root.after(0, self._stop_esc_polling)

        threading.Thread(target=task, daemon=True).start()

    def _show_stats(self):
        """
        查看统计按钮的回调函数。
        把 sw.show_stats() 的输出重定向到日志文本框。

        StringIO 的用法：
          StringIO 是"内存中的文件"
          可以把字符串写入 StringIO，就像写入文件一样
          只不过数据存在内存里，不写硬盘

        重定向 stdout 的原理：
          1. 把 sys.stdout 临时换成 StringIO 对象
          2. 调用 show_stats()，它的 print() 输出会写入 StringIO
          3. 恢复 sys.stdout
          4. 从 StringIO 读取内容，显示到日志文本框

        try/finally 的作用：
          确保无论如何都会恢复 sys.stdout
          即使 show_stats() 出错，也不会让程序陷入"无输出"状态
        """
        self.log_text.delete("1.0", "end")

        buf = StringIO()          # 创建内存文件
        old_stdout = sys.stdout    # 保存原来的 stdout
        sys.stdout = buf           # 替换 stdout

        try:
            sw.show_stats()       # 这个函数内部用了 print()，现在会写入 buf
        finally:
            sys.stdout = old_stdout  # 恢复原来的 stdout

        self.log_text.insert("end", buf.getvalue())  # 显示统计内容

    def _setup_logging(self):
        """
        设置日志系统：把日志同时输出到 GUI 文本框。

        这里把 LogHandler 添加到两个日志器：
          1. sw.logger       = send_wechat 模块的日志器
          2. logging.getLogger() = 根日志器（捕获所有模块的日志）

        为什么加两个？
          sw.logger 只捕获 send_wechat.py 的日志
          根日志器会捕获所有模块的日志（包括 gui.py 自己的）
          这样 gui.py 里如果调用 logging.info() 也会显示在文本框里
        """
        handler = LogHandler(self.log_text)  # 创建自定义处理器
        sw.logger.addHandler(handler)        # 加到 send_wechat 的日志器
        logger = logging.getLogger()         # 获取根日志器
        logger.addHandler(handler)           # 也加到根日志器

    def run(self):
        """
        启动 GUI 程序。

        mainloop() 是 tkinter 的"主事件循环"：
          1. 显示窗口
          2. 等待用户操作（点击按钮、输入文字、拖动窗口等）
          3. 响应用户操作（调用对应的回调函数）
          4. 重复步骤 2-3，直到用户关闭窗口

        为什么叫 mainloop？
          因为它是一个无限循环：不断检查有没有事件，有就处理
          处理完一个事件又回去等下一个，永不结束（直到关窗口）

        注意：
          mainloop() 会阻塞代码执行
          它后面的代码要等窗口关闭才会运行
        """
        self.root.mainloop()


# ==================== 程序入口 ====================

if __name__ == "__main__":
    """
    只有直接运行 gui.py 时才执行这里。

    __name__ 是 Python 的特殊变量：
      - 直接运行时：__name__ = "__main__"
      - 被 import 时：__name__ = "gui"

    App().run() 做了两件事：
      1. App()     = 创建 App 类的实例（自动调用 __init__）
      2. .run()    = 调用实例的 run 方法（启动界面）
    """
    App().run()
