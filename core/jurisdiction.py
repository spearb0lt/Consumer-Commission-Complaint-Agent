"""
Jurisdiction routing per CPA 2019 + 2021 Pecuniary Jurisdiction Rules.

Inputs: claim_amount (INR), complainant_state, opposite_party_state.
Outputs: which Commission (District/State/National), territorial options,
limitation status, indicative fee.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .knowledge import jurisdictions


@dataclass
class JurisdictionVerdict:
    forum: str                          # "District", "State", "National"
    pecuniary_basis: str                # human-readable explanation
    territorial_options: list[str]      # eligible filing locations
    limitation_status: str              # "within", "exceeded", "borderline"
    days_remaining: int | None
    indicative_filing_fee_inr: int | None
    fee_note: str
    raw: dict[str, Any]


def _select_forum(amount_inr: float) -> tuple[str, str]:
    rules = jurisdictions()["pecuniary_thresholds"]
    district_max = rules["district_commission_max_inr"]
    state_max = rules["state_commission_max_inr"]
    if amount_inr <= district_max:
        return "District", f"Claim amount Rs. {amount_inr:,.0f} is within District Commission limit (Rs. {district_max:,})."
    if amount_inr <= state_max:
        return "State", f"Claim amount Rs. {amount_inr:,.0f} is within State Commission band (Rs. {district_max:,} < amount <= Rs. {state_max:,})."
    return "National", f"Claim amount Rs. {amount_inr:,.0f} exceeds Rs. {state_max:,}; goes to the National Consumer Disputes Redressal Commission."


def _indicative_fee(forum: str, amount_inr: float) -> tuple[int | None, str]:
    schedule = jurisdictions().get("filing_fee_indicative", {})
    bracket = schedule.get(forum.lower(), [])
    for row in bracket:
        ceiling = row.get("upto_inr")
        if ceiling is None or amount_inr <= ceiling:
            return row.get("fee_inr"), schedule.get("comment", "")
    return None, schedule.get("comment", "")


def _limitation(cause_of_action_date: date | None, today: date | None = None) -> tuple[str, int | None]:
    if cause_of_action_date is None:
        return "unknown", None
    today = today or date.today()
    deadline = cause_of_action_date + timedelta(days=365 * 2)
    delta = (deadline - today).days
    if delta < 0:
        return "exceeded", delta
    if delta <= 30:
        return "borderline", delta
    return "within", delta


def _territorial_options(complainant_city: str, opposite_party_city: str, cause_city: str) -> list[str]:
    options = []
    if complainant_city:
        options.append(f"Where complainant resides / works for gain: {complainant_city}")
    if opposite_party_city:
        options.append(f"Where opposite party resides / carries on business: {opposite_party_city}")
    if cause_city and cause_city not in (complainant_city, opposite_party_city):
        options.append(f"Where the cause of action arose: {cause_city}")
    return options or ["Insufficient location data — confirm before filing."]


def route(
    *,
    claim_amount_inr: float,
    cause_of_action_date: date | None = None,
    complainant_city: str = "",
    opposite_party_city: str = "",
    cause_city: str = "",
) -> JurisdictionVerdict:
    forum, basis = _select_forum(claim_amount_inr)
    fee, fee_note = _indicative_fee(forum, claim_amount_inr)
    lim_status, days = _limitation(cause_of_action_date)
    terr = _territorial_options(complainant_city, opposite_party_city, cause_city)
    return JurisdictionVerdict(
        forum=forum,
        pecuniary_basis=basis,
        territorial_options=terr,
        limitation_status=lim_status,
        days_remaining=days,
        indicative_filing_fee_inr=fee,
        fee_note=fee_note,
        raw={
            "claim_amount_inr": claim_amount_inr,
            "cause_of_action_date": cause_of_action_date.isoformat() if cause_of_action_date else None,
            "complainant_city": complainant_city,
            "opposite_party_city": opposite_party_city,
            "cause_city": cause_city,
        },
    )
