from enum import StrEnum

from pydantic import Field, model_validator

from toolbreach.core import Authorization, Frozen


class ToolMode(StrEnum):
    LIVE = "live"
    INTERCEPTED = "intercepted"

class ToolSpec(Frozen):
    name: str = Field(min_length=1)
    mode: ToolMode = Field(
        default=ToolMode.INTERCEPTED
    )

class TargetProfile(Frozen):
    purpose: str = Field(min_length=1)
    policy: str = Field(min_length=1)
    tools: tuple[ToolSpec, ...] = Field(
        default=()
    )

class BudgetConfig(Frozen):
    max_tokens: int = Field(gt=0)
    max_seconds: float = Field(gt=0)
    max_usd: float | None = Field(
        default=None,
        gt=0
    )

class RoleModels(Frozen):
    planner: str = Field(min_length=1)
    attacker: str = Field(min_length=1)
    judge: str = Field(min_length=1)

class ReplayConfig(Frozen):
    trials: int = Field(default=3, ge=1)

class Config(Frozen):
    authorization: Authorization
    target: TargetProfile
    budget: BudgetConfig
    models: RoleModels
    replay: ReplayConfig = Field(default_factory=ReplayConfig)

    @model_validator(mode="after")
    def _judge_differs_from_attacker(self) -> "Config":
        if self.models.judge == self.models.attacker:
            raise ValueError(
                "models.judge must differ from models.attacker; "
                "the Judge cannot be an Attacker model"
            )
        return self
