"""
Streamlit multi-step app: guided intake -> jurisdiction routing -> draft + checklist.

Run:
    streamlit run app.py

Steps:
  1. Category & narrative
  2. Parties (complainant + opposite party)
  3. Transaction & evidence
  4. Relief sought
  5. Review jurisdiction & generate draft
  6. Download DOCX/PDF + view e-filing checklist
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from core import config
from core.checklist import build_checklist
from core.drafter import draft_complaint
from core.intake import (
    ComplaintIntake,
    IssueDetails,
    PartyDetails,
    ReliefSought,
    TransactionDetails,
)
from core.jurisdiction import route as route_jurisdiction
from core.knowledge import category, category_labels, cpa_sections


st.set_page_config(
    page_title="Consumer Commission Complaint Agent",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------- Session state ----------

DEFAULT_STATE = {
    "step": 1,
    "category_key": None,
    "issue_short": "",
    "issue_long": "",
    "pre_notice": False,
    "notice_response": "",
    "evidence": [],
    "complainant": {},
    "opposite_party": {},
    "transaction_date": None,
    "cause_date": None,
    "txn_amount": 0.0,
    "invoice": "",
    "payment_mode": "",
    "cause_city": "",
    "claim_amount": 0.0,
    "refund": True,
    "replacement": False,
    "mental_agony": 0,
    "litigation_cost": True,
    "custom_reliefs_text": "",
    "draft_bundle": None,
    "verdict": None,
    "checklist": None,
}
for k, v in DEFAULT_STATE.items():
    st.session_state.setdefault(k, v)


# ---------- Sidebar ----------

with st.sidebar:
    st.title("📜 Consumer Complaint Agent")
    st.caption("CPA 2019 — Guided drafting + jurisdiction routing")

    steps = [
        "1. Issue",
        "2. Parties",
        "3. Transaction",
        "4. Relief",
        "5. Generate",
        "6. Download",
    ]
    for i, s in enumerate(steps, start=1):
        marker = "✅" if st.session_state["step"] > i else ("➡️" if st.session_state["step"] == i else "·")
        st.write(f"{marker} {s}")

    st.divider()
    if st.button("Restart"):
        for k, v in DEFAULT_STATE.items():
            st.session_state[k] = v
        st.rerun()

    st.divider()
    st.caption(
        f"**Models**\n\n- Polish: `{config.GEMINI_DRAFT_MODEL}`\n- Fast: `{config.GROQ_FAST_MODEL}`"
    )


# ---------- Step renderers ----------

def step_issue() -> None:
    st.header("Step 1 — What happened?")
    st.write("Pick the category that fits best, then describe what happened in your own words.")
    labels = category_labels()
    key_to_label = dict(labels)
    label_to_key = {v: k for k, v in labels}
    current_label = key_to_label.get(st.session_state["category_key"])
    label = st.selectbox(
        "Complaint category",
        options=[v for _, v in labels],
        index=([v for _, v in labels].index(current_label) if current_label else 0),
    )
    st.session_state["category_key"] = label_to_key[label]

    st.session_state["issue_short"] = st.text_input(
        "One-line summary",
        value=st.session_state["issue_short"],
        placeholder="e.g. 'Refrigerator delivered defective and seller refuses replacement'",
    )
    st.session_state["issue_long"] = st.text_area(
        "Tell us what happened in your own words (timeline, key facts, what the seller / service provider said)",
        value=st.session_state["issue_long"],
        height=200,
    )

    cat = category(st.session_state["category_key"])
    st.markdown("**Suggested evidence for this category:**")
    st.session_state["evidence"] = st.multiselect(
        "Evidence you have available",
        options=cat["evidence_checklist"],
        default=st.session_state["evidence"] or [],
    )
    extra_evidence = st.text_input(
        "Other evidence (comma-separated)",
        value="",
        placeholder="e.g. 'screenshots of WhatsApp chat'",
    )
    if extra_evidence:
        for piece in [p.strip() for p in extra_evidence.split(",") if p.strip()]:
            if piece not in st.session_state["evidence"]:
                st.session_state["evidence"].append(piece)

    st.session_state["pre_notice"] = st.checkbox(
        "I sent a pre-litigation notice to the opposite party",
        value=st.session_state["pre_notice"],
    )
    if st.session_state["pre_notice"]:
        st.session_state["notice_response"] = st.text_area(
            "Summarise the response (or 'No response')",
            value=st.session_state["notice_response"],
            height=80,
        )

    col1, col2 = st.columns(2)
    with col2:
        if st.button("Continue → Parties", type="primary", disabled=not (
            st.session_state["issue_short"].strip() and len(st.session_state["issue_long"]) > 30
        )):
            st.session_state["step"] = 2
            st.rerun()


def _party_form(prefix: str, label: str) -> None:
    p = st.session_state[prefix]
    cols = st.columns(2)
    p["name"] = cols[0].text_input(f"{label} — Name", value=p.get("name", ""))
    p["phone"] = cols[1].text_input(f"{label} — Phone", value=p.get("phone", ""))
    p["address_line"] = st.text_input(f"{label} — Address", value=p.get("address_line", ""))
    cols = st.columns(3)
    p["city"] = cols[0].text_input(f"{label} — City", value=p.get("city", ""))
    p["state"] = cols[1].text_input(f"{label} — State", value=p.get("state", ""))
    p["pincode"] = cols[2].text_input(f"{label} — Pincode", value=p.get("pincode", ""))
    p["email"] = st.text_input(f"{label} — Email (optional)", value=p.get("email", ""))


def step_parties() -> None:
    st.header("Step 2 — Who are the parties?")
    st.subheader("Complainant (you)")
    _party_form("complainant", "Complainant")
    st.subheader("Opposite Party (seller / service provider)")
    _party_form("opposite_party", "Opposite Party")

    col1, col2 = st.columns(2)
    if col1.button("← Back"):
        st.session_state["step"] = 1
        st.rerun()
    if col2.button("Continue → Transaction", type="primary"):
        # minimal validation
        c = st.session_state["complainant"]
        o = st.session_state["opposite_party"]
        if not all([c.get("name"), c.get("address_line"), c.get("city"), c.get("state")]):
            st.error("Complainant name, address, city, and state are required.")
            return
        if not all([o.get("name"), o.get("address_line"), o.get("city"), o.get("state")]):
            st.error("Opposite Party name, address, city, and state are required.")
            return
        st.session_state["step"] = 3
        st.rerun()


def step_transaction() -> None:
    st.header("Step 3 — Transaction details")
    cols = st.columns(2)
    st.session_state["transaction_date"] = cols[0].date_input(
        "Date of the transaction",
        value=st.session_state["transaction_date"] or date.today(),
    )
    st.session_state["cause_date"] = cols[1].date_input(
        "Date the cause of action arose (when you knew the goods/service was deficient)",
        value=st.session_state["cause_date"] or date.today(),
    )
    st.session_state["txn_amount"] = float(st.number_input(
        "Amount you paid (INR)",
        value=float(st.session_state["txn_amount"] or 0),
        min_value=0.0,
        step=100.0,
    ))
    cols = st.columns(2)
    st.session_state["invoice"] = cols[0].text_input(
        "Invoice / order / reference number",
        value=st.session_state["invoice"],
    )
    st.session_state["payment_mode"] = cols[1].text_input(
        "Payment mode (UPI / card / cash / cheque ...)",
        value=st.session_state["payment_mode"],
    )
    st.session_state["cause_city"] = st.text_input(
        "City where the cause of action arose (if different from yours)",
        value=st.session_state["cause_city"],
    )

    col1, col2 = st.columns(2)
    if col1.button("← Back"):
        st.session_state["step"] = 2
        st.rerun()
    if col2.button("Continue → Relief", type="primary", disabled=st.session_state["txn_amount"] <= 0):
        st.session_state["step"] = 4
        st.rerun()


def step_relief() -> None:
    st.header("Step 4 — What relief do you want?")
    st.session_state["claim_amount"] = float(st.number_input(
        "Total claim amount (INR) — used for jurisdiction routing",
        value=float(st.session_state["claim_amount"] or st.session_state["txn_amount"] or 0),
        min_value=0.0,
        step=100.0,
        help="Should include refund + compensation + any other monetary claim.",
    ))
    cols = st.columns(2)
    st.session_state["refund"] = cols[0].checkbox(
        "Refund of price paid", value=st.session_state["refund"]
    )
    st.session_state["replacement"] = cols[1].checkbox(
        "Replacement of product / re-rendering of service", value=st.session_state["replacement"]
    )
    st.session_state["mental_agony"] = int(st.number_input(
        "Compensation for mental agony / harassment (INR)",
        value=int(st.session_state["mental_agony"] or 0),
        min_value=0,
        step=500,
    ))
    st.session_state["litigation_cost"] = st.checkbox(
        "Costs of litigation", value=st.session_state["litigation_cost"]
    )
    st.session_state["custom_reliefs_text"] = st.text_area(
        "Other reliefs (one per line)",
        value=st.session_state["custom_reliefs_text"],
        height=100,
    )

    col1, col2 = st.columns(2)
    if col1.button("← Back"):
        st.session_state["step"] = 3
        st.rerun()
    if col2.button(
        "Continue → Generate complaint",
        type="primary",
        disabled=st.session_state["claim_amount"] <= 0,
    ):
        st.session_state["step"] = 5
        st.rerun()


def _assemble_intake() -> ComplaintIntake:
    c = st.session_state["complainant"]
    o = st.session_state["opposite_party"]
    return ComplaintIntake(
        complainant=PartyDetails(**c),
        opposite_party=PartyDetails(**o),
        transaction=TransactionDetails(
            transaction_date=st.session_state["transaction_date"],
            cause_of_action_date=st.session_state["cause_date"],
            transaction_amount_inr=st.session_state["txn_amount"],
            invoice_or_reference=st.session_state["invoice"],
            payment_mode=st.session_state["payment_mode"],
        ),
        issue=IssueDetails(
            category_key=st.session_state["category_key"],
            short_summary=st.session_state["issue_short"],
            detailed_narrative=st.session_state["issue_long"],
            pre_litigation_notice_sent=st.session_state["pre_notice"],
            notice_response_summary=st.session_state["notice_response"],
            evidence_available=list(st.session_state["evidence"]),
        ),
        relief=ReliefSought(
            claim_amount_inr=st.session_state["claim_amount"],
            refund_requested=st.session_state["refund"],
            replacement_requested=st.session_state["replacement"],
            compensation_for_mental_agony_inr=st.session_state["mental_agony"],
            litigation_cost_requested=st.session_state["litigation_cost"],
            custom_reliefs=[
                line.strip()
                for line in st.session_state["custom_reliefs_text"].splitlines()
                if line.strip()
            ],
        ),
        cause_of_action_city=st.session_state["cause_city"],
    )


def step_generate() -> None:
    st.header("Step 5 — Review and generate")
    try:
        intake = _assemble_intake()
    except Exception as e:
        st.error(f"Intake is incomplete: {e}")
        if st.button("← Back to fix"):
            st.session_state["step"] = 1
            st.rerun()
        return

    verdict = route_jurisdiction(
        claim_amount_inr=intake.relief.claim_amount_inr,
        cause_of_action_date=intake.transaction.cause_of_action_date,
        complainant_city=intake.complainant.city,
        opposite_party_city=intake.opposite_party.city,
        cause_city=intake.cause_of_action_city,
    )
    st.session_state["verdict"] = verdict

    with st.container(border=True):
        st.subheader("Jurisdiction verdict")
        cols = st.columns(2)
        cols[0].metric("Forum", f"{verdict.forum} Commission")
        cols[1].metric(
            "Limitation",
            verdict.limitation_status,
            delta=f"{verdict.days_remaining}d remaining" if verdict.days_remaining is not None else None,
        )
        st.write(f"**Basis:** {verdict.pecuniary_basis}")
        st.write("**Territorial filing options:**")
        for opt in verdict.territorial_options:
            st.write(f"- {opt}")
        if verdict.indicative_filing_fee_inr is not None:
            st.write(f"**Indicative filing fee:** Rs. {verdict.indicative_filing_fee_inr}")
        st.caption(verdict.fee_note)

    with st.container(border=True):
        st.subheader("Intake summary")
        st.text(intake.display_summary())

    col1, col2 = st.columns(2)
    if col1.button("← Back to edit"):
        st.session_state["step"] = 4
        st.rerun()
    if col2.button("📝 Generate draft complaint", type="primary"):
        with st.spinner("Polishing narrative with Gemini and assembling DOCX + PDF..."):
            bundle = draft_complaint(intake, verdict)
            st.session_state["draft_bundle"] = bundle
            st.session_state["checklist"] = build_checklist(intake, verdict)
            st.session_state["step"] = 6
            st.rerun()


def step_download() -> None:
    st.header("Step 6 — Your draft complaint")
    bundle = st.session_state["draft_bundle"]
    verdict = st.session_state["verdict"]
    checklist = st.session_state["checklist"]
    if not bundle:
        st.error("No draft generated yet. Go back to Step 5.")
        return

    cols = st.columns(2)
    with open(bundle.docx_path, "rb") as f:
        cols[0].download_button(
            "⬇️ Download DOCX",
            data=f.read(),
            file_name=Path(bundle.docx_path).name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with open(bundle.pdf_path, "rb") as f:
        cols[1].download_button(
            "⬇️ Download PDF",
            data=f.read(),
            file_name=Path(bundle.pdf_path).name,
            mime="application/pdf",
            use_container_width=True,
        )

    with st.expander("📄 Preview generated text", expanded=False):
        st.code(bundle.text, language="markdown")

    st.subheader("E-filing checklist")
    st.write("**Documents to attach:**")
    for d in checklist["documents_to_attach"]:
        st.write(f"- {d}")
    st.write("**Filing steps:**")
    for s in checklist["filing_steps"]:
        st.write(s)
    st.info(
        f"E-filing portal: [{checklist['portal']['portal_name']}]({checklist['portal']['portal_url']})"
    )

    st.divider()
    st.warning(
        "⚠ This draft is generated guidance, not legal advice. Before filing, have it "
        "reviewed by a qualified advocate. Verify the cited sections against the latest "
        "official text of the Consumer Protection Act, 2019 and the 2021 Jurisdiction Rules."
    )

    if st.button("← Edit and regenerate"):
        st.session_state["step"] = 5
        st.session_state["draft_bundle"] = None
        st.rerun()


# ---------- Router ----------

st.title("Consumer Commission Complaint Agent")
st.caption(
    "Guided intake → jurisdiction routing → file-ready complaint draft (DOCX + PDF) + "
    "e-Daakhil filing checklist. Built on the Consumer Protection Act, 2019."
)

step_fn = {
    1: step_issue,
    2: step_parties,
    3: step_transaction,
    4: step_relief,
    5: step_generate,
    6: step_download,
}[st.session_state["step"]]
step_fn()
