import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("omalab_viewer", Path(__file__).parents[1] / "support/viewer.py")
viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viewer)


class ViewerEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = Path(self.directory.name)
        self.endpoint = self.runtime / "test-wayland"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.endpoint))
        self.addCleanup(self.socket.close)

    def test_detached_recovery_selects_wayland_without_importing_manager_secrets(self):
        manager = {"WAYLAND_DISPLAY": self.endpoint.name, "DISPLAY": ":0",
                   "XDG_RUNTIME_DIR": str(self.runtime), "SECRET_TOKEN": "not-for-viewer",
                   "HERDR_ENV": "1"}
        reply = subprocess.CompletedProcess([], 0, json.dumps(manager), "")
        with patch.object(viewer.subprocess, "run", return_value=reply):
            result = viewer.session_environment({"XDG_RUNTIME_DIR": str(self.runtime)})
        self.assertEqual(result["backend"], "wayland")
        self.assertEqual(result["WAYLAND_DISPLAY"], str(self.endpoint))
        self.assertEqual(result["source"], "user-manager")
        self.assertNotIn("SECRET_TOKEN", result)
        self.assertNotIn("HERDR_ENV", result)

    def test_explicit_wayland_destination_wins_over_invalid_x11_and_manager(self):
        with patch.object(viewer.subprocess, "run", side_effect=AssertionError("must not recover a different desktop")):
            result = viewer.session_environment({"WAYLAND_DISPLAY": str(self.endpoint), "DISPLAY": ":9999"})
        self.assertEqual(result["backend"], "wayland")
        self.assertEqual(result["WAYLAND_DISPLAY"], str(self.endpoint))
        self.assertEqual(result["source"], "caller")

    def test_explicit_x11_destination_is_not_redirected_to_the_users_wayland_desktop(self):
        with patch.object(viewer.subprocess, "run", side_effect=AssertionError("must not override explicit display")):
            result = viewer.session_environment({"DISPLAY": ":123", "HOME": str(self.runtime)})
        self.assertEqual(result["backend"], "x11")
        self.assertEqual(result["DISPLAY"], ":123")
        self.assertNotIn("WAYLAND_DISPLAY", result)

    def test_stale_or_non_socket_wayland_does_not_fall_back_to_another_display(self):
        for path in (self.runtime / "missing", self.runtime / "regular-file"):
            if path.name == "regular-file":
                path.write_text("not a socket")
            with self.subTest(path=path), patch.object(viewer.subprocess, "run", side_effect=AssertionError("must not guess")):
                with self.assertRaises(ValueError):
                    viewer.session_environment({"WAYLAND_DISPLAY": str(path), "DISPLAY": ":0"})

    def test_manager_failure_and_missing_endpoints_are_actionable_errors(self):
        cases = [subprocess.TimeoutExpired("systemctl", 5),
                 subprocess.CompletedProcess([], 0, "{}", ""),
                 subprocess.CompletedProcess([], 0, "[]", ""),
                 subprocess.CompletedProcess([], 0, "not-json", "")]
        for case in cases:
            with self.subTest(case=case):
                kwargs = {"side_effect": case} if isinstance(case, Exception) else {"return_value": case}
                with patch.object(viewer.subprocess, "run", **kwargs):
                    with self.assertRaises(ValueError):
                        viewer.session_environment({})

    def test_caller_runtime_is_not_overwritten_by_stale_manager_state(self):
        manager = {"WAYLAND_DISPLAY": self.endpoint.name, "XDG_RUNTIME_DIR": "/wrong/runtime"}
        reply = subprocess.CompletedProcess([], 0, json.dumps(manager), "")
        with patch.object(viewer.subprocess, "run", return_value=reply):
            result = viewer.session_environment({"XDG_RUNTIME_DIR": str(self.runtime)})
        self.assertEqual(result["WAYLAND_DISPLAY"], str(self.endpoint))
        self.assertEqual(result["XDG_RUNTIME_DIR"], str(self.runtime))


if __name__ == "__main__":
    unittest.main()
