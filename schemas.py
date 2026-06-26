"""Pydantic request/response models (API layer only)."""
from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    user_email: str


class ProfileIn(BaseModel):
    income: float = 0
    other_income: float = 0
    savings: float = 0
    min_balance: float = 0
    rent: float = 0
    utilities: float = 0
    insurance: float = 0
    subscriptions: float = 0
    food: float = 0
    transport: float = 0
    dining: float = 0
    shopping: float = 0
    misc: float = 0
    emis: List[Any] = Field(default_factory=list)
    horizon_months: int = 0
    safety_target: float = 0


class ScenarioIn(BaseModel):
    name: str
    scenario_type: str
    params: dict = Field(default_factory=dict)


class GoalIn(BaseModel):
    name: str
    target_amount: float
    target_months: int
    category: str = "other"


class GoalOut(BaseModel):
    id: int
    user_id: int
    name: str
    target_amount: float
    target_months: int
    category: str
    is_active: bool
    created_at: Any

    class Config:
        from_attributes = True


class SimulateRequest(BaseModel):
    scenario_ids: List[int] = Field(default_factory=list)
    simulation_mode: str = "moderate"
