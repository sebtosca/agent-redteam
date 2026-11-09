"""toolbreach core: framework-free domain models.

Import domain types from here (``from toolbreach.core import ToolCall``) rather
than reaching into ``toolbreach.core.models``.
"""

from toolbreach.core.authorization import (
    Authorization,
    AuthorizationError,
    AuthorizationRecord,
    require_authorization,
)
from toolbreach.core.models import (
    AdaptiveCase,
    Breach,
    BreachKind,
    CaseBase,
    CaseKind,
    Decision,
    DecisionKind,
    Finding,
    Frozen,
    FrozenCase,
    Objective,
    RegressionCase,
    Specialist,
    ToolCall,
    Trial,
)

__all__ = [
    "AdaptiveCase",
    "Authorization",
    "AuthorizationError",
    "AuthorizationRecord",
    "Breach",
    "BreachKind",
    "CaseBase",
    "CaseKind",
    "Decision",
    "DecisionKind",
    "Finding",
    "Frozen",
    "FrozenCase",
    "Objective",
    "RegressionCase",
    "Specialist",
    "ToolCall",
    "Trial",
    "require_authorization",
]
