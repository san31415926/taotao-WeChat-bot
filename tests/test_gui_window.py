import unittest

import gui


class FolderSearchTests(unittest.TestCase):
    def test_filter_folder_names_matches_case_insensitively_and_keeps_order(self):
        names = ["Apple16PMBlack", "Apple15Pro", "SamsungS24"]

        self.assertEqual(
            gui.filter_folder_names(names, "BLACK"),
            ["Apple16PMBlack"],
        )
        self.assertEqual(gui.filter_folder_names(names, ""), names)

    def test_folder_list_is_sized_larger_than_runtime_log(self):
        self.assertGreater(gui.FOLDER_LIST_HEIGHT, gui.LOG_HEIGHT)
        self.assertEqual(gui.FOLDER_SEARCH_LABEL, "搜索文件夹:")

    def test_gui_exposes_video_next_step_wait_setting(self):
        self.assertIn(
            ("video_next_step_wait", "视频转发完成后等待（如 5m、30s、1h）", "str"),
            gui.CONFIG_FIELDS,
        )


class FakeRoot:
    def __init__(self):
        self.states = []

    def state(self, value):
        self.states.append(value)


class GuiWindowTests(unittest.TestCase):
    def test_maximize_window_requests_windows_zoomed_state(self):
        root = FakeRoot()

        gui.maximize_window(root)

        self.assertEqual(root.states, ["zoomed"])


if __name__ == "__main__":
    unittest.main()
