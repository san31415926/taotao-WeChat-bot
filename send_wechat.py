# ============================================================
# 微信定时群发工具
# ============================================================
# 原理：用 Python 模拟人的键盘和鼠标操作，自动控制微信 PC 版
# 流程：发消息给自己 → 右键菜单选"转发" → 搜索群名 → 勾选群 → 发送
#
# 本脚本不依赖微信版本，因为只是模拟按键和点击，不改微信内部数据
# 需要安装的库：pip install pyautogui pyperclip pygetwindow schedule
# ============================================================


# ==================== 第一步：导入要用到的工具库 ====================
# 库（也叫模块）就像工具箱，每个箱子里有一些现成的功能
# import 就是打开工具箱的意思

import os      # 操作文件和路径（比如找 txt 文件在哪）
import sys     # 系统和 Python 解释器相关
import time    # 时间相关（让程序等一下、获取当前时间等）
import json    # 读写 JSON 格式的数据文件（用来存发送统计）
import csv     # 导出 CSV 表格（能用 Excel 打开）
import argparse  # 解析命令行参数（比如 --once --daemon 这些）
import logging   # 日志系统（在控制台打印带时间的信息）
import threading  # 线程：自动化放后台，tkinter 界面放前台


import pyperclip          # 剪贴板操纵（复制粘贴文字）
import pyautogui          # 键盘鼠标模拟（核心自动化库）
import pygetwindow as gw  # 查找和操纵 Windows 窗口
from datetime import datetime  # 获取当前时间（年-月-日 时:分:秒）


# ==================== 第二步：pyautogui 的全局设置 ====================

# FAILSAFE = 安全开关，True 表示开启
# 当鼠标移到屏幕左上角 (0,0) 位置时，pyautogui 会立即停止所有操作并报错
# 这是防止自动化失控的安全措施——万一程序乱点，你直接把鼠标甩到左上角就能紧急停止
pyautogui.FAILSAFE = True

# PAUSE = 每个操作之间的默认停顿时间（单位：秒）
# 比如按下键盘后，等 0.1 秒再执行下一个操作
# 如果设得太短（比如 0），操作太快可能导致微信没反应过来
# 如果设得太长，整个流程会变慢
pyautogui.PAUSE = 0.1


# ==================== 第三步：配置区 ====================
# 这里是你日常需要修改的参数，改完保存文件就行
# 每一行都标明了"什么作用"和"怎么改"

CONFIG = {
    # ---------- 群名前缀 ----------
    # 你的微信群名都是 00A001xxx、00A002xxx 这种格式
    # 脚本会依次搜索每个前缀，找到对应的群并发送消息
    # 想增加前缀：在列表里加 "00A006"
    # 想减少前缀：删掉不想要的
    "group_prefixes": [
        "00A001",
        "00A002",
        "00A003",
        "00A004",
        "00A005",
        "00A006",
        "00A007",
        "00A008",
    ],

    # ---------- 每个前缀有几个群 ----------
    # 比如 00A001 开头的群有 9 个，00A002 开头的也有 9 个
    # 如果你某个前缀只有 8 个群，改成 8 就行
    "groups_per_prefix": 9,

    # ---------- 要发送的文本文件 ----------
    # 脚本会依次读取这些文件，每个文件的内容分别发送到群里
    # 文件名从大到小排列：先发 苹果17，再发 苹果16，最后发 苹果12
    # 支持两种写法：
    #   1. 相对路径（相对于脚本所在目录）："苹果17.txt"
    #   2. 绝对路径（完整的文件位置）："C:/Users/xxx/Desktop/内容.txt"
    "txt_files": [
        "苹果17.txt",
        "苹果16.txt",
        "苹果15.txt",
        "苹果14.txt",
        "苹果13.txt",
        "苹果12.txt",
    ],

    # ---------- 定时发送时间 ----------
    # 只在 --daemon 模式下生效
    # 24 小时制，格式是 "时:分"
    # 比如 "09:00" = 早上 9 点，"21:30" = 晚上 9 点半
    # 想增加或修改时间点，直接改这个列表
    "send_times": [
        "09:00",
        "12:00",
        "18:00",
    ],

    # ---------- 发完一个前缀后等几秒 ----------
    # 比如发完 00A001 的 9 个群后，等 1 秒再发 00A002
    # 设大一点（比如 3 秒）更稳定，设小一点更快
    "interval_between_groups": 1,

    # ---------- 日志详细程度 ----------
    # DEBUG：最详细，会打印每一个步骤（适合调试）
    # INFO：普通，只打印关键信息（日常用这个）
    # WARNING：只有警告才打印
    # ERROR：只有出错才打印
    "log_level": "INFO",
}


# ==================== 第四步：固定路径设置 ====================

# __file__ 是当前脚本的完整路径
# os.path.dirname 取它所在的目录
# os.path.abspath 转换成绝对路径（防止有相对路径的问题）
# 结果：SCRIPT_DIR = "C:\Users\zcxz\Desktop\脚本test"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 统计数据存放在 data/send_stats.json 文件里
# os.path.join 的作用是把目录和文件名拼成完整路径
# 结果：DATA_FILE = "C:\Users\zcxz\Desktop\脚本test\data\send_stats.json"
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "send_stats.json")


# ==================== 第五步：配置日志系统 ====================
# logging 是 Python 自带的日志工具
# 日志会在控制台打印出类似这样的信息：
#   2026-07-09 22:01:59 [INFO] [00A001] 已发送 9 个群
#
# 几个概念：
#   level     = 日志级别，低于这个级别的日志不显示
#   format    = 日志的格式，"%(asctime)s" = 时间，"%(levelname)s" = 级别
#   logger    = 日志记录器，用 logger.info() 来打印信息

logging.basicConfig(
    level=getattr(logging, CONFIG["log_level"]),
    # getattr(logging, "INFO") 相当于 logging.INFO
    # 因为 CONFIG["log_level"] 是字符串 "INFO"，需要转成 logging.INFO 这个常量

    format="%(asctime)s [%(levelname)s] %(message)s"
    # 最终显示效果：2026-07-09 22:01:59 [INFO] 你好
)

# __name__ 是当前模块的名字，这里就是 "__main__"
# 创建一个日志记录器，后面用 logger.info() 来打印信息
logger = logging.getLogger(__name__)


# ==================== 第六步：窗口管理函数 ====================

def get_window():
    """
    查找微信窗口。

    pygetwindow.getWindowsWithTitle("微信") 的作用：
      遍历系统中所有打开的窗口，找到标题包含"微信"的窗口
      返回一个列表，里面是符合条件的窗口对象

    返回值：
      如果能找到，返回第一个微信窗口对象（Win32Window 类型）
      如果找不到，返回 None

    窗口对象有这些常用属性：
      .title      窗口标题
      .left, .top   窗口左上角在屏幕上的坐标（像素）
      .width, .height 窗口的宽度和高度
      .isMinimized   是否最小化
      .visible     是否可见
    """
    wins = gw.getWindowsWithTitle("微信")
    return wins[0] if wins else None
    # 这是 Python 的"条件表达式"，相当于：
    #   if wins:        # 如果 wins 列表不为空（找到了窗口）
    #       return wins[0]  # 返回第一个窗口
    #   else:           # 如果 wins 为空（没找到）
    #       return None     # 返回空


def activate_wechat():
    """
    激活微信窗口，最大化并拉到最前面。

    用 Windows API（user32.dll）：
      ShowWindow(hwnd, SW_RESTORE) → 从托盘/最小化恢复
      ShowWindow(hwnd, SW_MAXIMIZE) → 最大化，位置固定
      SetForegroundWindow(hwnd)   → 拉到最前面

    返回值：
      True  = 成功激活
      False = 找不到微信窗口（可能没打开微信）
    """
    import ctypes

    w = get_window()
    if not w:
        logger.error("未找到微信窗口")
        return False

    hwnd = w._hWnd

    SW_RESTORE = 9    # 恢复窗口
    SW_MAXIMIZE = 3   # 最大化窗口

    is_valid = ctypes.windll.user32.IsWindow(hwnd)
    logger.debug(f"微信窗口句柄={hwnd}, 有效={is_valid}, 位置=({w.left}, {w.top})")

    if not is_valid:
        logger.error("微信窗口句柄无效")
        return False

    # 1. 恢复窗口（从托盘弹出）
    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.3)

    # 2. 最大化
    ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
    time.sleep(0.5)

    # 3. 拉到最前面
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.8)

    return True


# ==================== 第七步：读取要发送的内容 ====================

def read_txt_content(filename):
    """
    读取指定 txt 文件的内容。

    参数：
      filename: 文件名（如 "苹果17.txt"）或完整路径

    文件路径有两种写法：
      1. 相对路径：比如 "苹果17.txt"，脚本会在"自己所在的目录"找这个文件
      2. 绝对路径：比如 "C:/Users/xxx/Desktop/内容.txt"，直接去这个位置找

    编码 utf-8：中文文本的标准编码方式，如果不指定可能乱码
    f.read().strip()：读全部内容，然后去掉首尾的空格和换行

    返回值：
      文件内容（字符串），如果文件不存在则返回 None
    """
    path = filename
    if not os.path.isabs(path):  # 如果是相对路径
        path = os.path.join(SCRIPT_DIR, path)  # 拼接成绝对路径

    if not os.path.exists(path):  # 检查文件是否存在
        logger.error(f"txt 文件不存在: {path}")
        return None

    # "r" 表示以只读模式打开，encoding="utf-8" 指定编码
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()
    # with 语句的作用：不管代码是否出错，都能自动关闭文件
    # strip() 去掉首尾的空白字符（空格、换行等）


# ==================== 第八步：核心发信流程 ====================
# 整体思路：
#   1. 把要发送的内容先发给自己（给自己发一条微信消息）
#   2. 右键点击这条消息 → 选择"转发"
#   3. 在转发对话框里搜索群名前缀（如 00A001）
#   4. 展开全部搜索结果 → 勾选所有匹配的群 → 点击发送
#   5. 重复步骤 3-4，处理下一个前缀（如 00A002）
#
# 为什么先发给自己？
#   因为"转发"功能需要有一条现成的消息才行
#   我们不能凭空转发，必须先有一条消息
#   发给自己是最安全的，不会打扰别人

# 你自己的微信昵称（就是微信上显示的名字）
# 脚本会用 Ctrl+F 搜索这个名字，进入聊天窗口
# 然后往这个窗口里发消息，方便下一步右键转发
# 注意：必须和微信上显示的一模一样，包括标点符号
SELF_CHAT = "A淘淘数码-同行报价号"


def send_to_self(content):
    """
    第一步：把内容发给自己。

    具体操作（模拟人操作微信的过程）：
      1. 按 Ctrl+F 打开微信的全局搜索框
      2. 输入自己的微信昵称
      3. 按回车打开和自己的聊天窗口
      4. 把 txt 内容粘贴进去
      5. 按回车发送消息

    pyautogui 的函数说明：
      hotkey("ctrl", "f") = 同时按下 Ctrl 和 F（组合键）
      press("enter")      = 按一下回车键
      press("delete")     = 按一下删除键

    pyperclip 的作用：
      copy("文字")  = 把文字复制进剪贴板
      hotkey("ctrl", "v") = 粘贴（把剪贴板的内容贴到输入框）

    参数：
      content: 要发送的文本内容（从 txt 文件读出来的）
    """
    # ----- 按 Ctrl+F 打开微信搜索 -----
    # hotkey = "hot key" = 快捷键，同时按多个键
    # 注意：多个键用逗号分隔，字符串里不用加号
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)  # 等 0.3 秒让搜索框出来

    # ----- 清空搜索框 -----
    # Ctrl+A 全选搜索框里的内容
    pyautogui.hotkey("ctrl", "a")
    # Delete 键删除选中的内容
    pyautogui.press("delete")

    # ----- 把自己的昵称粘贴到搜索框 -----
    pyperclip.copy(SELF_CHAT)       # 复制昵称到剪贴板
    pyautogui.hotkey("ctrl", "v")   # 粘贴（相当于 Ctrl+V）
    time.sleep(0.8)                 # 等微信搜索出结果

    # ----- 回车打开聊天窗口 -----
    # 搜索出来后，第一个结果就是"我"的聊天窗口
    # 按 enter 键打开它
    pyautogui.press("enter")
    time.sleep(1.5)  # 等聊天窗口完全打开

    # ----- 把内容粘贴到输入框然后发送 -----
    pyperclip.copy(content)          # 复制要发送的文字
    pyautogui.hotkey("ctrl", "v")    # 粘贴到聊天输入框
    time.sleep(0.3)

    pyautogui.press("enter")  # 按回车发送
    time.sleep(1)             # 等消息发出去


def forward_to_groups(prefix, count):
    """
    第二步：通过"转发"功能，把消息群发到多个群。

    流程详解：
      1. 右键点击刚才发出去的那条消息 → 弹出菜单
      2. 按 5 次下箭头选到"转发" → 回车打开转发对话框
      3. 转发对话框的搜索框里会自动有焦点，粘贴群名前缀
      4. 搜索结果中按 4 次下箭头到"展开全部" → 回车展开
      5. 按 3 次上箭头回到第一个群
      6. 逐条勾选群：下箭头 + 回车（勾选）
      7. 点击"发送"按钮

    参数：
      prefix: 群名前缀，比如 "00A001"
              脚本会搜索这个前缀，找到所有匹配的群
      count:  要勾选几个群，比如 9
              如果搜索结果不足 9 个，可能会出错

    关于坐标：
      (835, 612) = 消息在屏幕上的位置（右键点击用）
      (655, 775) = "发送"按钮在屏幕上的位置
      这两个坐标是在微信窗口对齐后测出来的
      如果微信窗口位置变了，这两个坐标就不准了
    """

    # ===== 1. 右键点击消息，弹出菜单 =====
    # rightClick = 鼠标右键点击
    # 参数 (835, 612) = 屏幕上的 X 和 Y 坐标（像素）
    # 这个坐标是你之前测出来的，指向"刚发出去的那条消息"的位置
    # 如果消息位置变了，需要重新测坐标
    pyautogui.rightClick(1643, 811)
    time.sleep(0.5)  # 等 0.5 秒让菜单弹出来

    # ===== 2. 在右键菜单中选"转发" =====
    # 右键菜单会出现在鼠标位置附近
    # 菜单里有多个选项（比如：复制、转发、收藏、删除...）
    # 我们需要选"转发"，它在菜单里排在第 X 位
    # 按 5 次下箭头 = 从菜单顶部往下移 5 次
    # 具体按几次取决于你的微信版本，自己测试时调整
    for _ in range(5):
        # for _ in range(5)：循环 5 次
        # _ 是变量名，表示我们不关心循环到第几次了
        pyautogui.press("down")   # 按一下下箭头
        time.sleep(0.2)           # 等 0.2 秒让菜单项被选中
    pyautogui.press("enter")    # 回车 = 选中当前菜单项（转发）
    time.sleep(1.5)             # 等转发对话框打开

    # ===== 3. 转发对话框已打开，粘贴群名前缀 =====
    # 转发对话框打开后，焦点（光标）会自动在搜索框里
    # 我们只需要粘贴前缀进去就行
    pyperclip.copy(prefix)              # 复制前缀（如 "00A001"）
    pyautogui.hotkey("ctrl", "v")       # 粘贴到搜索框
    time.sleep(1)                       # 等搜索结果出来

    # ===== 4. 搜索"展开全部"并点击 =====
    # 在转发对话框里搜索，结果也会分页显示
    # 需要点击"展开全部"才能看到所有匹配的群
    # 这里用键盘操作：按下箭头 4 次到"展开全部"，然后回车
    # 转发对话框里的搜索没有"常用"分组干扰，所以 4 次固定有效
    for _ in range(4):
        pyautogui.press("down")   # 按一下下箭头
        time.sleep(0.2)
    pyautogui.press("enter")    # 展开全部
    time.sleep(1.5)             # 等全部结果加载出来

    # ===== 5. 回到第一个群 =====
    # "展开全部"点击后，光标焦点在列表最末尾
    # 按 3 次上箭头，把光标移到第一个群
    for _ in range(3):
        pyautogui.press("up")     # 按一下上箭头
        time.sleep(0.2)

    # ===== 6. 逐个勾选所有群 =====
    # 用回车键来"勾选/选中"当前高亮的群
    # 勾选后自动跳到下一个（或者用下箭头手动跳到下一个）
    # 循环 count 次 = 勾选 count 个群
    for i in range(count):
        if i > 0:  # 第一个群已经定位好了，不用再按
            pyautogui.press("down")   # 移到下一个群
            time.sleep(0.2)
        pyautogui.press("enter")      # 勾选这个群
        time.sleep(0.2)

    # ===== 7. 点击"发送"按钮 =====
    # 勾选完所有群后，点击转发对话框里的"发送"按钮
    # (655, 775) 是你测出来的发送按钮坐标
    time.sleep(0.5)
    pyautogui.click(1055, 763)  # 鼠标左键点击
    time.sleep(1)              # 等发送完成


def send_to_prefix_groups(prefix, count, content):
    """
    对一个前缀执行完整的发送流程。

    完整流程：
      1. 激活微信窗口
      2. 把内容发给自己（send_to_self）
      3. 在转发对话框中搜索并发送（forward_to_groups）
      4. 记录日志

    参数：
      prefix:  群名前缀（如 "00A001"）
      count:   每个前缀有几个群（如 9）
      content: 要发送的文本内容

    返回值：
      成功发送的群数量（如果失败返回 0）
    """
    if not activate_wechat():  # 微信没开就退出
        return 0

    send_to_self(content)                # 发消息给自己
    forward_to_groups(prefix, count)     # 转发到群

    logger.info(f"[{prefix}] 已发送 {count} 个群")
    return count


def send_to_all(content):
    """
    遍历 CONFIG 里的所有前缀，逐个发送。

    流程：
      1. 先激活微信
      2. 对于每一个前缀（如 00A001、00A002...）
      3.    执行：发给自己 → 转发 → 勾选 → 发送
      4.    如果某个前缀失败，记下来但不影响下一个

    参数：
      content: 要发送的文本内容

    返回值：
      (成功数, 失败数)
    """
    if not activate_wechat():
        return 0, 0

    total = 0    # 总计发送的群数量
    failed = 0   # 发送失败的群数量

    # 遍历 CONFIG["group_prefixes"] 列表里的每一个前缀
    for prefix in CONFIG["group_prefixes"]:
        try:
            # try: 尝试执行，如果出错会跳到 except
            n = send_to_prefix_groups(
                prefix,           # 当前前缀
                CONFIG["groups_per_prefix"],  # 每个前缀的群数
                content           # 要发的内容
            )
            total += n  # 累加成功数
        except Exception as e:
            # 如果 send_to_prefix_groups 里出了任何错误
            # 就执行这里，不会让整个程序崩溃
            logger.error(f"前缀 {prefix} 发送失败: {e}")
            failed += CONFIG["groups_per_prefix"]

    return total, failed


# ==================== 第九步：数据统计功能 ====================
# 每次发送后，脚本会记录：什么时间、发了多少群、成功失败各多少
# 这些数据保存在 data/send_stats.json 文件里
# 可以用 --stats 查看，用 --export 导出到 Excel


def load_stats():
    """
    从 JSON 文件加载发送统计。
    如果文件不存在，返回默认的空数据。

    JSON = JavaScript Object Notation
    一种轻量级的数据存储格式，类似 Python 的字典

    返回的字典结构：
    {
        "total_sends": 5,     # 总共发了几次
        "last_send": "2026-...",  # 最后一次发送的时间
        "history": [           # 历史记录列表
            {"time": "...", "success": 9, "fail": 0, "total": 9},
            ...
        ]
    }
    """
    # 默认数据（第一次运行时用）
    stats = {
        "total_sends": 0,    # 总发送次数
        "last_send": None,    # 最后发送时间
        "history": []         # 发送历史列表
    }

    if os.path.exists(DATA_FILE):  # 检查文件是否存在
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)  # 从 JSON 文件读取并转成 Python 字典
        except Exception:
            pass  # 读文件出错就用默认数据

    return stats


def save_stats(stats):
    """
    保存发送统计到 JSON 文件。

    参数：
      stats: 要保存的统计数据（字典）
    """
    # os.makedirs 创建目录（如果不存在的话）
    # exist_ok=True 表示如果目录已经存在，不报错
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        # json.dump = 把 Python 字典变成 JSON 字符串写入文件
        # ensure_ascii=False 保证中文不乱码
        # indent=2 让 JSON 文件格式好看（每层缩进 2 空格）
        json.dump(stats, f, ensure_ascii=False, indent=2)


def show_stats():
    """
    在控制台显示发送统计信息。
    只显示最近 10 条历史记录。
    """
    stats = load_stats()
    print(f"总发送次数: {stats['total_sends']}")
    print(f"最后发送: {stats.get('last_send', '无')}")
    # .get() 是字典的方法：如果 'last_send' 存在就返回它，不存在返回 '无'

    print("发送历史:")
    # history[-10:] = 取列表的最后 10 个元素
    # [-10:] 是 Python 的切片语法，表示从倒数第 10 个到末尾
    for h in stats.get("history", [])[-10:]:
        print(f"  {h['time']} | 成功 {h['success']} 失败 {h['fail']} | 群数 {h['total']}")


def export_csv(path):
    """
    导出统计到 CSV 文件，可以用 Excel 打开。

    CSV = Comma-Separated Values，逗号分隔的值
    是一种通用表格格式

    参数：
      path: 要保存的文件路径（如 "统计.csv"）
    """
    stats = load_stats()

    # newline="" 避免 CSV 里出现多余的空行
    # encoding="utf-8-sig" 加上 BOM 头，Excel 打开不乱码
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)  # 创建一个 CSV 写入器

        # writerow = write a row = 写一行
        writer.writerow(["时间", "成功", "失败", "总群数"])  # 表头

        for h in stats.get("history", []):
            writer.writerow([h["time"], h["success"], h["fail"], h["total"]])

    logger.info(f"已导出统计到 {path}")


# ==================== 第十步：执行一次完整发送 ====================

def do_send(verbose=False):
    """
    执行一次完整的发送流程。

    步骤：
      1. 遍历 CONFIG 里所有 txt 文件（从苹果17到苹果12）
      2. 对每个文件：读取内容 → 发给自己 → 转发到所有前缀的群
      3. 记录本次发送的统计数据
      4. 保存统计到 JSON 文件

    参数：
      verbose: 是否显示详细输出（-v 参数开启）
    """
    grand_total = 0      # 所有文件加起来的群数
    grand_failed = 0     # 所有文件加起来的失败数

    # 遍历 CONFIG 里配置的所有 txt 文件
    for filename in CONFIG["txt_files"]:
        content = read_txt_content(filename)
        if not content:  # 如果这个文件不存在或为空，跳过
            logger.warning(f"文件 {filename} 不存在或为空，跳过")
            continue

        if verbose:
            print(f"--- [{filename}] 发送内容 ---\n{content}\n---------------")

        logger.info(f"开始发送文件: {filename}")

        # 对这个文件的内容执行：发给自己 → 转发到所有前缀的群
        total, failed = send_to_all(content)

        grand_total += total
        grand_failed += failed

        # 文件之间等一会，给微信反应时间
        time.sleep(CONFIG["interval_between_groups"])

    # ----- 记录本次发送统计 -----
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # strftime = string format time = 把时间格式化成字符串
    # "%Y" = 年(4位)  "%m" = 月(2位)  "%d" = 日(2位)
    # "%H" = 时(24h) "%M" = 分(2位)  "%S" = 秒(2位)

    stats = load_stats()
    stats["total_sends"] += 1                                  # 发送次数 +1
    stats["last_send"] = now                                   # 更新最后发送时间
    stats["history"].append({                                  # 添加一条记录
        "time": now,
        "success": grand_total - grand_failed,  # 成功数
        "fail": grand_failed,                    # 失败数
        "total": grand_total                     # 总群数
    })
    save_stats(stats)

    logger.info(f"全部文件发送完成: 成功 {grand_total - grand_failed}, 失败 {grand_failed}, 总计 {grand_total}")


# ==================== 第十一步：定时任务模式 ====================

def run_daemon():
    """
    定时守护进程模式。

    作用：
      按 CONFIG['send_times'] 设定的时间，每天自动执行发送。
      比如设了 09:00、12:00、18:00，就会每天这三个时间各发一次。

    实现：
      使用 schedule 库（一个轻量级的定时任务库）
      schedule.every().day.at("09:00").do(do_send)
      = 每天的 09:00 执行 do_send 函数

    守护进程启动后：
      1. 先立即执行一次（方便测试）
      2. 然后进入循环，每 30 秒检查一次有没有到点的任务
    """
    # 注意：schedule 库需要在 pip install 时单独安装
    import schedule  # 只在需要时导入，不用每次都加载

    # 遍历 CONFIG 里设置的所有时间点
    for t in CONFIG["send_times"]:
        # 注册定时任务：每天 t 时刻执行 do_send 函数
        schedule.every().day.at(t).do(do_send)
        logger.info(f"已设定定时任务: {t}")

    logger.info(f"守护进程启动中，定时发送时间: {CONFIG['send_times']}")

    do_send()  # 立即执行一次（启动时先跑一遍）

    # 无限循环：反复检查有没有到点的任务
    while True:
        schedule.run_pending()  # 执行所有到点的任务
        time.sleep(30)          # 每 30 秒检查一次，省 CPU


# ==================== 第十二步：运行时绿色参考框 ====================
# 在屏幕中央显示"发送中"提示，方便你看到脚本在运行


def create_overlay():
    """
    在屏幕中央显示"发送中"提示框。
    主线程跑 tkinter 事件循环，自动化在后台线程跑。
    发送完后自动关闭。
    """
    import tkinter as tk

    root = tk.Tk()
    root.title("发送中")
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", "white")
    root.overrideredirect(True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.geometry(f"{screen_w}x{screen_h}+0+0")

    canvas = tk.Canvas(root, highlightthickness=0, bg="white")
    canvas.pack(fill="both", expand=True)

    canvas.create_text(
        screen_w // 2, screen_h // 2,
        text="微信群发脚本运行中...\n发送完成后自动关闭",
        fill="#00ff00", font=("Microsoft YaHei", 20, "bold"),
        justify="center"
    )

    return root


# ==================== 第十三步：命令行入口 ====================

def get_position():
    """
    鼠标坐标测量工具。
    实时显示鼠标在屏幕上的位置，把鼠标停到目标位置读坐标就行。
    按 Ctrl+C 退出。

    用法：python send_wechat.py --getpos
    """
    print("=" * 50)
    print("坐标测量工具")
    print("  把鼠标移到目标位置，控制台会显示坐标")
    print("  记下坐标后填到脚本里")
    print("  按 Ctrl+C 退出")
    print("=" * 50)
    print()

    last_pos = None
    try:
        while True:
            x, y = pyautogui.position()
            if (x, y) != last_pos:
                print(f"\r鼠标: ({x:4d}, {y:4d})    ", end="")
                last_pos = (x, y)
    except KeyboardInterrupt:
        print("\n\n已退出")


def main():
    """
    命令行入口。

    支持的命令：
      python send_wechat.py --once         # 立即执行一次发送
      python send_wechat.py --daemon       # 启动定时发送
      python send_wechat.py --stats        # 查看发送统计
      python send_wechat.py --export 1.csv # 导出统计到 Excel
      python send_wechat.py --getpos       # 测坐标工具
      python send_wechat.py -v --once      # 详细模式

    不传参数时弹出菜单让你选。
    """
    parser = argparse.ArgumentParser(description="微信定时群发工具")
    parser.add_argument("--once", action="store_true", help="立即执行一次发送")
    parser.add_argument("--daemon", action="store_true", help="启动定时守护进程")
    parser.add_argument("--stats", action="store_true", help="显示发送统计")
    parser.add_argument("--export", type=str, help="导出统计到 CSV 文件（如 --export 统计.csv）")
    parser.add_argument("--getpos", action="store_true", help="测坐标：移到目标位置按 F6 记录")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志模式")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            h.setLevel(logging.DEBUG)

    if args.getpos:
        get_position()
    elif args.stats:
        show_stats()
    elif args.export:
        export_csv(args.export)
    elif args.daemon:
        root = create_overlay()
        t = threading.Thread(target=run_daemon, daemon=True)
        t.start()
        root.mainloop()
    elif args.once:
        root = create_overlay()
        def send_thread():
            try:
                do_send(verbose=args.verbose)
            finally:
                root.after(0, root.destroy)
        t = threading.Thread(target=send_thread, daemon=True)
        t.start()
        root.mainloop()
    else:
        print("=" * 50)
        print("  微信定时群发工具")
        print("=" * 50)
        print(f"  定时时间: {', '.join(CONFIG['send_times'])}")
        print(f"  群前缀: {', '.join(CONFIG['group_prefixes'])}")
        print(f"  发送文件: {', '.join(CONFIG['txt_files'])}")
        print("=" * 50)
        print()
        print("请选择运行模式：")
        print("  [1] 定时模式 — 按设定时间自动发送")
        print("  [2] 立即运行 — 立刻执行一次发送")
        print("  [q] 退出")
        print()
        choice = input("请输入 (1/2/q): ").strip()

        if choice == "1":
            root = create_overlay()
            t = threading.Thread(target=run_daemon, daemon=True)
            t.start()
            root.mainloop()
        elif choice == "2":
            root = create_overlay()
            def send_thread():
                try:
                    do_send()
                finally:
                    root.after(0, root.destroy)
            t = threading.Thread(target=send_thread, daemon=True)
            t.start()
            root.mainloop()
        else:
            print("已退出")


# ==================== 第十四步：程序入口 ====================
#
# __name__ 是 Python 的一个特殊变量：
#   - 当你直接运行这个文件时，__name__ = "__main__"
#   - 当你用 import 导入这个文件时，__name__ = "send_wechat"
#
# if __name__ == "__main__" 的意思是：
#   只有直接运行这个脚本时才执行 main()
#   如果被其他文件 import，不会自动运行
#
# 这样设计的目的是：
#   别人可以用 import send_wechat 来引入这里的函数
#   而不会一引入就自动开始发消息

if __name__ == "__main__":
    main()
