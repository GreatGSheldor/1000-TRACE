
from __future__ import annotations

from pathlib import Path

from . import gemini_client, prompts, repository_context

MAX_HISTORY_TURNS = 6
MAX_CONTEXT_FILES = 5


class RepositoryChatSession:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.history: list[tuple[str, str]] = []  # [(role, text), ...]

    def ask(self, question: str) -> str:
        if not question or not question.strip():
            raise ValueError("Please enter a question.")

        if not self.project_path or not self.project_path.exists():
            raise ValueError("No project is loaded.")

        relevant_files = repository_context.keyword_search(
            self.project_path, question, limit=MAX_CONTEXT_FILES
        )
        context_text = self._format_context(relevant_files)
        history_text = self._format_history()

        prompt = prompts.build_chat_prompt(
            history_text=history_text,
            context_text=context_text,
            question=question,
        )

        answer = gemini_client.generate(
            prompt, system_instruction=prompts.CHAT_SYSTEM_INSTRUCTION
        )

        self.history.append(("user", question))
        self.history.append(("assistant", answer))
        self.history = self.history[-(MAX_HISTORY_TURNS * 2):]

        return answer

    def _format_context(self, files: list[Path]) -> str:
        parts = []
        for file_path in files:
            try:
                rel = file_path.relative_to(self.project_path)
            except ValueError:
                rel = file_path.name
            text = repository_context.read_text_safe(file_path, max_chars=2500)
            parts.append(f"### {rel}\n{text}")
        return "\n\n".join(parts)

    def _format_history(self) -> str:
        lines = []
        for role, text in self.history[-(MAX_HISTORY_TURNS * 2):]:
            speaker = "User" if role == "user" else "Assistant"
            lines.append(f"{speaker}: {text}")
        return "\n".join(lines)
