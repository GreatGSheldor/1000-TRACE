

from __future__ import annotations

from dataclasses import dataclass

from .secret_scanner import SecretFinding
from .threat_scanner import ThreatFinding

# Points added per finding, by severity/threat level.
_SECRET_WEIGHTS = {"Critical": 18, "High": 10, "Medium": 5, "Low": 2}
_THREAT_WEIGHTS = {"Critical": 15, "High": 8, "Medium": 4, "Low": 1}

_BAND_THRESHOLDS = [
    (80, "Critical"),
    (55, "High"),
    (25, "Medium"),
    (0, "Low"),
]


@dataclass
class RiskScore:
    score: int
    band: str
    secret_points: int
    threat_points: int
    top_factors: list[str]


def compute_risk_score(
    secret_findings: list[SecretFinding],
    threat_findings: list[ThreatFinding],
) -> RiskScore:
    secret_points = sum(_SECRET_WEIGHTS.get(f.severity, 1) for f in secret_findings)
    threat_points = sum(_THREAT_WEIGHTS.get(f.threat_level, 1) for f in threat_findings)

    raw_score = secret_points + threat_points
    score = min(100, raw_score)

    band = "Low"
    for threshold, label in _BAND_THRESHOLDS:
        if score >= threshold:
            band = label
            break

    top_factors = _top_factors(secret_findings, threat_findings)

    return RiskScore(
        score=score,
        band=band,
        secret_points=secret_points,
        threat_points=threat_points,
        top_factors=top_factors,
    )


def _top_factors(secret_findings, threat_findings, limit: int = 5) -> list[str]:
    factors = []

    for finding in secret_findings:
        if finding.severity in ("Critical", "High"):
            factors.append(f"Secret: {finding.match_type} in {finding.file}:{finding.line}")

    for finding in threat_findings:
        if finding.threat_level in ("Critical", "High"):
            factors.append(f"Threat: {finding.pattern} in {finding.file}:{finding.line}")

    return factors[:limit]
