import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib import request

import customtkinter as ctk
from PIL import Image

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("theme.json")

root = ctk.CTk()

from text_style import HERO, TITLE, SUBTITLE, HEADING, SUBHEADING, BODYBIG, BODY, FONT_CODE

from ai import (
    gemini_client,
    repository_summary,
    file_explainer,
    repository_chat,
    secret_scanner,
    threat_scanner,
    risk_score,
    forensic_report,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

window_width = 0
window_height = 0
window_title = ""

CURRENT_PROJECT_PATH = None
CURRENT_REPO_URL = None
CURRENT_REPO_INFO = None

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".ico",
    ".tiff",
}

def update_window():
    root.title(window_title)

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2

    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    root.resizable(False, False)

    for widget in root.winfo_children():
        widget.destroy()


def format_timestamp(path):
    return datetime.fromtimestamp(path.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")


def format_modified_timestamp(path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def format_datetime(value):
    if not value:
        return "N/A"
    try:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value


def parse_github_repo(repo_url):
    if not repo_url:
        return None, None

    url = repo_url.strip().rstrip("/")

    if url.startswith("git@github.com:"):
        path = url.split(":", 1)[1]
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return parts[-2], parts[-1].removesuffix(".git")
        return None, None

    if "github.com" not in url:
        return None, None

    if url.startswith("http://") or url.startswith("https://"):
        if url.endswith(".git"):
            url = url[:-4]

        parts = [p for p in url.split("/") if p]
        if len(parts) >= 2:
            return parts[-2], parts[-1]

    return None, None


def get_github_repo_info(repo_url):
    owner, repo_name = parse_github_repo(repo_url)
    if not owner or not repo_name:
        return None

    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    req = request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TRACE-App",
        },
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            data = json.load(response)
    except Exception:
        return None

    return {
        "name": data.get("name") or repo_name,
        "owner": (data.get("owner") or {}).get("login") or owner,
        "created_at": data.get("created_at"),
        "pushed_at": data.get("pushed_at") or data.get("updated_at"),
    }


def get_directory_repo_url(path):
    if not path.exists() or not path.is_dir():
        return None

    if (path / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    return None


def get_project_author(path, repo_url=None):
    repo_info = get_github_repo_info(repo_url) if repo_url else None
    if repo_info:
        return repo_info["owner"]

    if (path / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(path), "config", "--get", "user.name"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    return "N/A"


def clone_repo(repo_url):
    if not shutil.which("git"):
        raise RuntimeError(" Git is not installed or not available on PATH.")

    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not repo_name:
        raise RuntimeError("Could not determine repository name from the URL.")

    target_dir = PROJECTS_DIR / repo_name

    if target_dir.exists() and any(target_dir.iterdir()):
        return target_dir

    if target_dir.exists():
        shutil.rmtree(target_dir)

    result = subprocess.run(
        ["git", "clone", repo_url, str(target_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Git clone failed.")

    return target_dir


def find_readme(path):
    candidates = [
        "README.md",
        "README.rst",
        "README.txt",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "README",
        "readme",
    ]

    for name in candidates:
        file_path = path / name
        if file_path.exists():
            return file_path 

    for item in sorted(path.rglob("*")):
        if item.is_file() and item.name.lower().startswith("readme"):
            return item

    return None


def find_license(path):
    candidates = [
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "LICENSE.rst",
        "COPYING",
        "COPYING.txt",
        "COPYING.md",
        "NOTICE",
        "NOTICE.txt",
    ]

    for name in candidates:
        file_path = path / name
        if file_path.exists():
            return file_path

    for item in sorted(path.rglob("*")):
        if item.is_file() and item.name.lower() in {
            "license",
            "license.txt",
            "license.md",
            "license.rst",
            "copying",
            "copying.txt",
            "copying.md",
            "notice",
            "notice.txt",
        }:
            return item

    return None


def find_requirements_files(path):
    candidates = [
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
    ]

    found = []
    for name in candidates:
        file_path = path / name
        if file_path.exists():
            found.append(file_path)

    for item in sorted(path.rglob("*")):
        if item.is_file() and item.name.lower() in {
            "requirements.txt",
            "pyproject.toml",
            "pipfile",
            "package.json",
            "cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
        }:
            if item not in found:
                found.append(item)

    return found


def normalize_package_name(name):
    name = name.strip()
    if not name:
        return ""
    name = re.split(r"[<>=!~\s\[\];,]", name, maxsplit=1)[0]
    return name.replace("_", "-").lower()


def collect_libraries(path):
    libraries = []

    package_json = path / "package.json"
    if package_json.exists():
        try:
            with package_json.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            for key in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
                if isinstance(data.get(key), dict):
                    libraries.extend(list(data[key].keys()))
        except Exception:
            pass

    requirements = path / "requirements.txt"
    if requirements.exists():
        try:
            with requirements.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    libraries.append(normalize_package_name(line))
        except Exception:
            pass

    pyproject = path / "pyproject.toml"
    if pyproject.exists() and tomllib:
        try:
            with pyproject.open("rb") as fh:
                data = tomllib.load(fh)
            for key in ["dependencies", "optional-dependencies", "dev-dependencies"]:
                if isinstance(data.get(key), dict):
                    libraries.extend(list(data[key].keys()))
        except Exception:
            pass

    pipfile = path / "Pipfile"
    if pipfile.exists():
        try:
            text = pipfile.read_text(encoding="utf-8", errors="ignore")
            matches = re.findall(r'^\s*([A-Za-z0-9_.-]+)\s*=', text, flags=re.M)
            libraries.extend(matches)
        except Exception:
            pass

    cargo = path / "Cargo.toml"
    if cargo.exists() and tomllib:
        try:
            with cargo.open("rb") as fh:
                data = tomllib.load(fh)
            for section in ["dependencies", "dev-dependencies", "build-dependencies"]:
                if isinstance(data.get(section), dict):
                    libraries.extend(list(data[section].keys()))
        except Exception:
            pass

    go_mod = path / "go.mod"
    if go_mod.exists():
        try:
            text = go_mod.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("require ") or line.startswith("require("):
                    continue
                if line and not line.startswith("//") and not line.startswith("\t"):
                    if " " in line:
                        libraries.append(line.split()[0])
        except Exception:
            pass

    pom = path / "pom.xml"
    if pom.exists():
        try:
            text = pom.read_text(encoding="utf-8", errors="ignore")
            libraries.extend(re.findall(r"<artifactId>([^<]+)</artifactId>", text))
        except Exception:
            pass

    build_gradle = path / "build.gradle"
    if build_gradle.exists():
        try:
            text = build_gradle.read_text(encoding="utf-8", errors="ignore")
            libraries.extend(re.findall(r"(?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s+[\"']([^\"']+)[\"']", text))
        except Exception:
            pass

    return sorted({lib for lib in libraries if lib})


def get_requirements_text(path):
    files = find_requirements_files(path)

    if not files:
        return "No requirements/dependency files found."

    parts = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        parts.append(f"### {file_path.name}\n{text[:4000]}")

    return "\n\n".join(parts) if parts else "No readable dependency files found."


def analyze_repository(path):
    if not path or not path.exists():
        return {
            "file_count": 0,
            "languages": [],
            "readme": "No project loaded.",
            "libraries": [],
            "license": "No license found.",
            "requirements": "No requirements/dependency files found.",
        }

    skip_dirs = {
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
    }

    files = []
    for root, dirs, files_in_dir in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        dirs.sort()
        for name in sorted(files_in_dir):
            if name.startswith(".") and name not in {".gitignore", ".editorconfig"}:
                continue
            file_path = Path(root) / name
            if file_path.is_file():
                files.append(file_path)

    lang_counts = {}
    total_lines = 0

    for file_path in files:
        ext = file_path.suffix.lower()
        language = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".jsx": "JavaScript",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".cc": "C++",
            ".cxx": "C++",
            ".h": "C/C++",
            ".hpp": "C++",
            ".cs": "C#",
            ".go": "Go",
            ".rb": "Ruby",
            ".php": "PHP",
            ".rs": "Rust",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".sass": "SASS",
            ".json": "JSON",
            ".xml": "XML",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".toml": "TOML",
            ".sh": "Shell",
            ".bash": "Shell",
            ".ps1": "PowerShell",
            ".sql": "SQL",
            ".md": "Markdown",
            ".txt": "Text",
        }.get(ext, "Other")

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue

        lines = [line for line in content.splitlines() if line.strip()]
        count = len(lines)
        lang_counts[language] = lang_counts.get(language, 0) + count
        total_lines += count

    language_stats = []
    for lang, count in sorted(lang_counts.items(), key=lambda item: item[1], reverse=True):
        percent = round((count / total_lines) * 100, 1) if total_lines else 0
        language_stats.append((lang, count, percent))

    readme_path = find_readme(path)
    readme_text = ""
    if readme_path and readme_path.exists():
        try:
            readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            readme_text = ""

    license_path = find_license(path)
    license_text = ""
    if license_path and license_path.exists():
        try:
            license_text = license_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            license_text = ""

    libraries = collect_libraries(path)
    requirements_text = get_requirements_text(path)

    return {
        "file_count": len(files),
        "languages": language_stats,
        "readme": readme_text or "No README found.",
        "libraries": libraries,
        "license": license_text or "No license found.",
        "requirements": requirements_text,
    }


def _create_ai_window(title, width=900, height=700):
    """Open a new CTkToplevel for an AI Analysis feature result."""
    window = ctk.CTkToplevel(root)
    window.title(title)
    window.geometry(f"{width}x{height}")
    window.transient(root)
    window.lift()
    window.focus_force()
    return window


def _run_ai_task(window, compute_fn, on_success, loading_text="Analyzing with Gemini...", width=900):
    """
    Run compute_fn() on a background thread (so the UI never freezes),
    then marshal the result back onto the Tk main thread via window.after.
    On any error, show a readable message in the window instead of
    crashing the app.
    """
    status_label = ctk.CTkLabel(window, text=loading_text, font=BODY, text_color="#64748b")
    status_label.pack(anchor="w", padx=16, pady=(4, 0))

    progress_bar = ctk.CTkProgressBar(window, mode="indeterminate")
    progress_bar.pack(fill="x", padx=16, pady=(6, 10))
    progress_bar.start()

    def worker():
        result = None
        error_text = None
        try:
            result = compute_fn()
        except gemini_client.GeminiConfigError as exc:
            error_text = f"AI not configured.\n\n{exc}"
        except gemini_client.GeminiNetworkError as exc:
            error_text = f"Network error while contacting Gemini.\n\n{exc}"
        except gemini_client.GeminiAPIError as exc:
            error_text = f"Gemini API error.\n\n{exc}"
        except ValueError as exc:
            error_text = str(exc)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            error_text = f"Unexpected error: {exc}"

        def finish():
            if not window.winfo_exists():
                return
            progress_bar.stop()
            progress_bar.destroy()
            status_label.destroy()

            if error_text:
                error_label = ctk.CTkLabel(
                    window,
                    text=f"⚠ {error_text}",
                    font=BODY,
                    text_color="#b91c1c",
                    wraplength=width - 60,
                    justify="left",
                )
                error_label.pack(anchor="w", padx=16, pady=16)
            else:
                on_success(result)

        window.after(0, finish)

    threading.Thread(target=worker, daemon=True).start()


def _render_text_result(window, text, mono=False):
    box = ctk.CTkTextbox(window, wrap="word", corner_radius=10)
    box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    box.insert("0.0", text)
    box.configure(state="disabled", font=FONT_CODE if mono else BODY)
    return box


def _risk_color(band):
    return {
        "Low": "#15803d",
        "Medium": "#ca8a04",
        "High": "#ea580c",
        "Critical": "#b91c1c",
    }.get(band, "#374151")


def _render_risk_badge(parent, score):
    row = ctk.CTkFrame(parent, fg_color="transparent", border_width=0)
    row.pack(fill="x", padx=16, pady=(0, 8))

    score_label = ctk.CTkLabel(
        row,
        text=f"Risk Score: {score.score}/100  ({score.band})",
        font=SUBHEADING,
        text_color=_risk_color(score.band),
    )
    score_label.pack(side="left")
    return row


def project_selection_screen():
    global window_width, window_height, window_title

    window_width = 1000
    window_height = 800
    window_title = "TRACE v1.0 - Project Selection"

    update_window()

    title_label = ctk.CTkLabel(root, text="TRACE", font=HERO)
    title_label.pack(pady=(10, 0))

    subtitle_label = ctk.CTkLabel(root, text="Tools for Reverse Analysis and Code Exploration", font=BODYBIG)
    subtitle_label.pack(pady=(0, 5))

    heading_label = ctk.CTkLabel(root, text="Select a Project", font=HEADING)
    heading_label.pack(pady=(20, 10))

    selection_frame = ctk.CTkFrame(root, width=900, height=500, corner_radius=12, border_width=1)
    selection_frame.pack(pady=(5, 10), padx=25, fill="both", expand=True)

    repo_label = ctk.CTkLabel(selection_frame, text="Kindly Enter the Repository URL:", font=BODYBIG)
    repo_label.pack(pady=(20, 5))

    repo_entry = ctk.CTkEntry(selection_frame, width=600, height=40, font=BODY)
    repo_entry.pack(pady=(0, 20))

    repo_note_label = ctk.CTkLabel(selection_frame, text="Note: The repository should be public and accessible.", font=BODY)
    repo_note_label.pack(pady=(0, 10))

    or_label = ctk.CTkLabel(selection_frame, text="OR", font=SUBHEADING)
    or_label.pack(pady=(0, 10))

    local_label = ctk.CTkLabel(selection_frame, text="Kindly Select a Local Project Directory:", font=BODYBIG)
    local_label.pack(pady=(0, 10))

    selected_project_path = None

    def update_description_labels(target_path, repo_url=None, repo_info=None):
        if repo_info is None:
            repo_info = get_github_repo_info(repo_url) if repo_url else None

        if repo_info is None and repo_url is None:
            detected_repo_url = get_directory_repo_url(target_path)
            if detected_repo_url:
                repo_info = get_github_repo_info(detected_repo_url)

        if repo_info is not None:
            project_desc_name_label.configure(text=f"Project Name: {repo_info['name']}")
            project_desc_author_label.configure(text=f"Author: {repo_info['owner']}")
            project_desc_datec_label.configure(text=f"Creation Date: {format_datetime(repo_info['created_at'])}")
            project_datem_label.configure(text=f"Last Modified Date: {format_datetime(repo_info['pushed_at'])}")
            return

        project_desc_name_label.configure(text=f"Project Name: {target_path.name}")
        project_desc_author_label.configure(text=f"Author: {get_project_author(target_path, repo_url)}")
        project_desc_datec_label.configure(text=f"Creation Date: {format_timestamp(target_path)}")
        project_datem_label.configure(text=f"Last Modified Date: {format_modified_timestamp(target_path)}")

    def select_local_directory():
        nonlocal selected_project_path
        directory = filedialog.askdirectory(title="Select a Local Project Directory")
        if directory:
            selected_project_path = Path(directory).resolve()
            update_description_labels(selected_project_path)

    local_button = ctk.CTkButton(selection_frame, text="Select Directory", font=BODY, height=50, command=select_local_directory)
    local_button.pack(pady=(10, 10))

    project_description_frame = ctk.CTkFrame(root, width=900, height=200, corner_radius=12, border_width=1)
    project_description_frame.pack(pady=(10, 20), padx=25, fill="both", expand=True)

    project_desc_name_label = ctk.CTkLabel(project_description_frame, text="Project Name: ", font=BODYBIG)
    project_desc_name_label.pack(pady=(20, 5), anchor="w", padx=20)

    project_desc_author_label = ctk.CTkLabel(project_description_frame, text="Author: ", font=BODYBIG)
    project_desc_author_label.pack(pady=(0, 5), anchor="w", padx=20)

    project_desc_datec_label = ctk.CTkLabel(project_description_frame, text="Creation Date: ", font=BODYBIG)
    project_desc_datec_label.pack(pady=(0, 5), anchor="w", padx=20)

    project_datem_label = ctk.CTkLabel(project_description_frame, text="Last Modified Date: ", font=BODYBIG)
    project_datem_label.pack(pady=(0, 5), anchor="w", padx=20)

    def load_project():
        nonlocal selected_project_path

        try:
            repo_url = repo_entry.get().strip()

            if repo_url:
                repo_info = get_github_repo_info(repo_url)
                try:
                    target_path = clone_repo(repo_url)
                except Exception:
                    target_path = PROJECTS_DIR / repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
                    target_path.mkdir(parents=True, exist_ok=True)

                global CURRENT_PROJECT_PATH, CURRENT_REPO_URL, CURRENT_REPO_INFO
                CURRENT_PROJECT_PATH = target_path
                CURRENT_REPO_URL = repo_url
                CURRENT_REPO_INFO = repo_info

                update_description_labels(target_path, repo_url=repo_url, repo_info=repo_info)
            elif selected_project_path is not None:
                target_path = selected_project_path

                CURRENT_PROJECT_PATH = target_path
                CURRENT_REPO_URL = get_directory_repo_url(target_path)
                CURRENT_REPO_INFO = get_github_repo_info(CURRENT_REPO_URL) if CURRENT_REPO_URL else None

                update_description_labels(target_path)
            else:
                raise ValueError("Please enter a repository URL or select a local directory.")

        except Exception as exc:
            project_desc_name_label.configure(text="Project Name: Error")
            project_desc_author_label.configure(text=f"Author: {exc}")
            project_desc_datec_label.configure(text="Creation Date: N/A")
            project_datem_label.configure(text="Last Modified Date: N/A")

    button_frame = ctk.CTkFrame(root, fg_color="transparent", border_width=0)
    button_frame.pack(pady=(0, 20))

    load_button = ctk.CTkButton(button_frame, text="Load Project", font=BODYBIG, text_color="white", border_width=5, height=50, width=220, command=load_project)
    load_button.pack(side="left", padx=10)

    analyse_button = ctk.CTkButton(button_frame, text="Analyse", font=BODYBIG, text_color="white", border_width=5, height=50, width=220, command=analysis_screen)
    analyse_button.pack(side="left", padx=10)


def analysis_screen():
    global window_width, window_height, window_title

    window_width = 1600
    window_height = 950
    window_title = "TRACE v1.0 - Analysis"

    update_window()

    if not CURRENT_PROJECT_PATH or not CURRENT_PROJECT_PATH.exists():
        error_label = ctk.CTkLabel(root, text="No project selected. Please load a project first.", font=BODYBIG)
        error_label.pack(expand=True)
        back_button = ctk.CTkButton(root, text="Back", command=project_selection_screen)
        back_button.pack(pady=20)
        return

    analysis = analyze_repository(CURRENT_PROJECT_PATH)

    header_frame = ctk.CTkFrame(root, fg_color="transparent", border_width=0)
    header_frame.pack(fill="x", padx=20, pady=(15, 10))

    header_row = ctk.CTkFrame(header_frame, fg_color="transparent", border_width=0)
    header_row.pack(fill="x")

    title_container = ctk.CTkFrame(header_row, fg_color="transparent", border_width=0)
    title_container.pack(side="left", fill="x", expand=True)

    title_label = ctk.CTkLabel(title_container, text=f"Analysis: {CURRENT_PROJECT_PATH.name}", font=HERO)
    title_label.pack(anchor="w")

    subtitle_label = ctk.CTkLabel(title_container, text="Repository overview", font=BODYBIG)
    subtitle_label.pack(anchor="w", pady=(5, 0))

    back_button = ctk.CTkButton(header_row, text="Back", command=project_selection_screen, width=100, height=36)
    back_button.pack(side="right")

    summary_frame = ctk.CTkFrame(root, fg_color="#ecd1b0", corner_radius=16, border_width=1)
    summary_frame.pack(fill="x", padx=20, pady=(0, 12))

    summary_inner = ctk.CTkFrame(summary_frame, fg_color="transparent", border_width=0)
    summary_inner.pack(fill="x", padx=16, pady=12)

    def add_stat_card(parent, label, value, accent):
        card = ctk.CTkFrame(parent, fg_color="#ecd1b0", corner_radius=12, border_width=1)
        card.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=4)

        card_label = ctk.CTkLabel(card, text=label, font=BODY, text_color="#64748b")
        card_label.pack(anchor="w", padx=12, pady=(10, 0))

        card_value = ctk.CTkLabel(card, text=value, font=SUBHEADING, text_color=accent)
        card_value.pack(anchor="w", padx=12, pady=(2, 10))

    add_stat_card(summary_inner, "Project", CURRENT_PROJECT_PATH.name, "#2563eb")
    add_stat_card(summary_inner, "Files", str(analysis["file_count"]), "#7c3aed")
    add_stat_card(summary_inner, "Languages", str(len(analysis["languages"])), "#802084")
    add_stat_card(summary_inner, "Dependencies", str(len(analysis["libraries"])), "#ea580c")

    content_frame = ctk.CTkFrame(root, fg_color="transparent", border_width=0)
    content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    sidebar = ctk.CTkFrame(content_frame, width=320, fg_color="#ecd1b0", corner_radius=16, border_width=0)
    sidebar.pack(side="left", fill="y", padx=(0, 12))

    main_area = ctk.CTkFrame(content_frame, fg_color="transparent", border_width=0)
    main_area.pack(side="right", fill="both", expand=True)

    sidebar_title = ctk.CTkLabel(sidebar, text="Project Files", font=SUBHEADING)
    sidebar_title.pack(anchor="w", padx=14, pady=(12, 6))

    sidebar_subtitle = ctk.CTkLabel(sidebar, text="Browse the repository structure", font=BODY)
    sidebar_subtitle.pack(anchor="w", padx=14, pady=(0, 8))

    ai_section = ctk.CTkFrame(sidebar, fg_color="#ecd1b0", corner_radius=12, border_width=0)
    ai_section.pack(fill="x", padx=10, pady=(0, 10))

    ai_section_title = ctk.CTkLabel(ai_section, text="AI Analysis", font=SUBHEADING)
    ai_section_title.pack(anchor="w", padx=4, pady=(6, 0))

    ai_section_subtitle = ctk.CTkLabel(
        ai_section, text="Digital forensics & repository intelligence", font=BODY
    )
    ai_section_subtitle.pack(anchor="w", padx=4, pady=(0, 8))

    def add_ai_button(label, command):
        button = ctk.CTkButton(
            ai_section,
            text=label,
            height=32,
            corner_radius=10,
            command=command,
        )
        button.pack(fill="x", padx=4, pady=3)
        return button

    add_ai_button("🧠 Repository Summary", lambda: open_repository_summary())
    add_ai_button("📄 Explain File", lambda: open_explain_file())
    add_ai_button("💬 Repository Chat", lambda: open_repository_chat())
    add_ai_button("🛡️ Threat Scan", lambda: open_threat_scan())
    add_ai_button("🔑 Secret Scan", lambda: open_secret_scan())
    add_ai_button("📋 Generate Report", lambda: open_generate_report())

    tree_area = ctk.CTkScrollableFrame(sidebar, width=450, height=640, fg_color="#ecd1b0", corner_radius=12, border_width=0 )
    tree_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    selected_file = None
    current_tab = "code"
    ai_state = {"summary": None, "secrets": None, "threats": None}

    def select_file(file_path):
        nonlocal selected_file
        selected_file = file_path
        render_content()


    def open_repository_summary():
        window = _create_ai_window(
            f"AI Repository Summary — {CURRENT_PROJECT_PATH.name}", width=900, height=700
        )

        header = ctk.CTkLabel(window, text="AI Repository Summary", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        def compute():
            result = repository_summary.generate_repository_summary(CURRENT_PROJECT_PATH)
            ai_state["summary"] = result
            return result

        def on_success(result):
            _render_text_result(window, result)

        _run_ai_task(window, compute, on_success, width=900)

    def open_explain_file():
        if not selected_file or not selected_file.exists():
            messagebox.showinfo("Explain File", "Select a file from the sidebar first.")
            return

        window = _create_ai_window(f"Explain File — {selected_file.name}", width=900, height=700)

        try:
            rel_path = selected_file.relative_to(CURRENT_PROJECT_PATH)
        except Exception:
            rel_path = selected_file.name

        header = ctk.CTkLabel(window, text=f"Explaining: {rel_path}", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        def compute():
            return file_explainer.explain_file(selected_file, CURRENT_PROJECT_PATH)

        def on_success(result):
            _render_text_result(window, result)

        _run_ai_task(window, compute, on_success, width=900)

    def open_repository_chat():
        window = _create_ai_window(
            f"Repository Chat — {CURRENT_PROJECT_PATH.name}", width=900, height=700
        )

        header = ctk.CTkLabel(window, text="Repository Chat", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        hint = ctk.CTkLabel(
            window,
            text='Ask about this codebase, e.g. "What starts the application?" or '
                 '"Where is the database initialized?"',
            font=BODY,
            text_color="#64748b",
            wraplength=860,
            justify="left",
        )
        hint.pack(anchor="w", padx=16, pady=(0, 8))

        transcript = ctk.CTkTextbox(window, wrap="word", corner_radius=10, font=BODY)
        transcript.configure(state="disabled")
        transcript.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        input_row = ctk.CTkFrame(window, fg_color="transparent", border_width=0)
        input_row.pack(fill="x", padx=16, pady=(0, 16))

        entry = ctk.CTkEntry(
            input_row, font=BODY, placeholder_text="Ask a question about this repository..."
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        session = repository_chat.RepositoryChatSession(CURRENT_PROJECT_PATH)

        def append_line(speaker, text):
            transcript.configure(state="normal")
            transcript.insert("end", f"{speaker}: {text}\n\n")
            transcript.configure(state="disabled")
            transcript.see("end")

        def send_message(event=None):
            question = entry.get().strip()
            if not question:
                return

            entry.delete(0, "end")
            append_line("You", question)
            send_button.configure(state="disabled")
            entry.configure(state="disabled")

            def worker():
                answer = None
                error_text = None
                try:
                    answer = session.ask(question)
                except gemini_client.GeminiConfigError as exc:
                    error_text = f"AI not configured. {exc}"
                except gemini_client.GeminiNetworkError as exc:
                    error_text = f"Network error: {exc}"
                except gemini_client.GeminiAPIError as exc:
                    error_text = f"Gemini error: {exc}"
                except ValueError as exc:
                    error_text = str(exc)
                except Exception as exc:  # noqa: BLE001
                    error_text = f"Unexpected error: {exc}"

                def finish():
                    if not window.winfo_exists():
                        return
                    if error_text:
                        append_line("TRACE AI", f"⚠ {error_text}")
                    else:
                        append_line("TRACE AI", answer)
                    send_button.configure(state="normal")
                    entry.configure(state="normal")
                    entry.focus_set()

                window.after(0, finish)

            threading.Thread(target=worker, daemon=True).start()

        send_button = ctk.CTkButton(input_row, text="Send", width=90, command=send_message)
        send_button.pack(side="left")

        entry.bind("<Return>", send_message)
        entry.focus_set()

    def open_threat_scan():
        window = _create_ai_window(
            f"Threat Scan — {CURRENT_PROJECT_PATH.name}", width=1000, height=750
        )

        header = ctk.CTkLabel(window, text="Threat Scan", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        status_label = ctk.CTkLabel(
            window, text="Scanning source files for dangerous API usage...",
            font=BODY, text_color="#64748b",
        )
        status_label.pack(anchor="w", padx=16)

        progress_bar = ctk.CTkProgressBar(window, mode="indeterminate")
        progress_bar.pack(fill="x", padx=16, pady=(6, 10))
        progress_bar.start()

        def worker():
            findings = None
            score = None
            observations = None
            error_text = None
            try:
                findings = threat_scanner.scan_repository(CURRENT_PROJECT_PATH)
                ai_state["threats"] = findings
                score = risk_score.compute_risk_score(ai_state.get("secrets") or [], findings)
                if findings and gemini_client.is_configured():
                    try:
                        observations = threat_scanner.get_ai_observations(findings)
                    except gemini_client.GeminiError:
                        observations = None
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)

            def finish():
                if not window.winfo_exists():
                    return
                progress_bar.stop()
                progress_bar.destroy()
                status_label.destroy()

                if error_text:
                    ctk.CTkLabel(
                        window, text=f"⚠ {error_text}", font=BODY, text_color="#b91c1c",
                        wraplength=940, justify="left",
                    ).pack(anchor="w", padx=16, pady=16)
                    return

                _render_risk_badge(window, score)
                count_label = ctk.CTkLabel(
                    window, text=f"{len(findings)} finding(s)", font=BODY, text_color="#64748b"
                )
                count_label.pack(anchor="w", padx=16, pady=(0, 8))

                lines = []
                if not findings:
                    lines.append("No suspicious API usage was detected.")
                else:
                    for finding in findings:
                        lines.append(f"[{finding.threat_level}] {finding.file}:{finding.line}  —  {finding.pattern}")
                        lines.append(f"    Reason: {finding.reason}")
                        lines.append(f"    Potential abuse: {finding.potential_abuse}")
                        lines.append(f"    Code: {finding.snippet}")
                        lines.append("")

                if observations:
                    lines.append("=" * 60)
                    lines.append("AI ANALYST OBSERVATIONS")
                    lines.append("=" * 60)
                    lines.append(observations)
                elif findings and not gemini_client.is_configured():
                    lines.append(
                        "(Configure GEMINI_API_KEY to get AI analyst commentary on these findings.)"
                    )

                _render_text_result(window, "\n".join(lines), mono=True)

            window.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def open_secret_scan():
        window = _create_ai_window(
            f"Secret Scan — {CURRENT_PROJECT_PATH.name}", width=1000, height=750
        )

        header = ctk.CTkLabel(window, text="Secret Scan", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        status_label = ctk.CTkLabel(
            window, text="Scanning source files for exposed secrets...",
            font=BODY, text_color="#64748b",
        )
        status_label.pack(anchor="w", padx=16)

        progress_bar = ctk.CTkProgressBar(window, mode="indeterminate")
        progress_bar.pack(fill="x", padx=16, pady=(6, 10))
        progress_bar.start()

        def worker():
            findings = None
            score = None
            error_text = None
            try:
                findings = secret_scanner.scan_repository(CURRENT_PROJECT_PATH)
                ai_state["secrets"] = findings
                score = risk_score.compute_risk_score(findings, ai_state.get("threats") or [])
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)

            def finish():
                if not window.winfo_exists():
                    return
                progress_bar.stop()
                progress_bar.destroy()
                status_label.destroy()

                if error_text:
                    ctk.CTkLabel(
                        window, text=f"⚠ {error_text}", font=BODY, text_color="#b91c1c",
                        wraplength=940, justify="left",
                    ).pack(anchor="w", padx=16, pady=16)
                    return

                _render_risk_badge(window, score)
                count_label = ctk.CTkLabel(
                    window, text=f"{len(findings)} finding(s)", font=BODY, text_color="#64748b"
                )
                count_label.pack(anchor="w", padx=16, pady=(0, 8))

                lines = []
                if not findings:
                    lines.append("No secrets were detected.")
                else:
                    for finding in findings:
                        lines.append(f"[{finding.severity}] {finding.file}:{finding.line}  —  {finding.match_type}")
                        lines.append(f"    {finding.explanation}")
                        lines.append(f"    Match: {finding.snippet}")
                        lines.append("")

                _render_text_result(window, "\n".join(lines), mono=True)

            window.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def open_generate_report():
        window = _create_ai_window(
            f"Forensic Report — {CURRENT_PROJECT_PATH.name}", width=900, height=750
        )

        header = ctk.CTkLabel(window, text="Forensic Report", font=SUBHEADING)
        header.pack(anchor="w", padx=16, pady=(16, 4))

        status_label = ctk.CTkLabel(
            window, text="Gathering repository summary and running scans...",
            font=BODY, text_color="#64748b",
        )
        status_label.pack(anchor="w", padx=16)

        progress_bar = ctk.CTkProgressBar(window, mode="indeterminate")
        progress_bar.pack(fill="x", padx=16, pady=(6, 10))
        progress_bar.start()

        def worker():
            report_text = None
            error_text = None
            try:
                summary_text = ai_state.get("summary")
                if summary_text is None and gemini_client.is_configured():
                    try:
                        summary_text = repository_summary.generate_repository_summary(
                            CURRENT_PROJECT_PATH
                        )
                        ai_state["summary"] = summary_text
                    except gemini_client.GeminiError:
                        summary_text = None

                secrets = ai_state.get("secrets")
                if secrets is None:
                    secrets = secret_scanner.scan_repository(CURRENT_PROJECT_PATH)
                    ai_state["secrets"] = secrets

                threats = ai_state.get("threats")
                if threats is None:
                    threats = threat_scanner.scan_repository(CURRENT_PROJECT_PATH)
                    ai_state["threats"] = threats

                score = risk_score.compute_risk_score(secrets, threats)

                observations = None
                if gemini_client.is_configured():
                    try:
                        observations = forensic_report.get_ai_observations(
                            summary_text, score, secrets, threats
                        )
                    except gemini_client.GeminiError:
                        observations = None

                report_text = forensic_report.generate_report(
                    project_name=CURRENT_PROJECT_PATH.name,
                    project_path=CURRENT_PROJECT_PATH,
                    repo_summary=summary_text,
                    risk=score,
                    secret_findings=secrets,
                    threat_findings=threats,
                    ai_observations=observations,
                )
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)

            def finish():
                if not window.winfo_exists():
                    return
                progress_bar.stop()
                progress_bar.destroy()
                status_label.destroy()

                if error_text:
                    ctk.CTkLabel(
                        window, text=f"⚠ {error_text}", font=BODY, text_color="#b91c1c",
                        wraplength=840, justify="left",
                    ).pack(anchor="w", padx=16, pady=16)
                    return

                box = _render_text_result(window, report_text, mono=True)

                def export():
                    path = filedialog.asksaveasfilename(
                        title="Export Forensic Report",
                        defaultextension=".md",
                        filetypes=[("Markdown", "*.md"), ("All Files", "*.*")],
                        initialfile=f"{CURRENT_PROJECT_PATH.name}_forensic_report.md",
                    )
                    if not path:
                        return
                    try:
                        forensic_report.export_markdown(report_text, Path(path))
                        messagebox.showinfo("Report Exported", f"Report saved to:\n{path}")
                    except Exception as exc:  # noqa: BLE001
                        messagebox.showerror("Export Failed", str(exc))

                export_row = ctk.CTkFrame(window, fg_color="transparent", border_width=0)
                export_row.pack(pady=(0, 16))

                export_button = ctk.CTkButton(
                    export_row, text="Export as Markdown", height=40, command=export
                )
                export_button.pack()

            window.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def add_tree(parent_frame, path, prefix=""):
        if path.is_dir():
            folder_label = ctk.CTkButton(
                parent_frame,
                text=f"{prefix}📁 {path.name}",
                fg_color="#ecd1b0",
                hover_color="#ecd1b0",
                border_width=0,
                anchor="w",
                command=lambda: None,
                font=BODY
            )
            folder_label.pack(anchor="w", padx=6, pady=2)

            for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                if child.name in {".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", "target", ".idea", ".vscode"}:
                    continue
                add_tree(parent_frame, child, prefix + "  ")
        else:
            try:
                rel_path = path.relative_to(CURRENT_PROJECT_PATH)
            except Exception:
                rel_path = path.name

            file_button = ctk.CTkButton(
                parent_frame,
                text=f"{prefix}📄 {rel_path}",
                fg_color="#ecd1b0",
                hover_color="#e0b47e",
                border_width=0,
                anchor="w",
                command=lambda p=path: select_file(p),
                font=FONT_CODE
            )
            file_button.pack(anchor="w", padx=6, pady=2)

    add_tree(tree_area, CURRENT_PROJECT_PATH)

    tab_frame = ctk.CTkFrame(main_area, fg_color="transparent", border_width=0)
    tab_frame.pack(fill="x", pady=(0, 8))

    tab_buttons = {}

    def set_tab(tab_name):
        nonlocal current_tab
        current_tab = tab_name
        render_content()

    def update_tab_style():
        for name, button in tab_buttons.items():
            if name == current_tab:
                button.configure( hover_color="#791118", text_color="white", border_width=3)
            else:
                button.configure(hover_color="#791118", text_color="#ffffff", border_width=0)

    tab_names = {
        "code": "Code",
        "readme": "README",
        "lang": "Languages",
        "license": "License",
        "libs": "Libraries",
        "requirements": "Requirements",
    }

    for name, label in tab_names.items():
        button = ctk.CTkButton(
            tab_frame,
            text=label,
            width=110,
            height=34,
            corner_radius=10,
            command=lambda n=name: set_tab(n),
        )
        button.pack(side="left", padx=4)
        tab_buttons[name] = button

    content_panel = ctk.CTkFrame(main_area, fg_color="#e0b47e", corner_radius=16, border_width=2)
    content_panel.pack(fill="both", expand=True)

    def render_content():
        for widget in content_panel.winfo_children():
            widget.destroy()

        update_tab_style()

        

        if current_tab == "code":
            if selected_file and selected_file.exists():

                extension = selected_file.suffix.lower()

                if extension in IMAGE_EXTENSIONS:

                    title = ctk.CTkLabel(
                        content_panel,
                        text="Image Preview",
                        font=SUBHEADING,
                    )
                    title.pack(anchor="w", padx=12, pady=(10, 6))

                    image = Image.open(selected_file)

                    MAX_WIDTH = 900
                    MAX_HEIGHT = 600

                    w, h = image.size

                    scale = min(
                        MAX_WIDTH / w,
                        MAX_HEIGHT / h,
                        1,
                    )

                    preview = ctk.CTkImage(
                        light_image=image,
                        dark_image=image,
                        size=(int(w * scale), int(h * scale)),
                    )

                    image_label = ctk.CTkLabel(
                        content_panel,
                        image=preview,
                        text="",
                    )

                    image_label.pack(expand=True)

                    return

                try:
                    text = selected_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = "Unable to read this file."

                try:
                    rel_path = selected_file.relative_to(CURRENT_PROJECT_PATH)
                except Exception:
                    rel_path = selected_file.name

                title = ctk.CTkLabel(content_panel, text=f"Code Preview", font=SUBHEADING, border_width=0)
                title.pack(anchor="w", padx=12, pady=(10, 6))

                meta_frame = ctk.CTkFrame(content_panel, fg_color="transparent", border_width=0)
                meta_frame.pack(fill="x", padx=12, pady=(0, 8))

                meta_label = ctk.CTkLabel(meta_frame, text=f"File: {rel_path}", font=BODY)
                meta_label.pack(anchor="w")

                code_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
                code_box.insert("0.0", text[:14000])
                code_box.configure(state="disabled", font=FONT_CODE)
                code_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            else:
                empty_label = ctk.CTkLabel(content_panel, text="Select a file from the sidebar to view its contents.", font=BODYBIG, text_color="#64748b")
                empty_label.pack(expand=True)

        elif current_tab == "readme":
            title = ctk.CTkLabel(content_panel, text="README", font=SUBHEADING, text_color="#111827")
            title.pack(anchor="w", padx=12, pady=(10, 6))

            readme_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
            readme_box.insert("0.0", analysis["readme"][:14000])
            readme_box.configure(state="disabled", font=BODY)
            readme_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        elif current_tab == "lang":
            title = ctk.CTkLabel(content_panel, text="Language Breakdown", font=SUBHEADING, text_color="#111827")
            title.pack(anchor="w", padx=12, pady=(10, 6))

            lang_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
            if analysis["languages"]:
                for lang, count, percent in analysis["languages"]:
                    lang_box.insert("end", f"{lang}: {count} lines ({percent}%)\n")
            else:
                lang_box.insert("end", "No code files detected.")
            lang_box.configure(state="disabled", font=BODY)
            lang_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        elif current_tab == "license":
            title = ctk.CTkLabel(content_panel, text="License", font=SUBHEADING, text_color="#111827")
            title.pack(anchor="w", padx=12, pady=(10, 6))

            license_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
            license_box.insert("0.0", analysis["license"][:14000] if analysis["license"] else "No license found.")
            license_box.configure(state="disabled", font=BODY)
            license_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        elif current_tab == "libs":
            title = ctk.CTkLabel(content_panel, text="Libraries / Dependencies", font=SUBHEADING, text_color="#111827")
            title.pack(anchor="w", padx=12, pady=(10, 6))

            libs_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
            if analysis["libraries"]:
                libs_box.insert("end", "\n".join(analysis["libraries"]))
            else:
                libs_box.insert("end", "No dependency files detected.")
            libs_box.configure(state="disabled", font=BODY)
            libs_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        elif current_tab == "requirements":
            title = ctk.CTkLabel(content_panel, text="Requirements / Dependency Files", font=SUBHEADING, text_color="#111827")
            title.pack(anchor="w", padx=12, pady=(10, 6))

            req_box = ctk.CTkTextbox(content_panel, height=560, wrap="word", corner_radius=10)
            req_box.insert("0.0", analysis["requirements"][:14000])
            req_box.configure(state="disabled", font=BODY)
            req_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    render_content()


def loading_screen():
    global window_width, window_height, window_title

    window_width = 600
    window_height = 600
    window_title = "TRACE v1.0 - Loading"

    update_window()

    title_label = ctk.CTkLabel(root, text="TRACE", font=HERO)
    title_label.pack(pady=(10, 0))

    subtitle_label = ctk.CTkLabel(root, text="Tools for Reverse Analysis and Code Exploration", font=BODYBIG)
    subtitle_label.pack(pady=(0, 5))

    credit_label = ctk.CTkLabel(root, text="Created by Akshat J & Mridul T.", font=SUBHEADING)
    credit_label.pack(pady=(0, 20))

    logo_path = BASE_DIR / "logo.png"
    logo_image = ctk.CTkImage(
        light_image=Image.open(str(logo_path)),
        dark_image=Image.open(str(logo_path)),
        size=(300, 300)
    )

    image_label = ctk.CTkLabel(root, image=logo_image, text="")
    image_label.pack(pady=(0, 15))

    loading_label = ctk.CTkLabel(root, text="Loading.", font=SUBTITLE)
    loading_label.pack(side="bottom", pady=(0, 20))

    loading_bar = ctk.CTkProgressBar(root, width=400, height=20, mode="indeterminate")
    loading_bar.start()
    loading_bar.pack(side="bottom", pady=(0, 10))

    def animate_loading():
        if not loading_label.winfo_exists():
            return

        dots = "." * (animate_loading.count % 4)
        loading_label.configure(text=f"Loading{dots}")

        animate_loading.count += 1
        root.after(300, animate_loading)

    animate_loading.count = 0
    animate_loading()

# Open next screen after 3 seconds
root.after(3000, project_selection_screen)


def main():
    loading_screen()


if __name__ == "__main__":
    main()
    root.mainloop()