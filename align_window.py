"""
微信窗口对齐工具
把微信窗口拖到绿色框框里，对齐后关掉这个窗口就行。
这样右键坐标 (1295,758) 和发送按钮坐标 (1111,876) 就永远准确了。
"""

import tkinter as tk

# 目标位置（你微信窗口当前的坐标和大小）
WX_LEFT = 337
WX_TOP = 206
WX_WIDTH = 896
WX_HEIGHT = 648

# 创建一个全屏透明窗口
root = tk.Tk()
root.title("微信对齐工具 - 把微信拖到框里")
root.attributes("-topmost", True)       # 置顶
root.attributes("-transparentcolor", "white")  # 白色变透明
root.overrideredirect(True)             # 无标题栏
root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

# 画布
canvas = tk.Canvas(root, highlightthickness=0, bg="white")
canvas.pack(fill="both", expand=True)

# 画一个绿色的框
canvas.create_rectangle(
    WX_LEFT, WX_TOP,
    WX_LEFT + WX_WIDTH, WX_TOP + WX_HEIGHT,
    outline="#00ff00",
    width=4,
    dash=(10, 5)        # 虚线效果
)

# 在框上方显示文字
canvas.create_text(
    WX_LEFT + WX_WIDTH // 2, WX_TOP - 20,
    text="← 把微信拖到这个框里对齐 →",
    fill="#00ff00",
    font=("Microsoft YaHei", 14, "bold")
)

# 在框内显示坐标信息
canvas.create_text(
    WX_LEFT + WX_WIDTH // 2, WX_TOP + WX_HEIGHT // 2 - 20,
    text="右键消息 ≈ (1295, 758)\n发送按钮 ≈ (1111, 876)",
    fill="#00ff00",
    font=("Microsoft YaHei", 12),
    justify="center"
)

# 添加关闭按钮
canvas.create_text(
    root.winfo_screenwidth() - 60, 20,
    text="✕ 关闭",
    fill="red",
    font=("Microsoft YaHei", 12, "bold"),
    tags="close"
)

def on_click(event):
    """点击关闭按钮退出"""
    tags = canvas.gettags(canvas.find_closest(event.x, event.y))
    if "close" in tags:
        root.destroy()

canvas.tag_bind("close", "<Button-1>", lambda e: root.destroy())

# 按 ESC 键退出
root.bind("<Escape>", lambda e: root.destroy())

root.mainloop()
