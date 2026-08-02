
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import gemini_client, prompts, repository_context

# (name, compiled regex, threat_level, reason, potential_abuse)
_PATTERNS = [
    (
        "eval()",
        re.compile(r"\beval\s*\("),
        "Critical",
        "Executes arbitrary strings as code at runtime.",
        "Can run attacker-controlled code if the input isn't fully trusted.",
    ),
    (
        "exec()",
        re.compile(r"\bexec\s*\("),
        "Critical",
        "Executes arbitrary Python source at runtime.",
        "Same risk profile as eval(); commonly used to hide malicious payloads.",
    ),
    (
        "os.system()",
        re.compile(r"\bos\.system\s*\("),
        "High",
        "Runs a command through the system shell.",
        "Command injection if any part of the string comes from user input.",
    ),
    (
        "subprocess",
        re.compile(r"\bsubprocess\.(run|call|Popen|check_output|check_call)\s*\("),
        "Medium",
        "Spawns an external process.",
        "Can be abused for command execution or shell injection if "
        "shell=True is combined with untrusted input.",
    ),
    (
        "pickle.loads()",
        re.compile(r"\bpickle\.(loads|load)\s*\("),
        "High",
        "Deserializes Python objects from a byte stream.",
        "Untrusted pickle data can execute arbitrary code on load.",
    ),
    (
        "marshal",
        re.compile(r"\bmarshal\.(loads|load)\s*\("),
        "High",
        "Deserializes Python bytecode/objects.",
        "Commonly used to hide/obfuscate malicious payloads.",
    ),
    (
        "socket",
        re.compile(r"\bsocket\.socket\s*\("),
        "Medium",
        "Opens a raw network socket.",
        "Could be used for unauthorized network communication, "
        "exfiltration, or a reverse shell.",
    ),
    (
        "requests",
        re.compile(r"\brequests\.(get|post|put|delete|patch)\s*\("),
        "Low",
        "Makes an outbound HTTP request.",
        "Legitimate in most apps, but can exfiltrate data if pointed at an "
        "attacker-controlled endpoint.",
    ),
    (
        "ctypes",
        re.compile(r"\bctypes\.(CDLL|WinDLL|windll|cdll)\b"),
        "High",
        "Loads and calls native code directly.",
        "Can bypass Python-level protections and interact directly with "
        "the OS/hardware.",
    ),
    (
        "base64 (decode)",
        re.compile(r"\bbase64\.(b64decode|b32decode|b16decode)\s*\("),
        "Low",
        "Decodes base64-encoded data.",
        "Frequently used to hide strings, commands, or payloads from "
        "casual inspection.",
    ),
    (
        "PowerShell invocation",
        re.compile(r"(?i)powershell(\.exe)?\s+.*-(enc|encodedcommand)\b|invoke-expression|iex\s*\("),
        "Critical",
        "Invokes PowerShell with an encoded/obfuscated command.",
        "A very common technique for delivering and hiding malicious "
        "payloads on Windows.",
    ),
    (
        "Windows Registry Access",
        re.compile(r"\bwinreg\.|HKEY_[A-Z_]+"),
        "Medium",
        "Reads or writes the Windows Registry.",
        "Can be used for persistence (e.g. run keys) or to disable "
        "security settings.",
    ),
]

THREAT_LEVEL_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass
class ThreatFinding:
    file: str
    line: int
    pattern: str
    threat_level: str
    reason: str
    potential_abuse: str
    snippet: str


def scan_repository(project_path: Path, progress_callback=None) -> list[ThreatFinding]:
    findings: list[ThreatFinding] = []

    files = list(repository_context.iter_source_files(project_path))
    total = max(len(files), 1)

    for index, file_path in enumerate(files, start=1):
        if progress_callback:
            try:
                progress_callback(index, total, file_path)
            except Exception:
                pass

        if file_path.suffix.lower() not in {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bash", ".ps1",
            ".java", ".rb", ".php", ".go", ".c", ".cpp", ".cs",
        }:
            continue

        text = repository_context.read_text_safe(file_path, max_chars=500000)
        if not text:
            continue

        try:
            rel_path = str(file_path.relative_to(project_path))
        except ValueError:
            rel_path = file_path.name

        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for name, pattern, level, reason, abuse in _PATTERNS:
                if pattern.search(line):
                    findings.append(
                        ThreatFinding(
                            file=rel_path,
                            line=line_number,
                            pattern=name,
                            threat_level=level,
                            reason=reason,
                            potential_abuse=abuse,
                            snippet=stripped[:160],
                        )
                    )

    findings.sort(
        key=lambda f: (THREAT_LEVEL_ORDER.get(f.threat_level, 9), f.file, f.line)
    )
    return findings


def summarize_findings_for_prompt(findings: list[ThreatFinding], limit: int = 40) -> str:
    lines = []
    for finding in findings[:limit]:
        lines.append(
            f"- [{finding.threat_level}] {finding.pattern} in "
            f"{finding.file}:{finding.line} -> `{finding.snippet}`"
        )
    if len(findings) > limit:
        lines.append(f"... and {len(findings) - limit} more findings.")
    return "\n".join(lines) if lines else "No suspicious patterns were found."


def get_ai_observations(findings: list[ThreatFinding]) -> str:
    """
    Optional Gemini pass over a *summary* of findings (never raw source).
    Raises gemini_client.GeminiError - callers should catch it and fall
    back to showing the static findings alone.
    """
    summary = summarize_findings_for_prompt(findings)
    prompt = prompts.build_threat_reasoning_prompt(summary)
    return gemini_client.generate(
        prompt, system_instruction=prompts.THREAT_SYSTEM_INSTRUCTION
    )
