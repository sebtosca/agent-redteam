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
from toolbreach.core.event_log import Event, EventLog
from toolbreach.core.interceptor import (
    Interceptor,
    acall_tool,
    active_interceptor,
    bind,
    call_tool,
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
    "Event",
    "EventLog",
    "Finding",
    "Frozen",
    "FrozenCase",
    "Interceptor",
    "Objective",
    "RegressionCase",
    "Specialist",
    "ToolCall",
    "Trial",
    "acall_tool",
    "active_interceptor",
    "bind",
    "call_tool",
    "require_authorization",
]
