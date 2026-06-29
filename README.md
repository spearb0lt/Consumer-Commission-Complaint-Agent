# Consumer Commission Complaint Agent (India)

A Streamlit-hosted guided-intake agent that turns a consumer's plain-language account of a grievance into a **file-ready Consumer Commission complaint petition** — formally drafted in Indian legal pleading style, jurisdiction-routed per the 2021 Pecuniary Rules, and packaged as a downloadable DOCX + PDF with an e-Daakhil filing checklist.

The complaint language follows Indian Consumer Commission pleading conventions directly: numbered `Para 1. That...` paragraphs, third-person formal voice, inline CPA 2019 section citations, `Rs. X/- (Rupees X Only)` monetary notation, `Annexure-A / B / C` exhibit labelling, and a Roman-numeral `GROUNDS:` section — the same style seen in real filings before District Consumer Commissions across Rajasthan, Punjab, Gujarat, and other states.

---

## Table of Contents

1. [What problem this solves](#what-problem-this-solves)
2. [How it works — end-to-end pipeline](#how-it-works)
3. [Stack](#stack)
4. [The six-step wizard](#the-six-step-wizard)
5. [Jurisdiction routing logic](#jurisdiction-routing-logic)
6. [LLM pipeline — how Gemini is constrained](#llm-pipeline)
7. [Document generation — DOCX and PDF](#document-generation)
8. [Legal language in generated complaints](#legal-language)
9. [Knowledge base in depth](#knowledge-base)
10. [Setup and configuration](#setup)
11. [Environment variables](#environment-variables)
12. [Repository layout](#repository-layout)
13. [How to extend — adding categories, sections, fee schedules](#how-to-extend)
14. [After download — the filing process](#after-download)
15. [Disclaimers and limitations](#disclaimers)

---

## What problem this solves

India's Consumer Commissions (District, State, and National) handle small-claims disputes — defective goods, deficient services, unfair trade practices, medical negligence, real estate delays, e-commerce fraud — under the Consumer Protection Act, 2019. They are accessible, relatively fast, and do not always require an advocate.

**The access barrier is not legal fees — it is knowledge.**

Most consumers:
- Do not know which forum (District / State / National) has jurisdiction for their claim amount
- Do not know the 2-year limitation window under Section 69 of CPA 2019, or that they might already be borderline
- Do not know what a complaint petition must contain (parties block, MOST RESPECTFULLY SHOWETH, statement of facts, grounds, prayer, verification affidavit)
- Do not know what language is required (formal legal pleading, not a letter of complaint)
- Do not know what evidence to attach or how to label it as Annexures
- Have never used the e-Daakhil online filing portal

This agent removes every one of those barriers through a guided six-step form that results in a draft complaint petition in the exact format expected by Indian Consumer Commissions.

---

## How it works

```
User narrative ("I bought a fridge, it was defective, seller refused to replace it")
        │
        │  Step 1–4: Streamlit multi-step form
        ▼
┌────────────────────────────────────────────────────┐
│  ComplaintIntake (Pydantic v2)                     │
│  complainant · opposite_party · transaction        │
│  issue (category + narrative) · relief             │
└──────────────────────┬─────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────┐
│  Jurisdiction router  (pure Python over JSON)      │
│  ─ Pecuniary: District / State / National          │
│  ─ Territorial: 3 filing-location options          │
│  ─ Limitation: within / borderline / exceeded      │
│  ─ Indicative filing fee lookup                    │
└──────────────────────┬─────────────────────────────┘
                       │ JurisdictionVerdict
                       ▼
┌────────────────────────────────────────────────────┐
│  Narrative polisher  (Gemini 2.5 Flash)            │
│  ─ System prompt enforces Indian pleading style    │
│  ─ Category-specific statutory vocabulary injected │
│  ─ Produces 10–16 "Para N. That..." paragraphs     │
│  ─ Inline CPA 2019 section citations               │
│  ─ Exhibit labels: Annexure-A, B, C ...            │
│  ─ ONLY rewrites supplied facts, never invents     │
└──────────────────────┬─────────────────────────────┘
                       │ polished_narrative (str)
                       ▼
┌────────────────────────────────────────────────────┐
│  Complaint assembler  (pure Python)                │
│  ─ Court header, cause title, party blocks         │
│  ─ MOST RESPECTFULLY SHOWETH:                      │
│  ─ STATEMENT OF FACTS  (Gemini narrative)          │
│  ─ GROUNDS: (I. BECAUSE ... II. BECAUSE ...)       │
│  ─ PRAYER: (formal relief items from intake)       │
│  ─ Verification affidavit                          │
└──────────────────────┬─────────────────────────────┘
                       │ full complaint text
                       ├──────────────────────▶  .docx  (python-docx, Times New Roman 12pt)
                       └──────────────────────▶  .pdf   (reportlab, A4, legal margins)
                                                    │
                                                    ▼
                                    Step 6: Download + e-Daakhil checklist
```

**Key design choice:** Gemini touches only the narrative paragraphs. Every other part of the document — court header, party block, grounds section, prayer, verification, jurisdiction verdict — is assembled by deterministic Python code from the structured intake and JSON knowledge base. This dramatically limits the surface area for hallucination.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| **Frontend / hosting** | [Streamlit](https://streamlit.io) | Multi-step wizard with sidebar progress tracker; fast to iterate; no frontend build step |
| **Drafting LLM** | Google **Gemini 2.5 Flash** via `google-genai` SDK | Long-context, strong instruction following, good at structured formal output; constrained to formal Indian legal style by a detailed system prompt |
| **Fast ops LLM** | Groq **Llama 3.3 70B Versatile** via `groq` | Available for lightweight tasks (issue classification, quick rewrites) — fast, cheap, structured JSON |
| **DOCX generation** | `python-docx` | Native `.docx` output; Times New Roman formatting; bold headings; direct paragraph control |
| **PDF generation** | `reportlab` | Pure-Python A4 PDF; no system dependencies (no LibreOffice, no wkhtmltopdf); legal margins; Times-Roman |
| **Schema validation** | `pydantic` v2 | Field-level validation on all intake models; type-safe throughout |
| **Knowledge base** | Static JSON (3 files) | CPA 2019 section summaries, jurisdiction rules, complaint-category playbook — readable, easily extendable, no DB required |
| **Document format** | DOCX + PDF | DOCX for advocate review and editing; PDF for e-Daakhil upload |

**API keys needed: two.**

```
GOOGLE_API_KEY   (or GEMINI_API_KEY)   — Gemini drafting
GROQ_API_KEY                           — Groq fast ops
```

---

## The six-step wizard

### Step 1 — Issue

The user picks a **complaint category** from the playbook (six categories, see [Knowledge base](#knowledge-base)) and provides:

| Field | Purpose |
|---|---|
| One-line summary | Short description used in the cause title |
| Detailed narrative | The user's own words — what happened, when, what the seller/provider said. Gemini converts this into legal prose but never invents facts. |
| Evidence available | Multi-select from the category's evidence checklist (pre-populated per category); free-text for additional items |
| Pre-litigation notice sent | Checkbox; if checked, prompts for the response summary. The complaint drafts an Annexure reference for the notice. |

**What the category selection drives:** Each category maps to a specific set of primary CPA 2019 sections, typical reliefs in formal legal language, and an evidence checklist. See `data/playbook.json`.

---

### Step 2 — Parties

Structured form for:
- **Complainant** (the person filing): name, address, city, state, pincode, phone, email
- **Opposite Party** (the seller / service provider / manufacturer): same fields

The party details flow into the formal party block in the complaint:

```
[Name]
S/o / D/o / W/o: _______________
[Address line]
[City], [State] – [Pincode]
Phone: [phone]
Email: [email]

                                                               ...COMPLAINANT
```

This mirrors the exact format used in real Consumer Commission filings (e.g., CASE 112/2024 before the District Consumer Disputes Redressal Commission, Dholpur, Rajasthan).

---

### Step 3 — Transaction

| Field | Used for |
|---|---|
| Date of transaction | Para in statement of facts ("on [date], the Complainant purchased...") |
| Date cause of action arose | **Limitation check** — 2-year clock runs from this date per Section 69 CPA 2019 |
| Amount paid (INR) | Formal Rs. X/- notation; refund prayer |
| Invoice / order reference | Introduced as Annexure-A in narrative |
| Payment mode | Factual record (UPI / card / cash / cheque) |
| City where cause arose | Third territorial option if different from either party's city |

---

### Step 4 — Relief

| Field | Drives |
|---|---|
| Total claim amount (INR) | **Jurisdiction routing** — this single number determines District / State / National Commission |
| Refund requested | Prayer item (a): formal refund prayer with 9% p.a. interest from payment date to realisation |
| Replacement requested | Prayer item (b): formal replacement prayer with "failing which, refund" fallback |
| Compensation for mental agony (INR) | Prayer item (c): "mental agony, harassment, inconvenience, hardship, and incidental expenses" |
| Costs of litigation | Prayer item (d): "as assessed by this Hon'ble Commission" |
| Custom reliefs (free text, one per line) | Appended verbatim after the standard items |

**Claim amount vs. transaction amount:** The claim amount (Step 4) is what drives jurisdiction routing — it should include everything the complainant wants, not just the refund. If a user paid ₹40,000 but wants ₹40,000 refund + ₹25,000 mental agony compensation, the claim amount is ₹65,000.

---

### Step 5 — Generate

The pipeline runs automatically on clicking **"📝 Generate draft complaint"**:

1. Assembles the `ComplaintIntake` Pydantic object from session state.
2. Calls `route_jurisdiction()` → `JurisdictionVerdict` (pure Python, no LLM).
3. Displays the jurisdiction verdict in a bordered container (forum, pecuniary basis, territorial options, limitation status, indicative filing fee).
4. Calls `draft_complaint(intake, verdict)`:
   - Gemini generates the statement of facts (constrained, ~10–16 paragraphs).
   - Assembler builds the full complaint text (deterministic).
   - `_write_docx()` saves a `.docx` to `output/`.
   - `_write_pdf()` saves a `.pdf` to `output/`.
5. Advances to Step 6.

**If the corpus is correct but the jurisdiction looks wrong:** go back to Step 4 and adjust the claim amount. The routing is purely mathematical — it does not read the narrative.

---

### Step 6 — Download

Two download buttons (DOCX and PDF), a preview expander showing the raw complaint text, and the **e-Daakhil filing checklist**:

- **Documents to attach** — complaint copy, affidavit, Vakalatnama (if using counsel), evidence Annexures listed by the playbook category, demand draft / online payment proof for filing fee
- **Filing steps** — 8-step walkthrough ending at [edaakhil.nic.in](https://edaakhil.nic.in)
- Limitation status and days remaining displayed prominently

A prominent warning: *"This draft is generated guidance, not legal advice. Before filing, have it reviewed by a qualified advocate."*

---

## Jurisdiction routing logic

Located in `core/jurisdiction.py`. Entirely deterministic — no LLM involved.

### Pecuniary (which forum)

Per the Consumer Protection (Jurisdiction of the District Commission, the State Commission and the National Commission) **Rules, 2021**:

| Forum | Claim amount |
|---|---|
| District Consumer Disputes Redressal Commission | ≤ ₹50,00,000 (₹50 lakh) |
| State Consumer Disputes Redressal Commission | > ₹50 lakh and ≤ ₹2,00,00,000 (₹2 crore) |
| National Consumer Disputes Redressal Commission | > ₹2 crore |

> **Note:** These limits have changed multiple times since the Act commenced in July 2020. The values above reflect the 2021 Rules. Verify current limits against the Department of Consumer Affairs' latest notification before filing.

### Territorial (where to file)

Under **Section 34(2) of CPA 2019**, a complaint may be filed where:

- **(a)** The opposite party **resides or carries on business** or has a branch office — OP's city
- **(b)** The **cause of action** wholly or in part arose — cause city (if different)
- **(c)** The complainant **resides or personally works for gain** — complainant's city ← *new under CPA 2019; not available under the 1986 Act*

All three valid locations are listed in the verdict and in the complaint's jurisdiction paragraph. The complainant chooses which one to actually file at.

### Limitation

Under **Section 69 of CPA 2019**, a complaint must be filed within **2 years** from the date the cause of action arose.

The agent flags three statuses:

| Status | Condition | Action |
|---|---|---|
| `within` | > 30 days remaining | Proceed normally |
| `borderline` | ≤ 30 days remaining | Highlighted warning — file immediately |
| `exceeded` | Past 2-year window | Warning — must file a separate Delay Condone Application with sufficient cause under the proviso to Section 69 |

### Indicative filing fee

Fees are stored in `data/jurisdictions.json` and are based on common practice across Consumer Commissions. They are **indicative only** — the actual fee varies by state. Some states waive fees for small claims; others use a different bracket schedule.

| District (indicative) | Fee |
|---|---|
| Up to ₹5 lakh | ₹200 |
| ₹5 lakh – ₹10 lakh | ₹400 |
| ₹10 lakh – ₹20 lakh | ₹500 |
| ₹20 lakh – ₹40 lakh | ₹2,000 |
| ₹40 lakh – ₹50 lakh | ₹4,000 |

---

## LLM pipeline

### Gemini's role — narrow and constrained

Gemini 2.5 Flash is called **once** per complaint generation. Its only job is to convert the user's plain-language narrative into formal Indian legal pleading prose. It does not:

- Decide jurisdiction (Python does this)
- Choose reliefs (Python builds the prayer block from the intake)
- Cite sections (Python appends the GROUNDS section from the knowledge base)
- Generate the verification, court header, or party blocks (Python assembles these)

The `_NARRATIVE_SYSTEM` prompt enforces these constraints explicitly:

```
MANDATORY STYLE RULES:
1. PARAGRAPH FORMAT: Every paragraph MUST begin with "That". Format: "Para 1.  That..."
2. VOICE: Third person only — "the Complainant", "the Opposite Party", "this Hon'ble Commission"
3. LEGAL TERMINOLOGY: "deficiency in service", "defect in the said goods", "unfair trade practice"
4. STATUTORY CITATIONS: "as defined under Section 2(10) of the Consumer Protection Act, 2019 (hereinafter 'the Act')"
5. MONETARY NOTATION: "Rs. X/- (Rupees X Only)"
6. EXHIBIT REFERENCES: "Annexure-A", "Annexure-B" in order of first introduction
7. STRICT FACTUAL ACCURACY: Use ONLY the facts in the intake. Never invent.
8. SCOPE: Do NOT include prayer / relief paragraphs.
```

### Category-specific vocabulary injection

Each complaint category has a `_CATEGORY_LEGAL_VOCAB` entry that is injected into the drafting prompt, telling Gemini which specific statutory sub-clauses and legal phrases apply:

| Category | Vocabulary injected |
|---|---|
| Defective goods | `defect` u/s 2(10), `product liability` u/s 2(34), `deficiency in service` u/s 2(11) if repair refused |
| Deficient service | `deficiency in service` u/s 2(11), `service` u/s 2(42) |
| Unfair trade practice | `unfair trade practice` u/s 2(47), specific sub-clauses (i), (vi), (viii); `false and misleading representation` |
| Medical negligence | `deficiency in service` u/s 2(11), consumer status u/s 2(7), standard of care |
| Real estate | `deficiency in service` u/s 2(11), `unfair trade practice` u/s 2(47), RERA cross-reference, Section 100 |
| E-commerce | `defect` u/s 2(10), `deficiency in service` u/s 2(11), Section 94, E-Commerce Rules 2020 |

### What the narrative prompt requests

The 10–16 paragraph narrative must cover these topics in order:

| Para range | Content required |
|---|---|
| 1 | Complainant's status as a **consumer** u/s 2(7) — what was purchased, for personal/household use, not for resale |
| 2 | Opposite Party's status — who they are, registered office, role as manufacturer / seller / service provider |
| 3–4 | Transaction — product/service, date, amount paid (Rs. format), invoice/order reference number; invoice = Annexure-A |
| 5 | Representation / promise made by the OP — quality, warranty, delivery date, specifications |
| 6–8 | The defect / deficiency / unfair practice — what went wrong, when discovered, how it falls within statutory definitions |
| 9–10 | Steps to resolve — complaint dates, pre-litigation notice (if any, = Annexure-D), OP's response or silence |
| 11 | Harm caused — financial loss, mental agony, harassment, loss of time, incidental expenses |
| 12 | Cause of action — when it arose, continuing cause (if applicable), within Section 69 limitation |
| 13 | Jurisdiction — pecuniary basis and territorial basis (complainant's place) |

### Gemini model configuration

```python
gemini_generate(
    prompt,
    system_instruction=_NARRATIVE_SYSTEM,
    temperature=0.15,      # low temperature: consistent formal style
    max_output_tokens=2800,
)
```

Temperature 0.15 keeps the output deterministic and formal — the goal is not creative writing but legal precision.

---

## Document generation

### DOCX (`_write_docx`)

- Font: **Times New Roman, 12pt** (the standard for Indian legal documents)
- Court header: **bold, centred, 13pt**
- Cause number: **bold, centred, 12pt**
- Section headers (MOST RESPECTFULLY SHOWETH, STATEMENT OF FACTS, GROUNDS, PRAYER, VERIFICATION): **bold, left-aligned**
- Party blocks: inline bold for `...COMPLAINANT` / `...OPPOSITE PARTY` lines
- Body paragraphs: left-aligned, 6pt space-after
- Saved to `output/complaint_[name]_[timestamp].docx`

### PDF (`_write_pdf`)

- Page size: **A4**
- Margins: 2.5 cm on all sides (standard legal document margins)
- Font: **Times-Roman / Times-Bold** (ReportLab's built-in Times family)
- Body text: 12pt, 18pt leading (line spacing)
- Court header: Times-Bold, 13pt, centred
- Section headers: Times-Bold, 12pt, left-aligned
- Built with ReportLab's `SimpleDocTemplate` + `Flowable` elements — no LibreOffice or external dependencies
- Saved to `output/complaint_[name]_[timestamp].pdf`

---

## Legal language

The generated complaint follows the same pleading conventions as real Indian Consumer Commission filings. Below is a comparison:

### Document structure

| Section | What appears in the draft |
|---|---|
| Court header | `BEFORE THE HON'BLE [CITY] DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, [STATE]` |
| Cause number | `Consumer Complaint No. _____ of [year]` |
| IN THE MATTER OF | Full party blocks with `...COMPLAINANT` and `...OPPOSITE PARTY` |
| Enabling provision | `COMPLAINT UNDER SECTION 35 OF THE CONSUMER PROTECTION ACT, 2019 (Read with ... Rules, 2021)` |
| Narrative opener | `MOST RESPECTFULLY SHOWETH:` followed by `STATEMENT OF FACTS` |
| Facts | `Para 1.  That...` / `Para 2.  That...` / ... (10–16 paragraphs) |
| Grounds | `GROUNDS:` with Roman numerals — `I. BECAUSE Section 2(7)...` / `II. BECAUSE Section 2(10)...` etc. |
| Prayer | `In the premises aforesaid... this Hon'ble Commission may graciously be pleased to: (a)... (b)...` |
| Closing | `AND FOR THIS ACT OF KINDNESS, THE COMPLAINANT AS IN DUTY BOUND SHALL EVER PRAY.` |
| Verification | Full verification affidavit: `"do hereby solemnly affirm and declare..."` |

### Prayer language examples

**Refund prayer:**
> Direct the Opposite Party to refund to the Complainant the sum of Rs. 25,000/- (Rupees 25 Thousand Only), being the amount paid by the Complainant, together with interest thereon at the rate of 9% per annum (or at such rate as this Hon'ble Commission may deem fit and proper) from the date of payment till the date of actual realisation.

**Compensation prayer:**
> Direct the Opposite Party to pay the Complainant a sum of Rs. 10,000/- (Rupees 10 Thousand Only) as compensation for the mental agony, harassment, inconvenience, hardship, and incidental expenses suffered and incurred by the Complainant as a direct and proximate consequence of the deficient and negligent conduct of the Opposite Party.

**Grounds section:**
> I. BECAUSE Section 2(10) of the Consumer Protection Act, 2019 — 'Definition: defect' — Any fault, imperfection, shortcoming or inadequacy in the quality, quantity, potency, purity or standard required to be maintained — is squarely attracted on the facts of the present case.
>
> II. BECAUSE the Complainant is a 'consumer' within the meaning of Section 2(7) of the Consumer Protection Act, 2019, having purchased the goods for consideration, for personal/household use and not for any commercial purpose or for resale.

---

## Knowledge base

Three static JSON files in `data/`. These are the only data the app reads — no database, no scraping, no live API fetches.

### `data/cpa_sections.json`

Key sections of the Consumer Protection Act, 2019 with curated summaries. Used to populate the GROUNDS section of the complaint.

| Section | Title |
|---|---|
| 2(7) | Definition: consumer |
| **2(10)** | **Definition: defect** |
| 2(11) | Definition: deficiency |
| 2(34) | Definition: product liability |
| **2(42)** | **Definition: service** |
| 2(47) | Definition: unfair trade practice |
| 17 | Filing of complaints |
| **34** | **Jurisdiction of District Commission — territorial** |
| 35 | Who may file a complaint |
| 38 | Procedure on admission of complaint |
| 39 | Reliefs available |
| 47 | Jurisdiction of State Commission |
| 69 | Limitation period |
| **94** | **E-commerce provisions** |
| 100 | Act in addition to other laws |

Sections marked **bold** were added to address earlier gaps — these are among the most commonly cited sections in real Consumer Commission filings.

**To add a section:** append an object to the `"sections"` array:
```json
{
  "section": "72",
  "title": "Penalty for non-compliance of order",
  "summary": "Where a trader or a person against whom an order is passed fails to comply without reasonable cause, the District Commission may sentence the person to imprisonment for up to three years or a fine of not less than Rs. 25,000 but not more than Rs. 1,00,000, or both."
}
```

---

### `data/playbook.json`

The complaint category playbook. Drives Step 1 of the wizard. Six categories:

| Key | Label | Primary sections |
|---|---|---|
| `defective_goods` | Defective goods (manufacturing defect, damaged product, wrong item) | 2(7), 2(10), 2(34), 39, 69 |
| `deficient_service` | Deficient service (telecom, banking, insurance, courier, e-commerce platform) | 2(7), 2(11), 2(42), 39, 69 |
| `unfair_trade_practice` | Unfair / misleading trade practice (false promises, hidden charges, misleading ads) | 2(7), 2(47), 39, 69 |
| `medical_negligence` | Medical negligence (consumer service deficiency by hospitals / clinics) | 2(7), 2(11), 2(42), 39, 69 |
| `real_estate` | Real estate / builder dispute (delayed possession, deviation from plan) | 2(7), 2(11), 2(34), 39, 69 |
| `e_commerce` | E-commerce / online marketplace dispute | 2(7), 2(10), 2(11), 94, 39, 69 |

Each category has:
- **`primary_sections`** — section IDs looked up in `cpa_sections.json` and used in the GROUNDS section
- **`typical_reliefs`** — formal legal relief language used when no custom reliefs are entered; also shown as suggestions in Step 4
- **`evidence_checklist`** — pre-populated evidence options in Step 1; items include `(Annexure-A)`, `(Annexure-B)` labels matching the narrative's exhibit references

**To add a category:** append an object to the `"categories"` array with all four fields. Also add the key to `_CATEGORY_LEGAL_VOCAB` in `core/drafter.py`.

---

### `data/jurisdictions.json`

Pecuniary thresholds, territorial rules, indicative filing fee schedule, and e-Daakhil portal URL. All sourced from the Consumer Protection (Jurisdiction of the District Commission, the State Commission and the National Commission) Rules, 2021.

```json
{
  "pecuniary_thresholds": {
    "district_commission_max_inr": 5000000,
    "state_commission_max_inr": 20000000
  },
  "territorial_rules": { ... },
  "filing_fee_indicative": {
    "district": [ {"upto_inr": 500000, "fee_inr": 200}, ... ],
    "state":    [ ... ],
    "national": [ ... ]
  },
  "e_filing": {
    "portal_name": "e-Daakhil",
    "portal_url": "https://edaakhil.nic.in"
  }
}
```

**Update pecuniary limits here** if the government issues revised Rules. Only two values need changing: `district_commission_max_inr` and `state_commission_max_inr`.

---

## Setup

```bash
cd consumer-commission-agent

# 1. Create a virtual environment (Python 3.10+)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env with API keys (see Environment variables section below)
#    The parent /LegalTech/.env is also auto-loaded if it exists

# 4. Run the app
streamlit run app.py
```

Open the URL Streamlit prints (default: http://localhost:8501).

> **Windows tip:** If the port is already in use, stop the other process with  
> `netstat -ano | findstr :8501` then `taskkill /PID [pid] /F`

---

## Environment variables

Create a `.env` file in `consumer-commission-agent/` (or in the parent `LegalTech/` directory — both are loaded):

```env
# Required
GOOGLE_API_KEY=AIza...              # Google AI Studio key — for Gemini 2.5 Flash
# Alternatively accepted:
# GEMINI_API_KEY=AIza...

GROQ_API_KEY=gsk_...               # Groq API key — for Llama 3.3 70B Versatile

# Optional overrides (defaults shown)
GEMINI_DRAFT_MODEL=gemini-2.5-flash
GROQ_FAST_MODEL=llama-3.3-70b-versatile
```

**Where to get keys:**
- Google API key: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — free tier sufficient for development
- Groq API key: [console.groq.com/keys](https://console.groq.com/keys) — generous free tier

**API usage per complaint generation:** One Gemini call (narrative polish, ~2,000–2,800 output tokens). The jurisdiction routing, document assembly, and checklist generation consume no API tokens.

---

## Repository layout

```
consumer-commission-agent/
├── app.py                      # Streamlit 6-step wizard, session state management
│
├── core/
│   ├── __init__.py
│   ├── config.py               # .env loading (local + parent), paths, model name constants
│   ├── llm.py                  # Gemini + Groq clients with 3-attempt retry logic
│   ├── knowledge.py            # LRU-cached JSON loaders: cpa_sections, jurisdictions, playbook
│   ├── intake.py               # Pydantic v2 models: PartyDetails, TransactionDetails,
│   │                           #   IssueDetails, ReliefSought, ComplaintIntake
│   ├── jurisdiction.py         # route() → JurisdictionVerdict (pecuniary + territorial + limitation)
│   ├── drafter.py              # _polish_narrative (Gemini), _reliefs_block, _grounds_section,
│   │                           #   _text_complaint, _write_docx, _write_pdf, draft_complaint()
│   └── checklist.py            # build_checklist() → e-Daakhil documents + steps + portal URL
│
├── data/
│   ├── cpa_sections.json       # 15 key CPA 2019 sections with curated summaries
│   ├── jurisdictions.json      # 2021 pecuniary rules, territorial rules, filing fees, portal
│   └── playbook.json           # 6 complaint categories × {sections, reliefs, evidence_checklist}
│
├── templates/                  # Reserved for future DOCX template overrides (currently unused)
│
├── output/                     # Generated DOCX + PDF land here (gitignored)
│   └── complaint_[name]_[ts].docx / .pdf
│
├── requirements.txt
└── .gitignore
```

### Key module responsibilities

**`core/drafter.py`** — the most complex module. Contains:

| Symbol | What it does |
|---|---|
| `_NARRATIVE_SYSTEM` | 10-rule system prompt enforcing Indian legal pleading conventions |
| `_CATEGORY_LEGAL_VOCAB` | Per-category dict of statutory vocabulary injected into each narrative prompt |
| `_polish_narrative()` | Builds the facts block, constructs the detailed prompt, calls Gemini |
| `_inr_words()` | Converts a float to "Rupees X Lakh Y Thousand Only" legal notation |
| `_reliefs_block()` | Builds the formal prayer items from the structured ReliefSought intake |
| `_grounds_section()` | Builds GROUNDS: with Roman-numeral BECAUSE clauses from relevant sections |
| `_text_complaint()` | Assembles the full complaint text in order: header → parties → facts → grounds → prayer → verification |
| `_write_docx()` | Writes Times New Roman, bold-header DOCX |
| `_write_pdf()` | Writes A4 Times-Roman PDF with legal margins |
| `draft_complaint()` | Orchestrates all of the above, returns `DraftBundle` |

**`core/jurisdiction.py`** — pure Python, zero LLM calls:

| Function | What it does |
|---|---|
| `_select_forum()` | Picks District / State / National from the claim amount |
| `_indicative_fee()` | Looks up the fee bracket from `jurisdictions.json` |
| `_limitation()` | Computes within / borderline / exceeded from cause-of-action date |
| `_territorial_options()` | Builds the three possible filing location strings |
| `route()` | Combines all of the above into a `JurisdictionVerdict` dataclass |

---

## How to extend

### Add a new complaint category

1. **`data/playbook.json`** — append a new object to `"categories"`:

```json
{
  "key": "insurance_claim",
  "label": "Insurance claim rejection / short settlement",
  "primary_sections": ["2(7)", "2(11)", "2(42)", "39", "69"],
  "typical_reliefs": [
    "Direct the Opposite Party / insurance company to forthwith settle and pay the full insured sum of Rs. X/- with interest at 9% per annum",
    "Direct the Opposite Party to pay compensation for mental agony and harassment",
    "Direct the Opposite Party to pay the costs of this complaint"
  ],
  "evidence_checklist": [
    "Insurance policy document (Annexure-A)",
    "Claim form and supporting documents submitted to insurer (Annexure-B)",
    "Rejection / partial settlement letter from insurer (Annexure-C)",
    "All correspondence with the insurer (Annexure-D)"
  ]
}
```

2. **`core/drafter.py`** — add the key to `_CATEGORY_LEGAL_VOCAB`:

```python
"insurance_claim": (
    "This matter involves wrongful rejection or short settlement of an insurance claim, "
    "constituting deficiency in service as defined under Section 2(11) of the Consumer "
    "Protection Act, 2019. The insurer is a 'service provider' and the policy-holder is "
    "a 'consumer' within Section 2(7). Reference IRDA regulations where the insurer "
    "violated mandatory settlement timelines."
),
```

No other changes needed — the rest of the pipeline picks up the new category automatically.

---

### Add or update a CPA section

Add an entry to `data/cpa_sections.json`:

```json
{
  "section": "72",
  "title": "Penalty for non-compliance of Commission order",
  "summary": "Where a trader fails or omits to comply with any order of the District Commission, State Commission or National Commission, without reasonable cause, the District Commission may impose imprisonment up to 3 years and/or a fine of Rs. 25,000 to Rs. 1,00,000."
}
```

Then reference `"72"` in any category's `"primary_sections"` list in `playbook.json`.

---

### Update pecuniary jurisdiction limits

If the Government issues a new Jurisdiction Rules notification changing the thresholds:

1. Edit `data/jurisdictions.json`:
```json
"pecuniary_thresholds": {
  "district_commission_max_inr": 10000000,   // updated: ₹1 crore
  "state_commission_max_inr": 100000000      // updated: ₹10 crore
}
```

2. Update the comment in the same file.

The routing logic in `core/jurisdiction.py` reads these values directly — no code change needed.

---

### Switch the drafting LLM

The Gemini call is in `core/drafter.py → _polish_narrative()` via `core/llm.py → gemini_generate()`. To switch to a different Gemini model:

```env
GEMINI_DRAFT_MODEL=gemini-2.5-pro   # higher quality, slower
```

To switch to a different provider entirely, replace the `gemini_generate()` call in `_polish_narrative()` with a function that accepts the same `(prompt, system_instruction, temperature, max_output_tokens)` signature.

---

## After download — the filing process

The agent generates a draft and a checklist. Here is the full process for actually filing:

### 1. Advocate review (strongly recommended)

Have the downloaded DOCX reviewed and edited by a qualified consumer law advocate before filing. The advocate may:
- Add or remove specific paragraphs
- Adjust the section references
- Add their Vakalatnama
- Attest the affidavit (some Commissions require notarisation)

### 2. Prepare the documents package

Using the e-Daakhil checklist as your guide:

| Document | Notes |
|---|---|
| Complaint (signed) | Print the PDF; complainant signs on every page or at minimum on the last page and the verification |
| Affidavit | Sworn before a Notary or Oath Commissioner; use the verification text at the end of the complaint as the affidavit body |
| Index and list of dates | One-page summary of key events; not generated by the agent — prepare manually |
| Memo of Parties | Names, addresses, and contact details of all parties; largely mirrors the party block |
| Evidence Annexures | Each Annexure labelled per the complaint — photocopy of invoice, photographs, correspondence, notice, etc. |
| Vakalatnama | If represented by counsel — standard form, signed by client and advocate |
| Filing fee payment proof | Demand Draft, UPI receipt, or NEFT/RTGS confirmation |

### 3. File on e-Daakhil

[edaakhil.nic.in](https://edaakhil.nic.in)

1. Register / log in with your mobile number (OTP-based)
2. Click **File Complaint → New Complaint**
3. Select **State → District → Commission**
4. Fill the online form with the same particulars as in the printed complaint
5. Upload PDF copies: complaint, affidavit, evidence Annexures
6. Pay the filing fee online (UPI / netbanking)
7. Note your **Case Diary Number** — this is your filing reference
8. The Commission will serve notice to the Opposite Party

### 4. Respond to Commission notices

After admission, the Commission typically:
- Issues notice to the Opposite Party, who must reply within 30 days (extendable to 45 days u/s 38 CPA 2019)
- Schedules hearing dates
- May require complainant to file evidence affidavits

The Opposite Party files a **Written Version** (a para-by-para reply to the complaint, as seen in the Hitachi Mohali case, Consumer Complaint No. 230 of 2024). After written version and evidence, the Commission proceeds to final arguments.

---

## Disclaimers

- **Not legal advice.** This tool generates a draft complaint for a qualified advocate's review. It is not a substitute for legal counsel. Do not file any document generated by this tool without having it reviewed by a licensed advocate.

- **Gemini is instructed not to invent facts** — but LLMs can still hallucinate. Read the generated narrative carefully. Every factual claim in the complaint must be verified against the intake you provided before filing. If any sentence does not accurately represent what happened, edit the DOCX before filing.

- **Knowledge base is curated, not exhaustive.** The section summaries in `cpa_sections.json` and the reliefs in `playbook.json` cover the most common cases but are not a complete statement of the law. An advocate reviewing the draft may identify additional applicable sections.

- **Pecuniary and territorial limits are jurisdiction-dependent.** The 2021 Rules apply nationally. Some states may have issued separate notifications. Verify with the relevant State Commission's website before filing.

- **Limitation calculation is conservative.** The 2-year window in Section 69 CPA 2019 is calculated from the date the complainant says the cause of action arose. The proviso to Section 69 allows the Commission to condone delay if sufficient cause is shown — the Commission decides this, not this tool.

- **Indicative filing fees are approximate.** The fee schedule in `data/jurisdictions.json` is based on common practice. The actual fee varies by state and may have been revised. Verify with the Commission's registry before preparing the demand draft.

- **e-Daakhil availability.** The e-Daakhil portal has been progressively rolled out. If your target Commission is not yet on e-Daakhil, physical filing at the Commission's registry may be required.

---

## License

MIT for the code. Knowledge-base JSON is editable under the same license. The Consumer Protection Act, 2019 and the Jurisdiction Rules, 2021 are Government of India publications in the public domain.
