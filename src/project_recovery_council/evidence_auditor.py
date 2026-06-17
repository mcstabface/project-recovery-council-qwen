"""Dedicated EvidenceAuditor response validation and conversion."""

from __future__ import annotations

from typing import Any

from pydantic import Field, ValidationError

from project_recovery_council.claim_normalization import ROLE_CLAIM_ALIASES
from project_recovery_council.contracts import ContractModel
from project_recovery_council.experiment_contracts import (
    AuditSupportStatus,
    EvidenceAuditorResponse,
)
from project_recovery_council.fixtures import CaseBundle


class CanonicalAuditFinding(ContractModel):
    invocation_id: str = Field(min_length=1)
    audited_agent: str = Field(min_length=1)
    audited_claim_key: str = Field(min_length=1)
    canonical_claim_key: str = Field(min_length=1)
    support_status: AuditSupportStatus
    citations: list[str] = Field(default_factory=list)
    rationale: str | None = None
    observed_value: Any = None
    expected_value: Any = None
    validation_reference: str | None = None
    original_invocation_id: str | None = None
    eligible_for_synthesis: bool
    exclusion_reason: str | None = None


class EvidenceAuditorValidationResult(ContractModel):
    invocation_id: str = Field(min_length=1)
    valid: bool
    errors: list[str] = Field(default_factory=list)
    canonical_findings: list[CanonicalAuditFinding] = Field(default_factory=list)


def validate_and_convert_evidence_auditor_response(
    *,
    invocation_id: str,
    response_payload: dict[str, Any] | None,
    bundle: CaseBundle,
    original_claim_sources: dict[tuple[str, str], str] | None = None,
) -> EvidenceAuditorValidationResult:
    errors: list[str] = []
    try:
        response = EvidenceAuditorResponse.model_validate(response_payload)
    except ValidationError as exc:
        return EvidenceAuditorValidationResult(
            invocation_id=invocation_id,
            valid=False,
            errors=[str(error) for error in exc.errors()],
        )
    except ValueError as exc:
        return EvidenceAuditorValidationResult(
            invocation_id=invocation_id,
            valid=False,
            errors=[str(exc)],
        )

    findings: list[CanonicalAuditFinding] = []
    sources = original_claim_sources or {}
    for audited_agent, assessments in response.assessments_by_agent.items():
        for raw_claim_key, assessment in assessments.items():
            canonical_key = ROLE_CLAIM_ALIASES.get(audited_agent, {}).get(raw_claim_key, raw_claim_key)
            missing_records = [
                record_id
                for record_id in assessment.citations
                if record_id not in bundle.evidence_by_id
            ]
            if missing_records:
                errors.append(
                    f"{audited_agent}.{raw_claim_key} cites unknown evidence records: {missing_records}"
                )
            original_invocation_id = sources.get((audited_agent, canonical_key))
            eligible = assessment.support_status == AuditSupportStatus.SUPPORTED and not missing_records
            exclusion_reason = None if eligible else f"audit support status {assessment.support_status.value}"
            if missing_records:
                exclusion_reason = f"{exclusion_reason}; unknown evidence record" if exclusion_reason else "unknown evidence record"
            findings.append(
                CanonicalAuditFinding(
                    invocation_id=invocation_id,
                    audited_agent=audited_agent,
                    audited_claim_key=raw_claim_key,
                    canonical_claim_key=canonical_key,
                    support_status=assessment.support_status,
                    citations=assessment.citations,
                    rationale=assessment.rationale,
                    observed_value=assessment.observed_value,
                    expected_value=assessment.expected_value,
                    validation_reference=assessment.validation_reference,
                    original_invocation_id=original_invocation_id,
                    eligible_for_synthesis=eligible,
                    exclusion_reason=exclusion_reason,
                )
            )
    return EvidenceAuditorValidationResult(
        invocation_id=invocation_id,
        valid=not errors,
        errors=errors,
        canonical_findings=findings,
    )


def audit_findings_to_response_payload(
    *,
    response_payload: dict[str, Any] | None,
    validation: EvidenceAuditorValidationResult,
) -> dict[str, Any] | None:
    if response_payload is None:
        return None
    normalized = dict(response_payload)
    claims: dict[str, Any] = {}
    citations: dict[str, list[str]] = {}
    for finding in validation.canonical_findings:
        claim_id = f"{finding.audited_agent}.{finding.canonical_claim_key}"
        claims[claim_id] = {
            "audited_agent": finding.audited_agent,
            "audited_claim_key": finding.audited_claim_key,
            "canonical_claim_key": finding.canonical_claim_key,
            "support_status": finding.support_status.value,
            "rationale": finding.rationale,
            "observed_value": finding.observed_value,
            "expected_value": finding.expected_value,
            "validation_reference": finding.validation_reference,
            "original_invocation_id": finding.original_invocation_id,
            "eligible_for_synthesis": finding.eligible_for_synthesis,
            "exclusion_reason": finding.exclusion_reason,
        }
        citations[claim_id] = list(finding.citations)
    normalized["claims"] = claims
    normalized["citations"] = citations
    return normalized
