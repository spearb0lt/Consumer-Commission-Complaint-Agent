"""
Generate the e-filing checklist for a complaint, tailored to the forum chosen and
the complaint category. Pure-Python; no LLM call required.
"""
from __future__ import annotations

from .intake import ComplaintIntake
from .jurisdiction import JurisdictionVerdict
from .knowledge import category, jurisdictions


def build_checklist(intake: ComplaintIntake, verdict: JurisdictionVerdict) -> dict:
    cat = category(intake.issue.category_key)
    j = jurisdictions()

    docs: list[str] = [
        "Final printed copy of the complaint (with verification page signed)",
        "Index and list of dates",
        "Memo of Parties (names, addresses, phone, email)",
        "Affidavit in support of the complaint, duly notarised",
        "Vakalatnama / Memo of Appearance (if represented by counsel)",
    ]
    docs.extend([f"Evidence: {e}" for e in cat["evidence_checklist"]])
    if intake.issue.pre_litigation_notice_sent:
        docs.append("Copy of pre-litigation legal notice and proof of delivery")
        if intake.issue.notice_response_summary:
            docs.append("Reply received from opposite party (if any)")
    docs.append(f"Demand Draft / online payment proof: Rs. {verdict.indicative_filing_fee_inr or '___'} towards filing fee")

    steps = [
        f"1. Verify pecuniary jurisdiction: {verdict.forum} Commission ({verdict.pecuniary_basis}).",
        f"2. Verify limitation: status = '{verdict.limitation_status}'."
        + (f" ({verdict.days_remaining} days remaining before 2-year bar)" if verdict.days_remaining is not None else ""),
        "3. Choose territorial Commission from the options listed (forum where complainant resides, OP carries on business, or cause of action arose).",
        f"4. Open the e-Daakhil portal: {j['e_filing']['portal_url']} and register / log in.",
        "5. Fill the online complaint form with the same particulars as in the printed complaint.",
        "6. Upload PDF copies of: complaint, affidavit, evidence annexures.",
        "7. Pay the filing fee online (UPI / netbanking).",
        "8. Note the Case Diary Number and serve notice to opposite party as directed by the Commission.",
    ]
    return {
        "forum": verdict.forum,
        "territorial_options": verdict.territorial_options,
        "limitation_status": verdict.limitation_status,
        "days_to_limitation_bar": verdict.days_remaining,
        "indicative_fee_inr": verdict.indicative_filing_fee_inr,
        "fee_note": verdict.fee_note,
        "documents_to_attach": docs,
        "filing_steps": steps,
        "portal": j["e_filing"],
    }
