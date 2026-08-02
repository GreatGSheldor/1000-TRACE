from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import gemini_client, prompts
from .risk_score import RiskScore
from .secret_scanner import SecretFinding
from .threat_scanner import ThreatFinding


def get_ai_observations(
    repo_summary: str | None,
    risk: RiskScore,
    secret_findings: list[SecretFinding],
    threat_findings: list[ThreatFinding],
) -> str:
    """Optional Gemini pass. Raises gemini_client.GeminiError on failure."""
    context = (
        f"Repository summary:\n{repo_summary or '(not generated)'}\n\n"
        f"Risk score: {risk.score}/100 ({risk.band})\n"
        f"Secret findings: {len(secret_findings)}\n"
        f"Threat findings: {len(threat_findings)}\n"
        f"Top risk factors:\n- " + "\n- ".join(risk.top_factors or ["None"])
    )
    prompt = prompts.build_report_observations_prompt(context)
    return gemini_client.generate(
        prompt, system_instruction=prompts.REPORT_SYSTEM_INSTRUCTION
    )


def _static_recommendations(
    risk: RiskScore,
    secret_findings: list[SecretFinding],
    threat_findings: list[ThreatFinding],
) -> str:
    """Fallback recommendations used when Gemini is unavailable."""
    lines = []
    if secret_findings:
        lines.append(
            "- Rotate and revoke any real credentials matched by the secret "
            "scan, then remove them from source control history."
        )
        lines.append(
            "- Move secrets to environment variables or a secrets manager "
            "instead of hardcoding them."
        )
    if threat_findings:
        lines.append(
            "- Review every Critical/High threat finding to confirm "
            "whether the dangerous call is necessary and properly sandboxed."
        )
    if risk.band in ("High", "Critical"):
        lines.append(
            "- Treat this repository as high-risk until the findings above "
            "are triaged; avoid running it in an unsandboxed environment."
        )
    if not lines:
        lines.append("- No significant issues were found by the static scans.")
    return "\n".join(lines)


def generate_report(
    project_name: str,
    project_path: Path,
    repo_summary: str | None,
    risk: RiskScore,
    secret_findings: list[SecretFinding],
    threat_findings: list[ThreatFinding],
    ai_observations: str | None = None,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# TRACE Forensic Report - {project_name}",
        f"*Generated {timestamp}*",
        "",
        "## Repository Summary",
        repo_summary or "_AI summary was not generated for this report._",
        "",
        "## Risk Score",
        f"**{risk.score}/100 - {risk.band}**",
        "",
        f"- Points from secrets: {risk.secret_points}",
        f"- Points from dangerous APIs: {risk.threat_points}",
        "",
        "### Top Risk Factors",
    ]

    if risk.top_factors:
        lines.extend(f"- {factor}" for factor in risk.top_factors)
    else:
        lines.append("- None identified.")

    lines += ["", "## Secret Scan Findings"]
    if secret_findings:
        lines.append("| File | Line | Type | Severity |")
        lines.append("|---|---|---|---|")
        for finding in secret_findings:
            lines.append(
                f"| {finding.file} | {finding.line} | {finding.match_type} "
                f"| {finding.severity} |"
            )
    else:
        lines.append("No secrets were detected.")

    lines += ["", "## Threat Scan Findings"]
    if threat_findings:
        lines.append("| File | Line | Pattern | Threat Level |")
        lines.append("|---|---|---|---|")
        for finding in threat_findings:
            lines.append(
                f"| {finding.file} | {finding.line} | {finding.pattern} "
                f"| {finding.threat_level} |"
            )
    else:
        lines.append("No suspicious API usage was detected.")

    lines += ["", "## AI Observations & Recommendations"]
    if ai_observations:
        lines.append(ai_observations)
    else:
        lines.append("_AI observations unavailable - showing static recommendations instead._")
        lines.append("")
        lines.append(_static_recommendations(risk, secret_findings, threat_findings))

    return "\n".join(lines)


def export_markdown(report_text: str, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.write_text(report_text, encoding="utf-8")
    return output_path
