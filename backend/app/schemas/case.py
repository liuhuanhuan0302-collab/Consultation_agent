"""Consulting case library schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CaseStudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    industry: str
    function_area: str
    module_code: str
    maturity: str
    roi_level: str
    difficulty: str
    description: str
    expected_benefit: str
    priority_tag: str
    is_active: bool
    created_at: datetime


class CaseStudyCreate(BaseModel):
    title: str
    industry: str
    function_area: str
    module_code: str
    maturity: str = "MVP"
    roi_level: str = "medium"
    difficulty: str = "medium"
    description: str
    expected_benefit: str
    priority_tag: str = "攻坚战"
    is_active: bool = True
