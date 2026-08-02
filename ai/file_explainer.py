from __future__ import annotations

from pathlib import Path

from . import gemini_client, prompts, repository_context


def explain_file(file_path: Path, project_path: Path | None = None) -> str:
    if not file_path or not file_path.exists():
        raise ValueError("No file is selected.")

    if repository_context.is_probably_binary(file_path):
        raise ValueError("This is a binary/image file and cannot be explained.")

    try:
        if file_path.stat().st_size > repository_context.MAX_FILE_SIZE:
            raise ValueError(
                "This file is larger than 2 MB and was skipped for performance."
            )
    except OSError:
        pass

    text = repository_context.read_text_safe(file_path, max_chars=12000)
    if not text.strip():
        raise ValueError("This file is empty or unreadable.")

    if project_path:
        try:
            relative_path = str(file_path.relative_to(project_path))
        except ValueError:
            relative_path = file_path.name
    else:
        relative_path = file_path.name

    prompt = prompts.build_explain_file_prompt(relative_path, text)

    return gemini_client.generate(
        prompt, system_instruction=prompts.SUMMARY_SYSTEM_INSTRUCTION
    )
