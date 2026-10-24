import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

script = Path(os.environ.get("TOUCAN_UPDATE_SCRIPT", Path(__file__).resolve().parents[1] / "nix/update-west.py"))
spec = importlib.util.spec_from_file_location("update_west", script)
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class UpdateWestTests(unittest.TestCase):
    def setUp(self):
        self.project = {
            "name": "zmk", "url": "https://github.com/zmkfirmware/zmk",
            "path": "zmk", "revision": "a" * 40,
        }
        self.locked = self.project | {"hash": "sha256-existing"}

    def test_resolves_workspace_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".west").mkdir()
            (workspace / ".west/config").write_text("[manifest]\npath = config\n")
            (workspace / "config").mkdir()
            (workspace / "config/west.yml").write_text("manifest:\n  projects: []\n  self:\n    path: config\n")
            self.assertEqual(update.resolve_projects(workspace), [])

    @patch.object(update.subprocess, "check_output")
    def test_unchanged_revision_reuses_hash(self, prefetch):
        self.assertEqual(update.hash_projects([self.project], [self.locked]), [self.locked])
        prefetch.assert_not_called()

    @patch.object(update.subprocess, "check_output", return_value='{"hash":"sha256-new"}')
    def test_new_revision_prefetches_unpacked_archive(self, prefetch):
        project = self.project | {"revision": "b" * 40}
        result = update.hash_projects([project], [self.locked])
        self.assertEqual(result, [project | {"hash": "sha256-new"}])
        command = prefetch.call_args.args[0]
        self.assertIn("--unpack", command)
        self.assertEqual(command[-1], f"{project['url']}/archive/{project['revision']}.tar.gz")
        self.assertNotIn("hash", project)  # Do not mutate the resolved manifest.

    @patch.object(update.subprocess, "check_output", return_value='{"hash":"sha256-new"}')
    def test_changed_remote_does_not_reuse_hash(self, prefetch):
        project = self.project | {"url": "https://github.com/example/zmk"}
        self.assertEqual(update.hash_projects([project], [self.locked])[0]["hash"], "sha256-new")
        prefetch.assert_called_once()

    def test_unsupported_host_fails(self):
        with self.assertRaises(ValueError):
            update.hash_projects([self.project | {"url": "https://example.org/zmk"}], [])

    def test_atomic_write_replaces_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sources.json"
            output.write_text("[]\n")
            update.write_sources(output, [self.locked])
            self.assertEqual(json.loads(output.read_text()), [self.locked])
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_failed_write_preserves_previous_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sources.json"
            output.write_text("[]\n")
            with self.assertRaises(TypeError):
                update.write_sources(output, [object()])
            self.assertEqual(output.read_text(), "[]\n")
            self.assertEqual(list(Path(directory).iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
