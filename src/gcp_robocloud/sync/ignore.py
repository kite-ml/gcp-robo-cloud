"""File exclusion patterns for project upload.

Supports .gcp-robocloud-ignore files (gitignore syntax) plus built-in defaults.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

# Always excluded - never upload these
BUILTIN_EXCLUDES = [
    ".git",
    ".git/**",
    "__pycache__",
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    "node_modules",
    "node_modules/**",
    "*.egg-info",
    "*.egg-info/**",
    ".gcp-robocloud",
    ".gcp-robocloud/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    "*.mp4",
    "*.avi",
    "*.mov",
    "*.mkv",
    ".env",
    ".DS_Store",
]

IGNORE_FILENAME = ".gcp-robocloud-ignore"


def load_ignore_patterns(project_dir: Path) -> list[str]:
    """Load exclusion patterns from all sources.

    Args:
        project_dir: Project root directory.

    Returns:
        Combined list of exclusion patterns.
    """
    patterns = list(BUILTIN_EXCLUDES)

    ignore_file = project_dir / IGNORE_FILENAME
    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    return patterns


def should_exclude(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path should be excluded.

    Args:
        rel_path: Relative path from project root.
        patterns: List of exclusion patterns (glob/fnmatch syntax).

    Returns:
        True if the path should be excluded.
    """
    for pattern in patterns:
        # Directory patterns (ending with /) match any file under that directory
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if rel_path.startswith(dir_pattern + "/") or rel_path == dir_pattern:
                return True
            # Also check with fnmatch for glob patterns
            if fnmatch(rel_path, dir_pattern + "/*"):
                return True
        # Direct match
        if fnmatch(rel_path, pattern):
            return True
        # Match against just the filename
        filename = rel_path.rsplit("/", 1)[-1]
        if fnmatch(filename, pattern):
            return True
        # Match against each directory component
        parts = rel_path.split("/")
        for part in parts:
            if fnmatch(part, pattern):
                return True
    return False


def collect_files(project_dir: Path, extra_excludes: list[str] | None = None) -> list[Path]:
    """Collect all files in a project, respecting exclusion rules.

    Args:
        project_dir: Project root directory.
        extra_excludes: Additional exclusion patterns.

    Returns:
        List of file paths relative to project_dir.
    """
    patterns = load_ignore_patterns(project_dir)
    if extra_excludes:
        patterns.extend(extra_excludes)

    files = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(project_dir))
        if not should_exclude(rel, patterns):
            files.append(path.relative_to(project_dir))

    return files
