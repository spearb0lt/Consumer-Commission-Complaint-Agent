"""
Structured intake for a consumer complaint. Pydantic models with light validation.
The Streamlit app drives a multi-step form that populates ComplaintIntake.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PartyDetails(BaseModel):
    name: str = Field(..., min_length=1)
    address_line: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    pincode: str = Field("", description="6-digit Indian pincode")
    phone: str = Field("", description="10-digit Indian phone")
    email: str = ""

    @field_validator("pincode")
    @classmethod
    def _pin(cls, v: str) -> str:
        v = (v or "").strip()
        if v and (not v.isdigit() or len(v) != 6):
            raise ValueError("Pincode must be a 6-digit number.")
        return v


class TransactionDetails(BaseModel):
    transaction_date: date | None = None
    cause_of_action_date: date | None = None
    transaction_amount_inr: float = Field(..., gt=0, description="Amount paid / contract value")
    invoice_or_reference: str = ""
    payment_mode: str = ""


class IssueDetails(BaseModel):
    category_key: str
    short_summary: str = Field(..., min_length=10)
    detailed_narrative: str = Field(..., min_length=30)
    pre_litigation_notice_sent: bool = False
    notice_response_summary: str = ""
    evidence_available: list[str] = Field(default_factory=list)


class ReliefSought(BaseModel):
    claim_amount_inr: float = Field(..., gt=0)
    refund_requested: bool = False
    replacement_requested: bool = False
    compensation_for_mental_agony_inr: float = 0.0
    litigation_cost_requested: bool = True
    custom_reliefs: list[str] = Field(default_factory=list)


class ComplaintIntake(BaseModel):
    complainant: PartyDetails
    opposite_party: PartyDetails
    transaction: TransactionDetails
    issue: IssueDetails
    relief: ReliefSought
    cause_of_action_city: str = ""
    locale_language: Literal["en"] = "en"

    def display_summary(self) -> str:
        return (
            f"Complainant: {self.complainant.name}, {self.complainant.city}\n"
            f"Opposite party: {self.opposite_party.name}, {self.opposite_party.city}\n"
            f"Issue: {self.issue.short_summary}\n"
            f"Claim: Rs. {self.relief.claim_amount_inr:,.0f}\n"
        )
