
from __future__ import annotations

from pathlib import Path

from . import gemini_client, prompts, repository_context


def generate_repository_summary(project_path: Path) -> str:
    """
    Build repository context and ask Gemini for a structured summary.
    Raises gemini_client.GeminiError subclasses on failure - callers
    should catch ``gemini_client.GeminiError``.
    """

    if not project_path or not project_path.exists():
        raise ValueError("No project is loaded.")

    tree_text = repository_context.build_repository_tree_text(project_path)

    readme_path = _find_readme(project_path)
    readme_text = repository_context.read_text_safe(readme_path, 4000) if readme_path else ""

    dependency_text = _gather_dependency_text(project_path)

    key_files = repository_context.pick_important_source_files(project_path, limit=6)
    key_files_text = _format_key_files(project_path, key_files)

    prompt = prompts.build_summary_prompt(
        repo_name=project_path.name,
        tree_text=tree_text,
        readme_text=readme_text,
        dependency_text=dependency_text,
        key_files_text=key_files_text,
    )

    return gemini_client.generate(
        prompt, system_instruction=prompts.SUMMARY_SYSTEM_INSTRUCTION
    )


def _find_readme(project_path: Path) -> Path | None:
    for name in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        candidate = project_path / name
        if candidate.exists():
            return candidate
    return None


def _gather_dependency_text(project_path: Path) -> str:
    candidates = [
        "requirements.txt", "pyproject.toml", "Pipfile", "package.json",
        "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    ]
    parts = []
    for name in candidates:
        file_path = project_path / name
        if file_path.exists():
            text = repository_context.read_text_safe(file_path, 1500)
            parts.append(f"### {name}\n{text}")
    return "\n\n".join(parts)


def _format_key_files(project_path: Path, files: list[Path]) -> str:
    parts = []
    for file_path in files:
        try:
            rel = file_path.relative_to(project_path)
        except ValueError:
            rel = file_path.name
        text = repository_context.read_text_safe(file_path, 1800)
        parts.append(f"### {rel}\n{text}")
    return "\n\n".join(parts)
