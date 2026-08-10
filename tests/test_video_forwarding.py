from types import SimpleNamespace
import unittest
from unittest import mock

import send_wechat as sw


class VideoForwardingTests(unittest.TestCase):
    def test_video_forwarding_moves_down_three_times_before_enter(self):
        window = SimpleNamespace(left=10, top=20)
        with mock.patch.object(sw, "get_window", return_value=window), \
                mock.patch.object(sw.pyautogui, "rightClick"), \
                mock.patch.object(sw.pyautogui, "press") as press, \
                mock.patch.object(sw.pyautogui, "hotkey"), \
                mock.patch.object(sw.pyautogui, "click"), \
                mock.patch.object(sw.pyperclip, "copy"), \
                mock.patch.object(sw.time, "sleep"):
            sw.forward_to_groups("00A001", 1, media=True)

        keys = [call.args[0] for call in press.call_args_list]
        self.assertEqual(keys[:4], ["down", "down", "down", "enter"])
        self.assertEqual(keys.count("down"), 7)


if __name__ == "__main__":
    unittest.main()
