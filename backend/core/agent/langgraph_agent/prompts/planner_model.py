# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StepType(str, Enum):
    RESEARCH = "research"
    PROCESSING = "processing"


class Step(BaseModel):
    need_search: bool = Field(..., description="Must be explicitly set for each step")
    title: str
    description: str = Field(..., description="Specify exactly what data to collect")
    step_type: StepType = Field(..., description="Indicates the nature of the step")
    execution_res: Optional[str] = Field(default=None, description="The Step execution result")


class Plan(BaseModel):
    locale: str = Field(..., description="e.g. 'en-US' or 'zh-CN', based on the user's language")
    has_enough_context: bool
    thought: str
    title: str
    steps: list[Step] = Field(
        default_factory=list,
        description="Research & Processing steps to get more context",
    )

    def to_dict(self) -> dict[str, Any]:
        """For backward compatibility with older Pydantic versions"""
        return self.model_dump()

    def dict_dump(self) -> dict[str, Any]:
        """Convert the model to a dictionary that can be JSON serialized"""
        return {
            "locale": self.locale,
            "has_enough_context": self.has_enough_context,
            "thought": self.thought,
            "title": self.title,
            "steps": [step.model_dump() for step in self.steps],
        }

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "has_enough_context": False,
                    "thought": (
                        "To understand the current market trends in AI, we need to gather comprehensive information."
                    ),
                    "title": "AI Market Research Plan",
                    "steps": [
                        {
                            "need_search": True,
                            "title": "Current AI Market Analysis",
                            "description": (
                                "Collect data on market size, growth rates, major \
                                    players, and investment trends in AI sector."
                            ),
                            "step_type": "research",
                        }
                    ],
                }
            ]
        }


class FillRef(BaseModel):
    """A minimal mapping from a plan step to an observation index."""
    step_title: str = Field(..., description="The title of the step to be filled")
    observation_index: int = Field(..., description="Index in state.observations to use as execution_res")


class PlannerUpdate(BaseModel):
    """Planner minimal output for stable orchestration.

    - plan: A Plan without large execution content
    - fills: A list of mappings that specify which observation should be assigned to which step's execution_res
    """
    plan: Plan
    fills: list[FillRef] = Field(default_factory=list)
