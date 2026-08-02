
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import repository_context

# (name, compiled regex, severity, explanation)
_PATTERNS = [
    (
        "AWS Access Key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "Critical",
        "Matches the AWS Access Key ID format. If real and committed to "
        "source control, it should be revoked immediately.",
    ),
    (
        "AWS Secret Key",
        re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
        "Critical",
        "Looks like an AWS secret access key assigned in code/config.",
    ),
    (
        "Google / Gemini API Key",
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        "High",
        "Matches Google's API key format (used by Gemini, Maps, and other "
        "Google Cloud APIs).",
    ),
    (
        "Gemini API Key Assignment",
        re.compile(r"(?i)gemini_api_key\s*[:=]\s*['\"][^'\"]{10,}['\"]"),
        "High",
        "A Gemini API key appears to be hardcoded rather than loaded from "
        "an environment variable.",
    ),
    (
        "JWT Token",
        re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
        "Medium",
        "Matches the structure of a JSON Web Token (header.payload.signature).",
    ),
    (
        "Private Key",
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
        "Critical",
        "A PEM-formatted private key block was found in the repository.",
    ),
    (
        "Hardcoded Password",
        re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
        "High",
        "A password-like value is assigned directly in source/config.",
    ),
    (
        "Bearer Token",
        re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_.=]{10,}"),
        "Medium",
        "An HTTP Bearer authorization token appears to be hardcoded.",
    ),
    (
        "MongoDB URI",
        re.compile(r"mongodb(\+srv)?://[^\s'\"]+"),
        "High",
        "A MongoDB connection string was found, which may embed "
        "credentials in the host portion of the URI.",
    ),
    (
        "Database Connection String",
        re.compile(r"(?i)(postgres|postgresql|mysql|mssql|redis)://[^:\s]+:[^@\s]+@"),
        "High",
        "A database connection string with an embedded username/password "
        "was found.",
    ),
]

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass
class SecretFinding:
    file: str
    line: int
    match_type: str
    severity: str
    explanation: str
    snippet: str


def scan_repository(project_path: Path, progress_callback=None) -> list[SecretFinding]:
    findings: list[SecretFinding] = []

    files = list(repository_context.iter_source_files(project_path))
    total = max(len(files), 1)

    for index, file_path in enumerate(files, start=1):
        if progress_callback:
            try:
                progress_callback(index, total, file_path)
            except Exception:
                pass

        text = repository_context.read_text_safe(file_path, max_chars=500000)
        if not text:
            continue

        try:
            rel_path = str(file_path.relative_to(project_path))
        except ValueError:
            rel_path = file_path.name

        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern, severity, explanation in _PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            file=rel_path,
                            line=line_number,
                            match_type=name,
                            severity=severity,
                            explanation=explanation,
                            snippet=_redact(line.strip())[:160],
                        )
                    )

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line))
    return findings


def _redact(line: str) -> str:
    """Avoid printing the full secret value back into the UI/report."""
    if len(line) <= 20:
        return line[:6] + "…[redacted]"
    return line[:20] + "…[redacted]"
