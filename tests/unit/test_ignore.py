"""Tests for file exclusion patterns."""

import tempfile
from pathlib import Path

from gcp_robo_cloud.sync.ignore import (
    BUILTIN_EXCLUDES,
    collect_files,
    load_ignore_patterns,
    should_exclude,
)


class TestShouldExclude:
    def test_git_excluded(self):
        assert should_exclude(".git/config", BUILTIN_EXCLUDES)
        assert should_exclude(".git", BUILTIN_EXCLUDES)

    def test_pycache_excluded(self):
        assert should_exclude("__pycache__/module.pyc", BUILTIN_EXCLUDES)
        assert should_exclude("src/__pycache__/foo.pyc", BUILTIN_EXCLUDES)

    def test_pyc_files_excluded(self):
        assert should_exclude("module.pyc", BUILTIN_EXCLUDES)
        assert should_exclude("src/foo.pyc", BUILTIN_EXCLUDES)

    def test_venv_excluded(self):
        assert should_exclude(".venv/lib/python3.11/site-packages/foo.py", BUILTIN_EXCLUDES)
        assert should_exclude("venv/bin/python", BUILTIN_EXCLUDES)

    def test_normal_files_not_excluded(self):
        assert not should_exclude("train.py", BUILTIN_EXCLUDES)
        assert not should_exclude("src/model.py", BUILTIN_EXCLUDES)
        assert not should_exclude("requirements.txt", BUILTIN_EXCLUDES)

    def test_video_excluded(self):
        assert should_exclude("output.mp4", BUILTIN_EXCLUDES)
        assert should_exclude("recordings/test.avi", BUILTIN_EXCLUDES)

    def test_ds_store_excluded(self):
        assert should_exclude(".DS_Store", BUILTIN_EXCLUDES)

    def test_env_excluded(self):
        assert should_exclude(".env", BUILTIN_EXCLUDES)

    def test_custom_patterns(self):
        patterns = ["*.hdf5", "data/raw/"]
        assert should_exclude("dataset.hdf5", patterns)
        assert should_exclude("data/raw/file.txt", patterns)


class TestCollectFiles:
    def test_collects_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "train.py").write_text("print('hi')")
            (root / "requirements.txt").write_text("torch\n")
            files = collect_files(root)
            names = [str(f) for f in files]
            assert "train.py" in names
            assert "requirements.txt" in names

    def test_excludes_pycache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "train.py").write_text("print('hi')")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "train.cpython-311.pyc").write_bytes(b"")
            files = collect_files(root)
            names = [str(f) for f in files]
            assert "train.py" in names
            assert not any("pycache" in n for n in names)

    def test_respects_ignore_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "train.py").write_text("print('hi')")
            (root / "data.bin").write_bytes(b"data")
            (root / ".gcp-robo-cloud-ignore").write_text("*.bin\n")
            files = collect_files(root)
            names = [str(f) for f in files]
            assert "train.py" in names
            assert "data.bin" not in names

    def test_extra_excludes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "train.py").write_text("print('hi')")
            (root / "big_model.pth").write_bytes(b"model")
            files = collect_files(root, extra_excludes=["*.pth"])
            names = [str(f) for f in files]
            assert "train.py" in names
            assert "big_model.pth" not in names
