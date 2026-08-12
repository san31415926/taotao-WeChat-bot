import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import send_wechat as sw


class MediaSupportTests(unittest.TestCase):
    def test_self_chat_matches_the_wechat_search_name(self):
        self.assertEqual(sw.SELF_CHAT, "A淘淘数码-同行号1 (支持闲鱼）")

    def test_classify_media_file_supports_text_images_and_videos(self):
        self.assertEqual(sw.classify_media_file("内容.txt"), "text")
        self.assertEqual(sw.classify_media_file("照片.JPG"), "image")
        self.assertEqual(sw.classify_media_file("演示.mp4"), "video")

    def test_classify_media_file_rejects_unsupported_extensions(self):
        with self.assertRaises(ValueError):
            sw.classify_media_file("文档.pdf")

    def test_get_available_files_includes_images_and_videos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for name in ("内容.txt", "照片.png", "演示.mov", "忽略.pdf"):
                Path(temp_dir, name).write_bytes(b"test")

            with mock.patch.object(sw, "SCRIPT_DIR", temp_dir):
                names = sw.get_available_files()

        self.assertEqual(set(names), {"内容.txt", "照片.png", "演示.mov"})

    def test_read_selected_files_returns_media_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            text_path = Path(temp_dir, "内容.txt")
            image_path = Path(temp_dir, "照片.png")
            video_path = Path(temp_dir, "演示.mp4")
            text_path.write_text("hello", encoding="utf-8")
            image_path.write_bytes(b"image")
            video_path.write_bytes(b"video")

            original_config = sw.CONFIG.copy()
            try:
                sw.SCRIPT_DIR = temp_dir
                sw.CONFIG = {
                    "send_files": [
                        text_path.name,
                        image_path.name,
                        video_path.name,
                    ]
                }
                items = sw.read_selected_files()
            finally:
                sw.CONFIG = original_config

        self.assertEqual([item.kind for item in items], ["text", "image", "video"])
        self.assertEqual(items[0].content, "hello")
        self.assertEqual(items[1].path, os.path.abspath(image_path))
        self.assertEqual(items[2].path, os.path.abspath(video_path))

    def test_send_media_to_all_reports_successful_groups(self):
        original_config = sw.CONFIG.copy()
        try:
            sw.CONFIG = {"group_prefixes": ["A", "B"], "groups_per_prefix": 2}
            with mock.patch.object(sw, "activate_wechat", return_value=True), \
                    mock.patch.object(sw, "send_media_to_prefix_groups", return_value=2):
                result = sw.send_media_to_all("C:\\media\\photo.png")
        finally:
            sw.CONFIG = original_config

        self.assertEqual(result, (4, 0))

    def test_image_forwarding_uses_the_three_down_media_menu_navigation(self):
        with mock.patch.object(sw, "send_media_to_self"), \
                mock.patch.object(sw, "forward_to_groups") as forward:
            result = sw.send_media_to_prefix_groups("00A001", 2, "C:\\media\\photo.png")

        self.assertEqual(result, 2)
        forward.assert_called_once_with("00A001", 2, media=True)

    def test_set_clipboard_files_rejects_missing_files(self):
        with self.assertRaises(FileNotFoundError):
            sw.set_clipboard_files(["C:\\missing\\photo.png"])

    def test_send_media_to_self_pastes_file_from_clipboard(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir, "照片.png")
            image_path.write_bytes(b"image")
            events = []
            original_config = sw.CONFIG.copy()
            try:
                sw.CONFIG = {
                    "media_prepare_wait": 2,
                    "media_upload_wait": 3,
                }
                with mock.patch.object(sw, "_open_self_chat"), \
                        mock.patch.object(sw, "set_clipboard_files", side_effect=lambda paths: events.append(("clipboard", paths))) as set_files, \
                        mock.patch.object(sw, "_wait_unscaled", side_effect=lambda seconds: events.append(("wait", seconds))), \
                        mock.patch.object(sw.pyautogui, "hotkey", side_effect=lambda *keys: events.append(("hotkey", keys))) as hotkey, \
                        mock.patch.object(sw.pyautogui, "press", side_effect=lambda key: events.append(("press", key))) as press:
                    sw.send_media_to_self(str(image_path))
            finally:
                sw.CONFIG = original_config

        set_files.assert_called_once_with([os.path.abspath(image_path)])
        hotkey.assert_called_once_with("ctrl", "v")
        press.assert_called_once_with("enter")
        self.assertEqual(events, [
            ("clipboard", [os.path.abspath(image_path)]),
            ("hotkey", ("ctrl", "v")),
            ("wait", 2),
            ("press", "enter"),
            ("wait", 3),
        ])

    def test_do_send_dispatches_media_items_to_media_sender(self):
        item = sw.SendFile(
            name="照片.png",
            kind="image",
            path="C:\\media\\photo.png",
        )
        batch = sw.SendBatch(name="单文件", files=(item,))
        original_config = sw.CONFIG.copy()
        try:
            sw.CONFIG = {"interval_between_files": "0"}
            with mock.patch.object(sw, "read_selected_batches", return_value=[batch]), \
                    mock.patch.object(sw, "send_batch_to_all", return_value=(2, 0)) as send_batch, \
                    mock.patch.object(sw, "load_stats", return_value={
                        "total_sends": 0, "last_send": None, "history": []
                    }), \
                    mock.patch.object(sw, "save_stats"):
                sw.do_send()
        finally:
            sw.CONFIG = original_config

        send_batch.assert_called_once_with(batch)


if __name__ == "__main__":
    unittest.main()
