
from __future__ import annotations

from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dll", ".so",
    ".dylib", ".pyc", ".pyd", ".class", ".jar", ".woff", ".woff2", ".ttf",
    ".eot", ".mp3", ".mp4", ".mov", ".avi", ".db", ".sqlite", ".sqlite3",
}

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB, per spec

ENTRY_POINT_CANDIDATES = [
    "main.py", "app.py", "manage.py", "run.py", "wsgi.py", "asgi.py",
    "__main__.py", "index.js", "index.ts", "server.js", "app.js",
    "main.go", "Main.java", "Program.cs", "main.rs",
]

LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".jsx": "JavaScript", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".h": "C/C++",
    ".hpp": "C++", ".cs": "C#", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".rs": "Rust", ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "SASS",
    ".json": "JSON", ".xml": "XML", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell",
    ".sql": "SQL",
}


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def is_probably_binary(file_path: Path, sniff_bytes: int = 2048) -> bool:
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with file_path.open("rb") as fh:
            chunk = fh.read(sniff_bytes)
        return b"\x00" in chunk
    except OSError:
        return True


def should_skip_file(file_path: Path) -> bool:
    """True if this file must not be read (binary or too large)."""
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return True
    except OSError:
        return True

    return is_probably_binary(file_path)


def iter_source_files(root_path: Path):
    """Yield every readable, non-binary, size-bounded file under root_path."""
    for current_dir, dirs, file_names in _walk(root_path):
        for name in sorted(file_names):
            file_path = current_dir / name
            if not file_path.is_file():
                continue
            if should_skip_file(file_path):
                continue
            yield file_path


def _walk(root_path: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if not should_skip_dir(d))
        yield Path(dirpath), dirnames, filenames


def read_text_safe(file_path: Path, max_chars: int = 8000) -> str:
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return text[:max_chars]


def build_repository_tree_text(root_path: Path, max_entries: int = 400) -> str:
    """A simple indented text tree, capped so the prompt stays small."""
    lines = []
    count = 0

    def walk(path: Path, prefix: str = ""):
        nonlocal count
        if count >= max_entries:
            return

        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
            )
        except OSError:
            return

        for entry in entries:
            if count >= max_entries:
                lines.append(f"{prefix}... (truncated)")
                return
            if entry.is_dir():
                if should_skip_dir(entry.name):
                    continue
                lines.append(f"{prefix}{entry.name}/")
                count += 1
                walk(entry, prefix + "  ")
            else:
                lines.append(f"{prefix}{entry.name}")
                count += 1

    walk(root_path)
    return "\n".join(lines) if lines else "(empty repository)"


def find_entry_points(root_path: Path) -> list[Path]:
    found = []
    for candidate in ENTRY_POINT_CANDIDATES:
        candidate_path = root_path / candidate
        if candidate_path.exists():
            found.append(candidate_path)

    if not found:
        for file_path in iter_source_files(root_path):
            if file_path.name in ENTRY_POINT_CANDIDATES:
                found.append(file_path)

    return found


def pick_important_source_files(root_path: Path, limit: int = 6) -> list[Path]:
    """
    Heuristic: entry points first, then the largest source files by line
    count (a rough proxy for "this file matters"). Capped so we never
    build a giant prompt.
    """
    entry_points = find_entry_points(root_path)

    scored = []
    for file_path in iter_source_files(root_path):
        if file_path.suffix.lower() not in LANGUAGE_BY_EXTENSION:
            continue
        if file_path in entry_points:
            continue
        text = read_text_safe(file_path, max_chars=20000)
        line_count = text.count("\n")
        scored.append((line_count, file_path))

    scored.sort(key=lambda item: item[0], reverse=True)
    extra = [path for _, path in scored[: max(0, limit - len(entry_points))]]

    return entry_points + extra


def language_breakdown(root_path: Path) -> dict:
    counts: dict[str, int] = {}
    for file_path in iter_source_files(root_path):
        language = LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower())
        if not language:
            continue
        text = read_text_safe(file_path, max_chars=200000)
        counts[language] = counts.get(language, 0) + sum(
            1 for line in text.splitlines() if line.strip()
        )
    return counts


def keyword_search(root_path: Path, question: str, limit: int = 5) -> list[Path]:
    """
    Very small "retrieval" step for the repository chat: pick files whose
    name or contents mention the keywords in the user's question, so we
    never have to send the whole repository to Gemini.
    """
    stopwords = {
        "the", "is", "a", "an", "how", "what", "where", "does", "do",
        "which", "file", "files", "in", "of", "to", "are", "this",
        "handles", "handle", "start", "starts", "work", "works",
    }
    keywords = [
        word.strip(".,?!:;()\"'").lower()
        for word in question.split()
        if len(word) > 2 and word.lower() not in stopwords
    ]

    if not keywords:
        return []

    scored = []
    for file_path in iter_source_files(root_path):
        if file_path.suffix.lower() not in LANGUAGE_BY_EXTENSION and file_path.suffix.lower() not in {".md", ".txt"}:
            continue

        name_lower = file_path.name.lower()
        score = sum(3 for kw in keywords if kw in name_lower)

        text = read_text_safe(file_path, max_chars=20000).lower()
        score += sum(text.count(kw) for kw in keywords)

        if score > 0:
            scored.append((score, file_path))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored[:limit]]
