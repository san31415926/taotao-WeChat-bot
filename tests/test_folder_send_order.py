import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import send_wechat as sw


class FolderSendOrderTests(unittest.TestCase):
    def test_get_available_send_folders_returns_only_complete_text_video_pairs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            complete = Path(temp_dir, "苹果16PM黑色256G")
            incomplete = Path(temp_dir, "不完整款式")
            complete.mkdir()
            incomplete.mkdir()
            Path(complete, "介绍.txt").write_text("文字内容", encoding="utf-8")
            Path(complete, "视频.mp4").write_bytes(b"video")
            Path(incomplete, "介绍.txt").write_text("缺少视频", encoding="utf-8")

            with mock.patch.object(sw, "SCRIPT_DIR", temp_dir):
                names = sw.get_available_send_folders()

        self.assertEqual(names, ["苹果16PM黑色256G"])

    def test_image_product_folder_is_discovered_and_orders_text_before_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir, "image-product")
            folder.mkdir()
            image_path = Path(folder, "photo.png")
            text_path = Path(folder, "description.txt")
            image_path.write_bytes(b"image")
            text_path.write_text("send this first", encoding="utf-8")

            original_config = sw.CONFIG.copy()
            original_script_dir = sw.SCRIPT_DIR
            try:
                sw.SCRIPT_DIR = temp_dir
                sw.CONFIG = {"send_folders": []}
                names = sw.get_available_send_folders()
                batches = sw.read_selected_batches()
            finally:
                sw.SCRIPT_DIR = original_script_dir
                sw.CONFIG = original_config

        self.assertEqual(names, ["image-product"])
        self.assertEqual(len(batches), 1)
        self.assertEqual([item.kind for item in batches[0].files], ["text", "image"])
        self.assertEqual(batches[0].files[0].content, "send this first")
        self.assertEqual(batches[0].files[1].path, os.path.abspath(image_path))

    def test_read_selected_batches_orders_text_before_video(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir, "苹果16PM黑色256G")
            folder.mkdir()
            video_path = Path(folder, "视频.mp4")
            text_path = Path(folder, "介绍.txt")
            video_path.write_bytes(b"video")
            text_path.write_text("先发这段文字", encoding="utf-8")

            original_config = sw.CONFIG.copy()
            try:
                sw.SCRIPT_DIR = temp_dir
                sw.CONFIG = {"send_folders": [folder.name]}
                batches = sw.read_selected_batches()
            finally:
                sw.CONFIG = original_config

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].name, folder.name)
        self.assertEqual([item.kind for item in batches[0].files], ["text", "video"])
        self.assertEqual(batches[0].files[0].content, "先发这段文字")
        self.assertEqual(batches[0].files[1].path, os.path.abspath(video_path))

    def test_do_send_sends_text_then_video_for_one_folder(self):
        batch = sw.SendBatch(
            name="苹果16PM黑色256G",
            files=(
                sw.SendFile("介绍.txt", "text", "C:\\data\\介绍.txt", "先发文字"),
                sw.SendFile("视频.mp4", "video", "C:\\data\\视频.mp4"),
            ),
        )
        calls = []
        original_config = sw.CONFIG.copy()
        try:
            sw.CONFIG = {"interval_between_files": "5s"}
            with mock.patch.object(sw, "read_selected_batches", return_value=[batch]), \
                    mock.patch.object(sw, "send_to_all", side_effect=lambda content: calls.append(("text", content)) or (2, 0)), \
                    mock.patch.object(sw, "send_media_to_all", side_effect=lambda path: calls.append(("video", path)) or (2, 0)), \
                    mock.patch.object(sw, "_time_sleep") as wait, \
                    mock.patch.object(sw, "load_stats", return_value={
                        "total_sends": 0, "last_send": None, "history": []
                    }), \
                    mock.patch.object(sw, "save_stats"):
                sw.do_send()
        finally:
            sw.CONFIG = original_config

        self.assertEqual(calls, [("text", "先发文字"), ("video", "C:\\data\\视频.mp4")])
        wait.assert_not_called()

    def test_do_send_waits_after_video_before_the_next_batch(self):
        video_batch = sw.SendBatch(
            name="video-product",
            files=(
                sw.SendFile("description.txt", "text", "C:\\data\\description.txt", "text"),
                sw.SendFile("clip.mp4", "video", "C:\\data\\clip.mp4"),
            ),
        )
        next_batch = sw.SendBatch(
            name="next-product",
            files=(sw.SendFile("next.txt", "text", "C:\\data\\next.txt", "next"),),
        )
        original_config = sw.CONFIG.copy()
        try:
            sw.STOP_EVENT.clear()
            sw.CONFIG = {
                "interval_between_files": "0s",
                "video_next_step_wait": "2s",
            }
            with mock.patch.object(sw, "read_selected_batches", return_value=[video_batch, next_batch]), \
                    mock.patch.object(sw, "send_to_all", return_value=(2, 0)), \
                    mock.patch.object(sw, "send_media_to_all", return_value=(2, 0)), \
                    mock.patch.object(sw, "_time_sleep") as wait, \
                    mock.patch.object(sw, "load_stats", return_value={
                        "total_sends": 0, "last_send": None, "history": []
                    }), \
                    mock.patch.object(sw, "save_stats"):
                sw.do_send()
        finally:
            sw.CONFIG = original_config

        self.assertEqual(wait.call_args_list, [mock.call(1.0), mock.call(1.0)])


if __name__ == "__main__":
    unittest.main()
