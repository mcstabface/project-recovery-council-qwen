"""Narrow expert-system interfaces for future orchestration."""

from __future__ import annotations

from abc import ABC, abstractmethod

from project_recovery_council.contracts import (
    Contradiction,
    ExpertFinding,
    ExpertRequest,
    FinalRecommendation,
    RecoveryCase,
)
from project_recovery_council.fixtures import CaseBundle


class Director(ABC):
    """Routes governed case work to specialist experts."""

    @abstractmethod
    def evaluate_case(self, bundle: CaseBundle) -> list[ExpertFinding]:
        raise NotImplementedError


class ScheduleExpert(ABC):
    @abstractmethod
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        raise NotImplementedError


class CommercialExpert(ABC):
    @abstractmethod
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        raise NotImplementedError


class RiskExpert(ABC):
    @abstractmethod
    def evaluate(self, request: ExpertRequest, bundle: CaseBundle) -> ExpertFinding:
        raise NotImplementedError


class EvidenceAuditor(ABC):
    @abstractmethod
    def audit(self, case: RecoveryCase, bundle: CaseBundle) -> list[Contradiction]:
        raise NotImplementedError


class RecoveryPlanner(ABC):
    @abstractmethod
    def plan(self, case: RecoveryCase, bundle: CaseBundle) -> FinalRecommendation:
        raise NotImplementedError

