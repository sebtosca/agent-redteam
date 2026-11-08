"""Core domain models for toolbreach.

Framework-free on purpose: no langchain / langgraph imports may appear in this
module. The import-boundary test enforces that. Every model is frozen and
rejects unknown fields, so each record is immutable and self-validating.
"""

import json
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Frozen(BaseModel):
    """Base for all core domain models.

    frozen=True: instances are read-only after creation, so a recorded fact
        (a ToolCall, a Breach) can never be mutated, and the model is hashable.
    extra="forbid": an unknown field raises at construction instead of being
        silently dropped, so a mistyped field name fails loudly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolCall(Frozen):
    """The Target tries to call a tool. ToolCall records the tool name and its
    arguments, as the Interceptor observes them.
    """

    tool_name: str = Field(min_length=1)  # may become a Literal once a tool registry exists
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str = Field(min_length=1)

    @field_validator("arguments", mode="before")
    @classmethod
    def parse_json_str(cls, value: Any) -> Any:
        """Accept arguments as a dict or as a JSON string; store a dict."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"arguments is not valid JSON: {exc}") from exc
        return value


class DecisionKind(StrEnum):
    """The three ways the Interceptor can resolve a ToolCall.

    LIVE: the real tool runs for real (read-only tools marked safe).
    INTERCEPTED: the call is recorded but never runs; a fake result is returned.
    INJECTED: an attacker-controlled result is returned instead of the real one.
    """

    LIVE = "live"
    INTERCEPTED = "intercepted"
    INJECTED = "injected"


class Decision(Frozen):
    """What the Interceptor does about a ToolCall, and what it returned.

    The Interceptor sits between the Target and its real tool functions. It sees
    every tool call and chooses one DecisionKind. Decision is the record of that
    choice.
    """

    kind: DecisionKind
    result: Any | None = Field(
        default=None,
        description="Value returned to the Target. None for LIVE (the real call provides it).",
    )
    source: str | None = Field(
        default=None,
        description='Where the result came from, e.g. "fixture", "default", "injected:P1".',
    )

    @model_validator(mode="after")
    def _result_matches_kind(self) -> "Decision":
        if self.kind is DecisionKind.LIVE and self.result is not None:
            raise ValueError("a LIVE decision must not carry a result; the real call provides it")
        if self.kind in (DecisionKind.INTERCEPTED, DecisionKind.INJECTED) and self.result is None:
            raise ValueError(f"a {self.kind.value} decision must carry a result")
        return self


class Specialist(StrEnum):
    """The four Attacker specialties (GLOSSARY). The Planner routes each
    Objective to one of them.

    INJECTOR: plants attacks in Intercepted Tool results.
    SOCIAL_ENGINEER: pursues the Objective through multi-turn persuasion.
    EXTRACTOR: tries to make the Target reveal its system prompt, secrets or canaries.
    TOOL_ABUSER: tries to force forbidden tool arguments or escalating tool chains.
    """

    INJECTOR = "injector"
    SOCIAL_ENGINEER = "social_engineer"
    EXTRACTOR = "extractor"
    TOOL_ABUSER = "tool_abuser"


class Objective(Frozen):
    """One concrete thing an attack tries to make the Target do, such as calling
    a given tool with given arguments. The Planner derives Objectives from the
    Target Profile and routes each one to a Specialist.
    """

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    pattern_id: str | None = Field(
        default=None,
        description="Attack Pattern this came from. None until the pattern library (P4) exists.",
    )
    specialist: Specialist | None = Field(
        default=None,
        description="Which Specialist pursues this Objective. The Planner assigns it.",
    )
    tags: tuple[str, ...] = Field(
        default=(),
        description="OWASP LLM / OWASP Agentic / ATLAS ids for reporting.",
    )


class BreachKind(StrEnum):
    """The two kinds of Breach (DISCOVERY C2). OBJECTIVE outranks POLICY.

    OBJECTIVE: forbidden content appears in the Target's outbound tool-call
        arguments, i.e. the Target took the forbidden action. Most severe.
    POLICY: forbidden content appears only in the Target's assistant text,
        i.e. the Target said something forbidden but did not act.
    """

    OBJECTIVE = "objective"
    POLICY = "policy"

    @property
    def severity(self) -> int:
        """Higher is worse. Used to rank Breaches within a Finding."""
        return {BreachKind.POLICY: 1, BreachKind.OBJECTIVE: 2}[self]


class Breach(Frozen):
    """One observed instance of the Target failing under attack.

    A Breach records the outcome only (what went wrong), never the attack recipe
    that caused it; the recipe lives on the RegressionCase.
    """

    kind: BreachKind
    objective_id: str = Field(
        min_length=1,
        description="The Objective.id this Breach was found against.",
    )
    detected_by: str = Field(
        min_length=1,
        description='The Check id that fired, or "judge" when the LLM Judge decided it.',
    )
    evidence: str = Field(
        min_length=1,
        description="The offending text, or a rendering of the forbidden tool call and its args.",
    )


class Finding(Frozen):
    """A deduplicated group of Breaches that share one root cause, and the unit
    that gets reported. Its severity is that of its worst Breach.
    """

    id: str = Field(min_length=1)
    objective_id: str = Field(min_length=1)
    pattern_id: str | None = None
    breaches: tuple[Breach, ...] = Field(min_length=1)
    summary: str | None = Field(
        default=None,
        description="Human-readable summary written by an LLM (P3.T2); None in Replay.",
    )

    @property
    def severity(self) -> BreachKind:
        """The worst Breach kind in the group (OBJECTIVE outranks POLICY)."""
        return max((b.kind for b in self.breaches), key=lambda k: k.severity)


class CaseKind(StrEnum):
    """Whether a RegressionCase replays a fixed script or retries a strategy.

    FROZEN: replays the exact recorded Attacker messages and injected payloads.
    ADAPTIVE: stores the Objective plus the strategy that worked, and lets an
        Attacker try again on a small Budget.
    """

    FROZEN = "frozen"
    ADAPTIVE = "adaptive"


class CaseBase(Frozen):
    """Fields shared by every RegressionCase kind."""

    id: str = Field(min_length=1)
    objective: Objective
    pattern_id: str | None = None
    tags: tuple[str, ...] = ()
    source_finding_id: str = Field(min_length=1)
    schema_version: int = 1
    checks: tuple[str, ...] = Field(
        default=(),
        description="Check ids this case re-runs during Replay.",
    )


class FrozenCase(CaseBase):
    """A RegressionCase that replays a fixed script verbatim (the default)."""

    kind: Literal[CaseKind.FROZEN] = CaseKind.FROZEN
    user_task: str = Field(min_length=1)
    attacker_messages: tuple[str, ...] = Field(min_length=1)
    injected_payloads: tuple[str, ...] = ()


class AdaptiveCase(CaseBase):
    """A RegressionCase that retries a winning strategy on a small Budget."""

    kind: Literal[CaseKind.ADAPTIVE] = CaseKind.ADAPTIVE
    strategy: str = Field(min_length=1)
    budget: dict[str, Any] = Field(
        default_factory=dict,
        description="Placeholder; a typed Budget replaces this in P1.T6.",
    )


# A RegressionCase is one of the two kinds above, selected by its `kind` tag.
# Validate it in tests via TypeAdapter(RegressionCase).
RegressionCase = Annotated[FrozenCase | AdaptiveCase, Field(discriminator="kind")]


class Trial(Frozen):
    """One execution of a RegressionCase during Replay. A case fails if any of
    its Trials produces a Breach.
    """

    case_id: str = Field(min_length=1)
    index: int = Field(ge=0, description="0-based trial number within the Replay.")
    breaches: tuple[Breach, ...] = ()

    @property
    def passed(self) -> bool:
        """True when this Trial saw no Breach."""
        return len(self.breaches) == 0
