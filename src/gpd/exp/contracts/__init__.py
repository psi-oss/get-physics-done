"""GPD-Exp contract models for inter-stage data flow.

All public types are re-exported here for convenient imports:
    from gpd.exp.contracts import ExperimentProtocol, ExperimentBudget, DataPoint
"""

from __future__ import annotations

from gpd.exp.contracts.bounty import BountyLifecycleRecord, BountyRecord, BountySpec, BountyStatus
from gpd.exp.contracts.budget import BudgetExceeded, Currency, ExperimentBudget, LedgerAction, LedgerEntry
from gpd.exp.contracts.cost_estimate import CostCategory, CostEstimate, CostLineItem
from gpd.exp.contracts.data import (
    BaseDataPoint,
    CategoricalDataPoint,
    DataPoint,
    NumericDataPoint,
    ObservationDataPoint,
    QualityStatus,
    TimingDataPoint,
)
from gpd.exp.contracts.experiment import (
    BetweenSubjectsDesign,
    ExperimentProtocol,
    ExperimentSpec,
    ExperimentVariable,
    FactorialDesign,
    Hypothesis,
    StudyDesign,
    VariableRole,
    VariableType,
    WithinSubjectsDesign,
)
from gpd.exp.contracts.feasibility import EthicsScreeningResult, FeasibilityResult, RejectionCategory

__all__ = [
    # experiment
    "BetweenSubjectsDesign",
    "ExperimentProtocol",
    "ExperimentSpec",
    "ExperimentVariable",
    "FactorialDesign",
    "Hypothesis",
    "StudyDesign",
    "VariableRole",
    "VariableType",
    "WithinSubjectsDesign",
    # data
    "BaseDataPoint",
    "CategoricalDataPoint",
    "DataPoint",
    "NumericDataPoint",
    "ObservationDataPoint",
    "QualityStatus",
    "TimingDataPoint",
    # budget
    "BudgetExceeded",
    "Currency",
    "LedgerAction",
    "LedgerEntry",
    "ExperimentBudget",
    # bounty
    "BountyLifecycleRecord",
    "BountyRecord",
    "BountySpec",
    "BountyStatus",
    # feasibility
    "EthicsScreeningResult",
    "FeasibilityResult",
    "RejectionCategory",
    # cost_estimate
    "CostCategory",
    "CostEstimate",
    "CostLineItem",
]
