# ============================================================
# 微信定时群发工具
# ============================================================
# 本软件由 淘淘数码 研发，版权归 淘淘数码 所有。
# 仅限于授权用户内部使用，禁止用于任何商业用途。
# 未经许可，禁止复制、修改、分发或转售。
# 解释权归 淘淘数码 所有。
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
from dataclasses import dataclass

import pyperclip          # 剪贴板操纵（复制粘贴文字）
import pyautogui          # 键盘鼠标模拟（核心自动化库）
import pygetwindow as gw  # 查找和操纵 Windows 窗口
from datetime import datetime  # 获取当前时间（年-月-日 时:分:秒）


TEXT_EXTENSIONS = {".txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"
}


@dataclass(frozen=True)
class SendFile:
    """A selected text, image, or video file ready for the send pipeline."""

    name: str
    kind: str
    path: str
    content: str | None = None


@dataclass(frozen=True)
class SendBatch:
    """One product folder whose items must be sent in the listed order."""

    name: str
    files: tuple[SendFile, ...]


# ==================== 第二步：pyautogui 的全局设置 ====================

# FAILSAFE = 安全开关，设为 True 作为备用紧急停止方式
# 主要用 ESC 键停止，但如果 ESC 没生效，鼠标移到左上角 (0,0) 也能触发停止
# 这是双重保险，防止自动化失控
pyautogui.FAILSAFE = True


# ==================== 紧急停止 ====================
import threading
import ctypes

STOP_EVENT = threading.Event()
SPEED_FACTOR = 1.0  # 会被 CONFIG["speed_factor"] 覆盖

_time_sleep = time.sleep


def _is_esc_pressed():
    """
    检测 ESC 键是否被按下（非阻塞，无需额外库）。

    原理：
      用 Windows API 的 GetAsyncKeyState 检测键盘状态
      0x1B 是 ESC 键的虚拟键码（Virtual Key Code）
      GetAsyncKeyState 返回一个 16 位的整数
      如果最高位（bit 15）是 1，表示按键当前被按下
      用 & 0x8000 提取最高位

    优点：
      - 不依赖额外库（不用 pip install keyboard）
      - 非阻塞，瞬间返回 True/False
      - 全局检测，不管窗口焦点在哪都有效
    """
    return (ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000) != 0


def _safe_sleep(seconds):
    actual = seconds * SPEED_FACTOR
    end = time.monotonic() + actual
    while time.monotonic() < end:
        # 检测 ESC 键——按一下就触发紧急停止
        # 比鼠标移到左上角更快速、更顺手
        if _is_esc_pressed():
            STOP_EVENT.set()
        if STOP_EVENT.is_set():
            raise SystemExit("紧急停止: 已触发停止信号")
        _time_sleep(min(0.1, end - time.monotonic()))


time.sleep = _safe_sleep


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

    # ---------- 要发送的文件列表（为空则自动选择所有支持的文件） ----------
    # 支持 TXT、图片和视频；只存文件名，不存完整路径
    "send_files": [
        "苹果17.txt",
        "苹果16.txt",
        "苹果15.txt",
        "苹果14.txt",
        "苹果13.txt",
        "苹果12.txt",
    ],
    # 旧版配置名，保留用于兼容已有配置文件
    "txt_files": [
        "苹果17.txt",
        "苹果16.txt",
        "苹果15.txt",
        "苹果14.txt",
        "苹果13.txt",
        "苹果12.txt",
    ],
    # 产品文件夹列表。每个文件夹内必须有一个 TXT 和一张图片或一个视频。
    # 为空时自动扫描脚本目录下所有符合条件的文件夹。
    "send_folders": [],

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

    # ---------- 全局速度倍率 ----------
    # 1.0=正常，0.5=2倍速，0.3=3倍速，0.2=极速
    # 所有等待时间都会乘以这个值，调低总耗时大幅缩短
    "speed_factor": 0.5,

    # ---------- 发完一个前缀后等几秒 ----------
    # 比如发完 00A001 的 9 个群后，等 1 秒再发 00A002
    # 设大一点（比如 3 秒）更稳定，设小一点更快
    "interval_between_groups": 1,

    # ---------- 每个文件的发送间隔 ----------
    # 发完一个 TXT 文件后等多久再发下一个
    # 支持格式：30s（秒）、5m（分钟）、1h（小时）
    # 设成 0s 表示不等待
    "interval_between_files": "3m",
    # 视频转发完成并发送到全部群后，等待多久再处理下一组内容。
    # 支持格式：30s（秒）、5m（分钟）、1h（小时）。
    "video_next_step_wait": "3m",

    # ---------- 鼠标点击坐标（相对于微信窗口左上角） ----------
    # 如果你的微信窗口在屏幕左上角 (0,0) 位置，那这些值就和旧版坐标一样
    # 换电脑或改分辨率后，运行 python send_wechat.py --align 重新校准
    # click_msg_offset  = 右键点击消息的位置
    # click_send_offset = 点击"发送"按钮的位置
    "click_msg_offset": [1643, 811],
    "click_send_offset": [1055, 763],
    # 粘贴图片/视频后，等待微信生成待发送卡片的秒数
    "media_prepare_wait": 2,
    # 图片/视频发送后，等待微信完成上传的秒数
    "media_upload_wait": 3,

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
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 统计数据存放在 data/send_stats.json 文件里
# os.path.join 的作用是把目录和文件名拼成完整路径
# 结果：DATA_FILE = "C:\Users\zcxz\Desktop\脚本test\data\send_stats.json"
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "send_stats.json")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "data", "config.json")


def save_config_to_file():
    """把当前 CONFIG 保存到 data/config.json"""
    cleaned = {
        k: [t.replace("：", ":") for t in v] if k == "send_times" else v
        for k, v in CONFIG.items()
    }
    selected = cleaned.get("send_files", cleaned.get("txt_files", []))
    selected = [os.path.basename(f) for f in selected]
    cleaned["send_files"] = selected
    # 保留旧键，便于旧版程序继续读取配置
    cleaned["txt_files"] = list(selected)
    cleaned["send_folders"] = [
        os.path.basename(folder) for folder in cleaned.get("send_folders", [])
    ]
    CONFIG.update(cleaned)
    pyautogui.PAUSE = CONFIG.get("click_delay", 0.05)
    global SPEED_FACTOR; SPEED_FACTOR = CONFIG.get("speed_factor", 1.0)
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    try:
        logger.info("配置已保存到文件")
    except NameError:
        print("配置已保存到文件")


def load_config_from_file():
    """从 data/config.json 加载配置（如果存在）"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if "send_files" not in saved and "txt_files" in saved:
                saved["send_files"] = list(saved["txt_files"])
            if "txt_files" not in saved and "send_files" in saved:
                saved["txt_files"] = list(saved["send_files"])
            saved["send_times"] = [t.replace("：", ":") for t in saved.get("send_times", [])]
            CONFIG.update(saved)
            try:
                logger.info("已加载配置文件")
            except NameError:
                pass
        except Exception as e:
            try:
                logger.warning(f"配置文件加载失败: {e}")
            except NameError:
                pass


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


# 启动时自动加载保存的配置
load_config_from_file()

# 应用全局速度
pyautogui.PAUSE = CONFIG.get("click_delay", 0.05)
SPEED_FACTOR = CONFIG.get("speed_factor", 1.0)


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
      .width, .height 窗口的宽度和高度12
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
    """
    import ctypes

    SW_RESTORE = 9
    SW_MAXIMIZE = 3

    hwnd = ctypes.windll.user32.FindWindowW("WeChatMainWndForPC", None)
    if not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "微信")
    if not hwnd:
        w = get_window()
        if w:
            hwnd = w._hWnd

    if not hwnd:
        logger.error("未找到微信窗口，请确认微信已登录")
        return False

    logger.info(f"找到微信窗口")

    ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.2)
    ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
    time.sleep(0.3)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)

    return True


# ==================== 第七步：读取要发送的内容 ====================

def classify_media_file(path):
    """Return ``text``, ``image`` or ``video`` for a supported file."""
    extension = os.path.splitext(os.fspath(path))[1].lower()
    if extension in TEXT_EXTENSIONS:
        return "text"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(f"不支持的文件类型: {path}")


def get_available_files():
    """Return supported text, image, and video file names in the script folder."""
    files = []
    if os.path.isdir(SCRIPT_DIR):
        for entry in os.scandir(SCRIPT_DIR):
            if not entry.is_file():
                continue
            try:
                classify_media_file(entry.name)
            except ValueError:
                continue
            files.append(entry.name)
    return sorted(set(files), reverse=True)


def get_available_txt_files():
    """Backward-compatible alias for the expanded file discovery function."""
    return get_available_files()


def _selected_file_names():
    selected = CONFIG.get("send_files")
    if selected is None:
        selected = CONFIG.get("txt_files", [])
    return selected


def _read_send_file(path):
    """Load one supported file into the representation used by the send flow."""
    path = os.path.abspath(os.fspath(path))
    kind = classify_media_file(path)
    if kind == "text":
        with open(path, "r", encoding="utf-8") as file:
            content = file.read().strip()
        if not content:
            return None
    else:
        content = None
    return SendFile(
        name=os.path.basename(path),
        kind=kind,
        path=path,
        content=content,
    )


def read_selected_files():
    """
    读取配置中选中的文本、图片和视频文件。
    如果列表为空，则自动使用目录中的所有支持文件。

    返回值：
      [SendFile(...), ...]
    """
    selected = _selected_file_names()
    if not selected:
        selected = get_available_files()

    result = []
    for name in selected:
        path = os.path.join(SCRIPT_DIR, name)
        if not os.path.isfile(path):
            logger.warning(f"文件不存在，跳过: {name}")
            continue
        try:
            item = _read_send_file(path)
        except ValueError as exc:
            logger.warning(str(exc))
            continue
        if not item:
            logger.warning(f"文件内容为空，跳过: {name}")
            continue
        result.append(item)
        logger.info(f"读取文件: {name} ({item.kind})")
    return result


def _build_send_batch(folder_path):
    """Build one text-then-image-or-video product batch from a folder."""
    folder_path = os.path.abspath(os.fspath(folder_path))
    text_files = []
    media_files = []
    for entry in os.scandir(folder_path):
        if not entry.is_file():
            continue
        try:
            item = _read_send_file(entry.path)
        except ValueError:
            continue
        if not item:
            continue
        if item.kind == "text":
            text_files.append(item)
        elif item.kind in {"image", "video"}:
            media_files.append(item)

    if len(text_files) != 1 or len(media_files) != 1:
        raise ValueError(
            f"文件夹 {os.path.basename(folder_path)} 必须包含一个非空 TXT 和一张图片或一个视频"
        )
    return SendBatch(
        name=os.path.basename(folder_path),
        files=(text_files[0], media_files[0]),
    )


def get_available_send_folders():
    """Return product folders containing exactly one TXT and one image or video."""
    folders = []
    if not os.path.isdir(SCRIPT_DIR):
        return folders
    for entry in os.scandir(SCRIPT_DIR):
        if not entry.is_dir():
            continue
        try:
            _build_send_batch(entry.path)
        except ValueError:
            continue
        folders.append(entry.name)
    return sorted(folders, reverse=True)


def read_selected_batches():
    """Load selected product folders, preserving text-before-video ordering."""
    selected = CONFIG.get("send_folders", [])
    folder_names = selected if selected else get_available_send_folders()
    if folder_names:
        batches = []
        for name in folder_names:
            folder_path = os.path.join(SCRIPT_DIR, name)
            if not os.path.isdir(folder_path):
                logger.warning(f"文件夹不存在，跳过: {name}")
                continue
            try:
                batch = _build_send_batch(folder_path)
            except ValueError as exc:
                logger.warning(str(exc))
                continue
            batches.append(batch)
            logger.info(f"读取发送组合: {batch.name}")
        return batches

    # 兼容旧版根目录文本、图片和视频文件。
    return [SendBatch(name=item.name, files=(item,)) for item in read_selected_files()]


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
SELF_CHAT = "A淘淘数码-同行号1 (支持闲鱼）"


def _wait_unscaled(seconds):
    """Wait in real seconds while still honoring the stop signal."""
    end = time.monotonic() + max(0, float(seconds))
    while time.monotonic() < end:
        if STOP_EVENT.is_set():
            raise SystemExit("紧急停止: 已触发停止信号")
        _time_sleep(min(0.1, end - time.monotonic()))


def _open_self_chat():
    """Open the configured self chat and leave focus in its input area."""
    logger.info("  -> 打开搜索")
    pyautogui.hotkey("ctrl", "f")
    _wait_unscaled(0.5)

    logger.info("  -> 清空搜索框")
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("delete")

    logger.info("  -> 粘贴昵称")
    pyperclip.copy(SELF_CHAT)
    pyautogui.hotkey("ctrl", "v")
    _wait_unscaled(1)

    logger.info("  -> 回车打开聊天")
    pyautogui.press("enter")
    _wait_unscaled(2)


def send_to_self(content):
    """Send a text message to the configured self chat."""
    _open_self_chat()

    logger.info("  -> 粘贴内容并发送")
    pyperclip.copy(content)
    pyautogui.hotkey("ctrl", "v")
    _wait_unscaled(0.5)

    pyautogui.press("enter")
    _wait_unscaled(1.5)


def set_clipboard_files(paths):
    """Put Windows file-drop data on the clipboard for WeChat Ctrl+V."""
    paths = [os.path.abspath(os.fspath(path)) for path in paths]
    if not paths:
        raise ValueError("至少需要一个文件路径")
    for path in paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    class DROPFILES(ctypes.Structure):
        _fields_ = [
            ("pFiles", ctypes.c_uint),
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
            ("fNC", ctypes.c_int),
            ("fWide", ctypes.c_bool),
        ]

    dropfiles = DROPFILES()
    dropfiles.pFiles = ctypes.sizeof(DROPFILES)
    dropfiles.fWide = True
    file_data = ("\0".join(path.replace("/", "\\") for path in paths) + "\0\0").encode("utf-16-le")
    clipboard_data = bytes(dropfiles) + file_data

    import win32clipboard

    deadline = time.monotonic() + 10
    while True:
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, clipboard_data)
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"设置文件剪贴板超时: {paths}")
            _time_sleep(0.1)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass


def send_media_to_self(path):
    """Send one image or video to the configured self chat."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if classify_media_file(path) not in {"image", "video"}:
        raise ValueError(f"不是图片或视频文件: {path}")

    _open_self_chat()
    logger.info(f"  -> 选择媒体文件: {os.path.basename(path)}")
    set_clipboard_files([path])
    pyautogui.hotkey("ctrl", "v")
    _wait_unscaled(CONFIG.get("media_prepare_wait", 2))
    pyautogui.press("enter")
    _wait_unscaled(CONFIG.get("media_upload_wait", 3))


def forward_to_groups(prefix, count, media=False):
    """
    第二步：通过"转发"功能，把消息群发到多个群。

    流程详解：
       1. 右键点击刚才发出去的那条消息 → 弹出菜单
       2. 文字按 5 次下箭头选到"转发"；视频按 3 次下箭头选到"转发"
       3. 转发对话框的搜索框里会自动有焦点，粘贴群名前缀
       4. 搜索结果中按 4 次下箭头到"展开全部" → 回车展开
       5. 按 3 次上箭头回到第一个群
       6. 逐条勾选群：下箭头 + 回车（勾选）
       7. 点击"发送"按钮

    参数：
      prefix: 群名前缀，比如 "00A001"
      count:  要勾选几个群，比如 9

    关于坐标：
      坐标是相对于微信窗口左上角的位置偏移
      这样不管微信窗口在屏幕哪个位置，鼠标都能点对地方
      换电脑后用 --align 重新校准
    """

    # 获取当前微信窗口位置
    w = get_window()
    if not w:
        logger.error("微信窗口未找到，无法获取坐标")
        return

    msg_off = CONFIG["click_msg_offset"]
    send_off = CONFIG["click_send_offset"]

    # ===== 1. 右键点击消息，弹出菜单 =====
    pyautogui.rightClick(w.left + msg_off[0], w.top + msg_off[1])
    time.sleep(0.5)

    # ===== 2. 在右键菜单中选"转发" =====
    # 文字/图片菜单需要 5 次下移；视频菜单按截图中的顺序需要 3 次下移。
    menu_down_count = 3 if media else 5
    for _ in range(menu_down_count):
        pyautogui.press("down")
        time.sleep(0.2)
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
    # 用配置里的坐标偏移 + 窗口当前位置
    time.sleep(0.5)
    pyautogui.click(w.left + send_off[0], w.top + send_off[1])
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
    send_to_self(content)                # 发消息给自己
    forward_to_groups(prefix, count)     # 转发到群

    logger.info(f"[{prefix}] 已发送 {count} 个群")
    return count


def send_media_to_prefix_groups(prefix, count, path):
    """Send one image or video to all groups matching one prefix."""
    send_media_to_self(path)
    forward_to_groups(prefix, count, media=classify_media_file(path) == "video")
    logger.info(f"[{prefix}] 已发送媒体文件 {os.path.basename(path)} 到 {count} 个群")
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


def send_media_to_all(path):
    """Send one image or video to every configured group prefix."""
    if not activate_wechat():
        return 0, 0

    total = 0
    failed = 0
    for prefix in CONFIG["group_prefixes"]:
        try:
            total += send_media_to_prefix_groups(
                prefix, CONFIG["groups_per_prefix"], path
            )
        except Exception as exc:
            logger.error(f"媒体文件 {os.path.basename(path)} 在前缀 {prefix} 发送失败: {exc}")
            failed += CONFIG["groups_per_prefix"]

    return total, failed


def send_batch_to_all(batch):
    """Send every item in one batch to each prefix before moving to the next."""
    if not activate_wechat():
        return 0, 0

    total = 0
    failed = 0
    groups_per_prefix = CONFIG["groups_per_prefix"]
    for prefix in CONFIG["group_prefixes"]:
        for item in batch.files:
            try:
                logger.info(f"[{prefix}] 开始发送文件: {item.name}")
                if item.kind == "text":
                    total += send_to_prefix_groups(
                        prefix, groups_per_prefix, item.content or ""
                    )
                else:
                    total += send_media_to_prefix_groups(
                        prefix, groups_per_prefix, item.path
                    )
            except Exception as exc:
                logger.error(f"文件 {item.name} 在前缀 {prefix} 发送失败: {exc}")
                failed += groups_per_prefix

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


# ==================== 第十步：时间间隔解析工具 ====================

def parse_interval(text):
    """
    把 "30s"、"5m"、"1h" 这样的字符串转成秒数。

    支持格式：
      "30s" → 30 秒      （s = seconds）
      "5m"  → 300 秒     （m = minutes）
      "1h"  → 3600 秒    （h = hours）
      "0"   → 0 秒       （纯数字也兼容）
      ""    → 0 秒       （空字符串也兼容）

    实现原理：
      1. 去掉首尾空格
      2. 看最后一个字符是不是 s/m/h 之一
      3. 如果是，把前面的数字部分取出来，乘以对应倍数
      4. 如果不是，直接当秒数解析
    """
    text = text.strip()
    if not text:
        return 0

    unit = text[-1].lower()  # 取最后一个字符，转小写
    if unit == "s":
        return int(text[:-1])
    elif unit == "m":
        return int(text[:-1]) * 60
    elif unit == "h":
        return int(text[:-1]) * 3600
    else:
        return int(text)


# ==================== 第十一步：执行一次完整发送 ====================

def do_send(verbose=False):
    """
    执行一次完整的发送流程。

    步骤：
      1. 扫描目录下所有 .txt 文件
      2. 对每个文件：读取内容 → 发到所有前缀的群
      3. 记录本次发送的统计数据
      4. 保存统计到 JSON 文件

    参数：
      verbose: 是否显示详细输出（-v 参数开启）
    """
    batches = read_selected_batches()
    if not batches:
        logger.warning("没有找到要发送的文件夹组合或文件")
        return

    grand_total = 0
    grand_failed = 0

    for idx, batch in enumerate(batches):
        logger.info(f"开始发送组合: {batch.name}")
        for item in batch.files:
            if verbose:
                detail = item.content if item.kind == "text" else item.path
                print(f"--- [{batch.name}/{item.name}] {item.kind} ---\n{detail}\n---------------")

        total, failed = send_batch_to_all(batch)
        grand_total += total
        grand_failed += failed

        # 如果不是最后一组，按设定的间隔等待再处理下一组。
        # 视频优先使用独立的“视频转发完成后等待”设置。
        # 注意：文件间隔是真实时间，不应该被 speed_factor 缩放
        # 所以不用 time.sleep（已被 _safe_sleep 替换）
        # 而是用原始 sleep + 每秒检测一次停止信号
        if idx < len(batches) - 1:
            is_video_batch = batch.files[-1].kind == "video"
            interval_key = (
                "video_next_step_wait"
                if is_video_batch
                else "interval_between_files"
            )
            interval = parse_interval(CONFIG[interval_key])
            if interval > 0:
                reason = "视频转发完成" if is_video_batch else "当前组合发送完成"
                logger.info(f"{reason}，等待 {interval} 秒后发送下一组...")
                remaining = interval
                while remaining > 0:
                    if STOP_EVENT.is_set():
                        logger.warning("停止信号触发，终止发送")
                        save_stats({
                            "total_sends": 0,
                            "last_send": None,
                            "history": []
                        })
                        return
                    chunk = min(1.0, remaining)
                    _time_sleep(chunk)
                    remaining -= chunk

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats = load_stats()
    stats["total_sends"] += 1
    stats["last_send"] = now
    stats["history"].append({
        "time": now,
        "success": grand_total - grand_failed,
        "fail": grand_failed,
        "total": grand_total
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

    # 无限循环：反复检查有没有到点的任务
    while not STOP_EVENT.is_set():
        schedule.run_pending()  # 执行所有到点的任务
        time.sleep(3)           # 每 3 秒检查一次，点了停止最多等 3 秒


# ==================== 第十二步：微信窗口对齐工具 ====================
# 如果微信窗口位置变了，之前测的坐标（835,612）就不准了
# 运行 python send_wechat.py --align 会在屏幕上画一个绿色框
# 你把微信窗口拖进去对齐，坐标就回到标准值了
#
# 什么时候需要重新对齐？
#   1. 第一次使用本脚本
#   2. 移动了微信窗口位置
#   3. 换了显示器或改了分辨率
#   4. 点击右键或发送按钮时位置不对


# 微信窗口在屏幕上的预期位置
# left  = 窗口左边距屏幕左边的像素数
# top   = 窗口上边距屏幕顶部的像素数
# width = 窗口的宽度
# height = 窗口的高度
#
# 当前值 (337, 206, 896, 648) 是在你电脑上测出来的
# 如果换了电脑或改了分辨率，需要用 --align 重新对齐
WX_EXPECTED = {
    "left": 337,
    "top": 206,
    "width": 896,
    "height": 648
}


def show_align_guide():
    """
    在屏幕上画一个绿色虚线框，提示用户把微信窗口拖进去。

    原理：
      用 tkinter（Python 自带的 GUI 库）创建一个全屏幕透明窗口
      在透明窗口上画一个绿色矩形框
      用户把微信窗口拖到框里对齐即可

    坐标说明：
      (835, 612) = 右键点击消息的位置
      (655, 775) = 发送按钮的位置
      这两个坐标只有在微信窗口对齐后才准确
    """
    import tkinter as tk  # Python 自带的图形界面库

    # 创建主窗口
    root = tk.Tk()
    root.title("微信对齐工具 - 把微信拖到框里")


    # 窗口属性设置
    root.attributes("-topmost", True)              # 置顶（在其他窗口上面）
    root.attributes("-transparentcolor", "white")  # 白色部分透明
    root.overrideredirect(True)                    # 去掉标题栏和边框

    # 把窗口铺满整个屏幕
    screen_w = root.winfo_screenwidth()   # 获取屏幕宽度
    screen_h = root.winfo_screenheight()  # 获取屏幕高度
    root.geometry(f"{screen_w}x{screen_h}+0+0")  # 宽x高+左偏移+上偏移

    # Canvas = 画布，用来画图形和文字
    canvas = tk.Canvas(root, highlightthickness=0, bg="white")
    canvas.pack(fill="both", expand=True)

    # 从配置里读取微信窗口的预期位置
    cfg = WX_EXPECTED

    # ---- 画绿色虚线矩形框 ----
    canvas.create_rectangle(
        cfg["left"], cfg["top"],                              # 左上角坐标
        cfg["left"] + cfg["width"], cfg["top"] + cfg["height"],  # 右下角坐标
        outline="#00ff00",    # 边框颜色（绿色）
        width=4,              # 边框宽度
        dash=(10, 5)          # 虚线样式（画 10 像素，空 5 像素）
    )

    # ---- 在框上方显示提示文字 ----
    canvas.create_text(
        cfg["left"] + cfg["width"] // 2,   # X = 框的水平中心
        cfg["top"] - 20,                    # Y = 框的上边缘往上 20 像素
        text="← 把微信拖到这个框里对齐 →",
        fill="#00ff00",
        font=("Microsoft YaHei", 14, "bold")  # 字体、大小、加粗
    )

    # ---- 在框内显示坐标参考 ----
    canvas.create_text(
        cfg["left"] + cfg["width"] // 2,   # X = 框的中心
        cfg["top"] + cfg["height"] // 2,    # Y = 框的中心
        text=(
            "右键消息 ≈ (835, 612)\n"
            "发送按钮 ≈ (655, 775)\n\n"
            "对齐后按 ESC 或点 ✕ 关闭"
        ),
        fill="#00ff00",
        font=("Microsoft YaHei", 12),
        justify="center"  # 文字居中
    )

    # ---- 右上角的关闭按钮 ----
    canvas.create_text(
        screen_w - 60, 20,                    # X = 屏幕右边偏左，Y = 靠上
        text="✕ 关闭",
        fill="red",
        font=("Microsoft YaHei", 12, "bold"),
        tags="close"  # 给这个文字打个标签，方便识别点击
    )

    # 鼠标点击事件：如果点到了"✕ 关闭"，就退出
    def on_click(event):
        # find_closest = 找到离点击位置最近的图形元素
        # gettags = 获取该元素的所有标签
        tags = canvas.gettags(canvas.find_closest(event.x, event.y))
        if "close" in tags:
            root.destroy()  # 关闭窗口

    # 绑定鼠标点击事件
    canvas.tag_bind("close", "<Button-1>", lambda e: root.destroy())
    # 按 ESC 键也退出
    root.bind("<Escape>", lambda e: root.destroy())

    # 启动界面（进入消息循环）
    root.mainloop()


def check_window_position():
    """
    检查微信窗口是否在预期的位置。
    如果位置偏差超过 10 像素，会在日志里警告。

    为什么要检查？
      如果窗口位置不对，右键坐标 (835,612) 和发送按钮坐标 (655,775)
      就会点错地方，可能点到别的聊天或按钮
    """
    w = get_window()
    if not w:
        return

    cfg = WX_EXPECTED

    # abs = absolute = 绝对值
    # abs(左边界偏差) 或 abs(上边界偏差) 超过 10 像素就告警
    if abs(w.left - cfg["left"]) > 10 or abs(w.top - cfg["top"]) > 10:
        logger.warning(
            f"微信窗口位置 ({w.left}, {w.top}) 与预期 ({cfg['left']}, {cfg['top']}) 不一致，"
            f"建议运行 python send_wechat.py --align 对齐"
        )


# ==================== 第十三步：命令行入口 ====================

def main():
    """
    命令行入口。这是用户和程序交互的界面。

    支持的命令（在终端/CMD/PowerShell 里运行）：
      python send_wechat.py --once         # 立即执行一次发送
      python send_wechat.py --daemon       # 启动定时发送（按配置时间自动发）
      python send_wechat.py --stats        # 查看发送统计
      python send_wechat.py --export 1.csv # 导出统计到 Excel
      python send_wechat.py --align        # 显示绿色框（对齐微信窗口）
      python send_wechat.py -v --once      # 详细模式 + 立即发送（看每一步）

    不传任何参数时会显示帮助信息。
    """
    # argparse 的用法：
    #   1. 创建一个 ArgumentParser 对象，传入描述文字
    #   2. 用 add_argument 添加每个参数
    #   3. parse_args() 解析用户实际输入的命令

    parser = argparse.ArgumentParser(description="微信定时群发工具")

    # action="store_true" 表示：如果用户写了 --once，args.once = True
    # help 是显示帮助时的说明文字
    parser.add_argument("--once", action="store_true", help="立即执行一次发送")
    parser.add_argument("--daemon", action="store_true", help="启动定时守护进程")
    parser.add_argument("--stats", action="store_true", help="显示发送统计")
    parser.add_argument("--export", type=str, help="导出统计到 CSV 文件（如 --export 统计.csv）")
    parser.add_argument("--align", action="store_true", help="显示对齐框（定位微信窗口）")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志模式")
    # -v 是缩写，--verbose 是完整写法，两者都可以

    # 解析用户输入的命令
    args = parser.parse_args()

    # 如果开启了详细模式，把日志级别调成 DEBUG（最详细）
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:  # 遍历所有日志处理器
            h.setLevel(logging.DEBUG)

    # 根据用户输入的命令执行对应的功能
    # 注意：这些命令是互斥的，一次只能选一个
    if args.align:
        show_align_guide()                # 显示绿色对齐框
    elif args.stats:
        show_stats()                      # 显示统计
    elif args.export:
        export_csv(args.export)           # 导出到 CSV
    elif args.daemon:
        run_daemon()                      # 启动定时任务
    elif args.once:
        check_window_position()           # 先检查窗口位置
        do_send(verbose=args.verbose)     # 立即发送
    else:
        parser.print_help()               # 没传参数就显示帮助


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
