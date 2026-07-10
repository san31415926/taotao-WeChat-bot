import pyautogui
import time

print("鼠标坐标测量工具")
print("  实时显示鼠标位置，左键点击记录坐标")
print("  Ctrl+C 退出")
print()

left_was_down = False
right_was_down = False

try:
    while True:
        x, y = pyautogui.position()
        left_now = pyautogui.mouseDown(button="left")
        right_now = pyautogui.mouseDown(button="right")

        if left_now and not left_was_down:
            print(f"\n>>> 左键坐标: ({x:4d}, {y:4d})")
        if right_now and not right_was_down:
            print(f"\n>>> 右键坐标: ({x:4d}, {y:4d})")

        left_was_down = left_now
        right_was_down = right_now

        print(f"\r鼠标: ({x:4d}, {y:4d})    ", end="")
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\n\n已退出")
