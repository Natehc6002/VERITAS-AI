"""Transparent, rule-based document classification.

This is an explainable keyword/pattern baseline - not a machine-learning model.
Every decision records the exact rules that fired so users can audit it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORIES: dict[str, str] = {
    "invoice": "Invoice",
    "receipt": "Receipt",
    "certificate": "Certificate",
    "identity_document": "Identity document",
    "financial_statement": "Financial statement",
    "contract": "Contract",
    "report": "Report",
    "other": "Other",
}


@dataclass(frozen=True)
class Rule:
    category: str
    pattern: re.Pattern[str]
    weight: float
    description: str


def _r(category: str, pattern: str, weight: float, description: str) -> Rule:
    return Rule(category=category, pattern=re.compile(pattern, re.IGNORECASE), weight=weight, description=description)


RULES: list[Rule] = [
    # Invoices
    _r("invoice", r"\binvoice\b", 3.0, "Contains the word 'invoice'"),
    _r("invoice", r"\binvoice\s*(no|number|#)\b", 3.0, "Contains an invoice number label"),
    _r("invoice", r"\b(bill to|ship to|payable to|due date)\b", 2.0, "Contains billing address labels"),
    _r("invoice", r"\b(tax invoice|invoice total|subtotal)\b", 2.5, "Contains invoice totals terminology"),
    _r("invoice", r"\bqty\b|\bquantity\b", 1.0, "Contains line-item quantity columns"),
    # Receipts
    _r("receipt", r"\breceipt\b", 3.0, "Contains the word 'receipt'"),
    _r("receipt", r"\b(amount paid|change due|cashier|purchase)\b", 2.0, "Contains point-of-sale terminology"),
    _r("receipt", r"\bthank you for your (purchase|business)\b", 2.5, "Contains receipt thank-you footer"),
    # Certificates
    _r("certificate", r"\bcertificate\b", 3.0, "Contains the word 'certificate'"),
    _r("certificate", r"\b(certified|hereby awarded|presented to|is awarded)\b", 2.5, "Contains award/certification phrasing"),
    _r("certificate", r"\b(seal|signature of|authorised signatory)\b", 1.5, "Contains seal or signatory block"),
    # Identity documents
    _r("identity_document", r"\b(date of birth|dob)\b", 3.0, "Contains a date-of-birth label"),
    _r("identity_document", r"\b(passport|driver'?s? license|national id|aadhaar|pan card|social security)\b", 3.0, "Names an identity document type"),
    _r("identity_document", r"\b(gender|sex)\b.*\b(nationality|citizenship)\b", 2.0, "Contains demographic identity fields"),
    # Financial statements
    _r("financial_statement", r"\b(balance sheet|income statement|cash flow statement|profit and loss)\b", 3.5, "Names a financial statement"),
    _r("financial_statement", r"\b(account statement|bank statement)\b", 3.0, "Contains a bank/account statement label"),
    _r("financial_statement", r"\b(assets|liabilities|equity)\b.*\b(total|balance)\b", 2.0, "Contains accounting balance terminology"),
    _r("financial_statement", r"\b(opening balance|closing balance|transactions)\b", 2.0, "Contains statement period terminology"),
    # Contracts
    _r("contract", r"\bagreement\b", 3.0, "Contains the word 'agreement'"),
    _r("contract", r"\b(this contract\b|\bterms and conditions\b|\bhereby agree\b)", 3.0, "Contains contract commitment language"),
    _r("contract", r"\b(governing law|indemnif|liabilit(y|ies)|termination clause)\b", 2.5, "Contains legal clause terminology"),
    _r("contract", r"\b(party of the first part|lessor|lessee|licensor|licensee)\b", 2.5, "Contains contractual party roles"),
    # Reports
    _r("report", r"\b(report)\b", 2.0, "Contains the word 'report'"),
    _r("report", r"\b(executive summary|introduction|methodology|findings|recommendation)\b", 2.5, "Contains report section headings"),
    _r("report", r"\b(prepared by|submitted to|department)\b", 1.5, "Contains report attribution labels"),
]

DEFAULT_CATEGORY = "other"
MIN_SCORE_FOR_CONFIDENT_LABEL = 3.0


def classify_text(text: str, filename: str = "") -> dict:
    """Classify ``text`` and return an explainable result dictionary.

    Returns::

        {
          "category": str,
          "category_label": str,
          "confidence": float,
          "rationale": [{"rule": str, "category": str, "weight": float, "matched": str}],
          "method": "rule_based_baseline",
        }
    """
    haystack = f"{filename}\n{text}" if filename else text
    scores: dict[str, float] = {key: 0.0 for key in CATEGORIES}
    rationale: list[dict] = []

    for rule in RULES:
        match = rule.pattern.search(haystack)
        if match:
            scores[rule.category] += rule.weight
            rationale.append(
                {
                    "rule": rule.description,
                    "category": rule.category,
                    "weight": rule.weight,
                    "matched": match.group(0)[:120],
                }
            )

    best_category = max(scores, key=lambda key: scores[key])
    best_score = scores[best_category]

    if best_score <= 0:
        return {
            "category": DEFAULT_CATEGORY,
            "category_label": CATEGORIES[DEFAULT_CATEGORY],
            "confidence": 0.0,
            "rationale": [],
            "method": "rule_based_baseline",
        }

    total = sum(scores.values()) or 1.0
    confidence = round(min(0.99, best_score / total), 4)
    if best_score < MIN_SCORE_FOR_CONFIDENT_LABEL:
        confidence = round(min(confidence, 0.4), 4)

    return {
        "category": best_category,
        "category_label": CATEGORIES[best_category],
        "confidence": confidence,
        "rationale": rationale,
        "method": "rule_based_baseline",
    }
