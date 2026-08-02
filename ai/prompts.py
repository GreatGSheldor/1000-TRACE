"""
All prompt templates in one place, so tone/format is consistent and easy
to tune without hunting through every feature module.
"""

from __future__ import annotations

SUMMARY_SYSTEM_INSTRUCTION = (
    "You are a senior software engineer performing a repository review for "
    "a digital forensics tool. Be precise, factual, and concise. If the "
    "provided context is insufficient to know something for certain, say "
    "so instead of guessing."
)

CHAT_SYSTEM_INSTRUCTION = (
    "You are TRACE's repository assistant. Answer questions about the "
    "codebase using ONLY the file excerpts you are given. If the excerpts "
    "don't contain the answer, say you're not sure rather than inventing "
    "details. Keep answers focused and reference file names when relevant."
)

THREAT_SYSTEM_INSTRUCTION = (
    "You are a cybersecurity analyst assisting with static code review for "
    "a digital forensics tool. Explain findings clearly for a reviewer who "
    "is not a security expert, without being alarmist about routine, safe "
    "usage."
)

REPORT_SYSTEM_INSTRUCTION = (
    "You are a digital forensics analyst writing the observations section "
    "of a forensic report. Be objective, evidence-based, and concise."
)


def build_summary_prompt(repo_name: str, tree_text: str, readme_text: str,
                          dependency_text: str, key_files_text: str) -> str:
    return f"""Analyze this repository and produce a clear technical summary.

Repository name: {repo_name}

--- FOLDER STRUCTURE ---
{tree_text}

--- README (may be empty) ---
{readme_text[:4000] or "(no README found)"}

--- DEPENDENCY FILES ---
{dependency_text[:3000] or "(no dependency files found)"}

--- KEY SOURCE FILES (entry points + largest files) ---
{key_files_text[:8000]}

Respond in this exact structure, using Markdown headings:

## Project Purpose
## Framework(s)
## Programming Languages
## Entry Point
## Architecture Overview
## Folder Structure Summary
## Important Files
## Dependencies Summary
"""


def build_explain_file_prompt(relative_path: str, file_text: str) -> str:
    return f"""Explain the following source file in detail.

File: {relative_path}

--- FILE CONTENTS ---
{file_text}

Respond in this exact structure, using Markdown headings:

## Purpose
## Functions
## Classes
## Execution Flow
## Potential Bugs
## Possible Improvements

If a section does not apply (e.g. no classes), say "None found" under it.
"""


def build_chat_prompt(history_text: str, context_text: str, question: str) -> str:
    return f"""--- CONVERSATION SO FAR ---
{history_text or "(no previous messages)"}

--- RELEVANT REPOSITORY CONTEXT ---
{context_text or "(no matching files were found for this question)"}

--- USER QUESTION ---
{question}

Answer the user's question using only the context above.
"""


def build_threat_reasoning_prompt(findings_summary: str) -> str:
    return f"""The following static analysis findings were detected in a code
repository being reviewed for a digital forensics investigation:

{findings_summary}

Write a short, high-level analyst summary covering:

## Overall Assessment
## Most Concerning Findings
## Legitimate Use vs Malicious Use
## Recommended Next Steps
"""


def build_report_observations_prompt(context_text: str) -> str:
    return f"""Based on the following repository summary and scan findings,
write concise forensic observations and recommendations.

{context_text[:10000]}

Respond in this exact structure, using Markdown headings:

## AI Observations
## Recommendations
"""
