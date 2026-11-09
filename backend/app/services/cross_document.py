"""Cross-document comparison: shared entities, related records and conflicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DocumentNotFoundError
from app.models.document import Document
from app.models.intelligence import Entity, TextExtraction

# Entity types that normally hold a single value per document/label context.
SINGLE_VALUED_TYPES = {"document_identifier"}

RELATED_THRESHOLD = 2

# Fuzzy (near-match) sharing is limited to name-like types so identifiers,
# dates and amounts are never merged by similarity.
FUZZY_ENTITY_TYPES = {"organization", "person_name", "address"}
FUZZY_THRESHOLD = 0.80


@dataclass
class _DocContext:
    document: Document
    entities: list[Entity] = field(default_factory=list)

    def by_type(self, entity_type: str) -> list[Entity]:
        return [e for e in self.entities if e.entity_type == entity_type]


def compare_documents(db: Session, document_ids: list[str]) -> dict[str, Any]:
    """Compare 2+ documents and return an explainable report."""
    if len(document_ids) < 2:
        raise ValueError("At least two documents are required for comparison.")

    contexts: list[_DocContext] = []
    seen: set[str] = set()
    for document_id in document_ids:
        if document_id in seen:
            continue
        seen.add(document_id)
        document = db.get(Document, str(document_id))
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found.")
        entities = list(
            db.scalars(select(Entity).where(Entity.document_id == document.id)).all()
        )
        contexts.append(_DocContext(document=document, entities=entities))

    if len(contexts) < 2:
        raise ValueError("At least two distinct documents are required for comparison.")

    exact_shared = _shared_entities(contexts)
    fuzzy_shared = _fuzzy_shared_entities(contexts, exact_shared)
    shared = sorted(
        exact_shared + fuzzy_shared,
        key=lambda item: (-item["document_count"], item["entity_type"], item["value"]),
    )
    related = _related_records(contexts, shared)
    conflicts = _conflicts(contexts, exact_shared)

    return {
        "document_ids": [ctx.document.id for ctx in contexts],
        "document_names": [ctx.document.original_filename for ctx in contexts],
        "shared_entities": shared,
        "related_records": related,
        "conflicts": conflicts,
        "summary": {
            "documents_compared": len(contexts),
            "shared_entity_count": len(shared),
            "fuzzy_match_count": len(fuzzy_shared),
            "related_record_count": len(related),
            "conflict_count": len(conflicts),
        },
        "method": "exact_normalized_matching+fuzzy_name_matching",
        "disclaimer": (
            "Matches and conflicts are explainable observations derived from extracted "
            "text. Shared values are not inherently suspicious and conflicting values are "
            "not proof of fraud - both require human review."
        ),
    }


def _shared_entities(contexts: list[_DocContext]) -> list[dict[str, Any]]:
    """Values (normalized) that appear in two or more documents."""
    index: dict[tuple[str, str], list[tuple[_DocContext, Entity]]] = {}
    for ctx in contexts:
        for entity in ctx.entities:
            key_value = (entity.normalized_value or entity.value).strip().lower()
            if not key_value:
                continue
            index.setdefault((entity.entity_type, key_value), []).append((ctx, entity))

    shared: list[dict[str, Any]] = []
    for (entity_type, key_value), occurrences in index.items():
        docs = {ctx.document.id for ctx, _ in occurrences}
        if len(docs) < 2:
            continue
        shared.append(
            {
                "entity_type": entity_type,
                "value": occurrences[0][1].value,
                "normalized_value": key_value,
                "match_type": "exact",
                "document_count": len(docs),
                "occurrences": [
                    {
                        "document_id": ctx.document.id,
                        "document_name": ctx.document.original_filename,
                        "page_number": entity.page_number,
                        "source_text": entity.source_text,
                        "confidence": entity.confidence,
                    }
                    for ctx, entity in occurrences
                ],
                "explanation": (
                    f"The value '{occurrences[0][1].value}' ({entity_type}) appears in "
                    f"{len(docs)} documents."
                ),
            }
        )
    shared.sort(key=lambda item: (-item["document_count"], item["entity_type"], item["value"]))
    return shared


def _fuzzy_shared_entities(
    contexts: list[_DocContext], exact_shared: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Near-identical name-like values across documents (difflib similarity).

    Only organization / person / address values are considered, the threshold is
    ``FUZZY_THRESHOLD`` and values already exactly shared are skipped.
    """
    exact_keys = {
        (item["entity_type"], item["normalized_value"]) for item in exact_shared
    }
    # Per type -> document -> list of (normalized, entity)
    per_type: dict[str, dict[str, list[tuple[str, Entity]]]] = {}
    for ctx in contexts:
        for entity in ctx.entities:
            if entity.entity_type not in FUZZY_ENTITY_TYPES:
                continue
            norm = (entity.normalized_value or entity.value).strip().lower()
            if not norm or len(norm) < 6:
                continue
            per_type.setdefault(entity.entity_type, {}).setdefault(
                ctx.document.id, []
            ).append((norm, entity))

    fuzzy: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    name_by_id = {ctx.document.id: ctx.document.original_filename for ctx in contexts}

    for entity_type, doc_values in per_type.items():
        doc_ids = sorted(doc_values)
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                left_id, right_id = doc_ids[i], doc_ids[j]
                for left_norm, left_entity in doc_values[left_id]:
                    if (entity_type, left_norm) in exact_keys:
                        continue
                    for right_norm, right_entity in doc_values[right_id]:
                        if left_norm == right_norm:
                            continue
                        if (entity_type, right_norm) in exact_keys:
                            continue
                        pair_key = tuple(sorted((left_norm, right_norm)))
                        marker = (entity_type, pair_key[0], pair_key[1])
                        if marker in seen:
                            continue
                        ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
                        if ratio < FUZZY_THRESHOLD:
                            continue
                        seen.add(marker)
                        fuzzy.append(
                            {
                                "entity_type": entity_type,
                                "value": left_entity.value,
                                "normalized_value": left_norm,
                                "match_type": "fuzzy",
                                "similarity": round(ratio, 3),
                                "fuzzy_variant": right_entity.value,
                                "document_count": 2,
                                "occurrences": [
                                    {
                                        "document_id": left_id,
                                        "document_name": name_by_id[left_id],
                                        "page_number": left_entity.page_number,
                                        "source_text": left_entity.source_text,
                                        "confidence": left_entity.confidence,
                                    },
                                    {
                                        "document_id": right_id,
                                        "document_name": name_by_id[right_id],
                                        "page_number": right_entity.page_number,
                                        "source_text": right_entity.source_text,
                                        "confidence": right_entity.confidence,
                                    },
                                ],
                                "explanation": (
                                    f"Fuzzy match ({ratio:.0%} similar): "
                                    f"'{left_entity.value}' in {name_by_id[left_id]} "
                                    f"≈ '{right_entity.value}' in {name_by_id[right_id]}. "
                                    "Similar names may refer to the same entity and "
                                    "require human review."
                                ),
                            }
                        )
    fuzzy.sort(key=lambda item: (-item["similarity"], item["entity_type"]))
    return fuzzy


def _related_records(contexts: list[_DocContext], shared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Document pairs sharing at least RELATED_THRESHOLD distinct values."""
    pair_matches: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in shared:
        ids = sorted({occ["document_id"] for occ in item["occurrences"]})
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pair_matches.setdefault((ids[i], ids[j]), []).append(item)

    name_by_id = {ctx.document.id: ctx.document.original_filename for ctx in contexts}
    related: list[dict[str, Any]] = []
    for (left, right), items in pair_matches.items():
        if len(items) < RELATED_THRESHOLD:
            continue
        related.append(
            {
                "document_ids": [left, right],
                "document_names": [name_by_id[left], name_by_id[right]],
                "shared_values": [
                    {
                        "entity_type": item["entity_type"],
                        "value": item["value"],
                    }
                    for item in items
                ],
                "explanation": (
                    f"'{name_by_id[left]}' and '{name_by_id[right]}' share "
                    f"{len(items)} distinct extracted values."
                ),
            }
        )
    related.sort(key=lambda item: -len(item["shared_values"]))
    return related


def _conflicts(contexts: list[_DocContext], shared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []

    conflicts.extend(_label_value_conflicts(contexts))
    conflicts.extend(_person_contact_conflicts(contexts, shared))
    return conflicts


def _label_value_conflicts(contexts: list[_DocContext]) -> list[dict[str, Any]]:
    """Same identifier label with different values across related documents."""
    # Only compare documents that already share some other entity (context).
    shared_context_keys: set[str] = set()
    for entity_type in ("person_name", "organization"):
        values: dict[str, set[str]] = {}
        for ctx in contexts:
            for entity in ctx.by_type(entity_type):
                key = (entity.normalized_value or entity.value).lower()
                values.setdefault(key, set()).add(ctx.document.id)
        for key, docs in values.items():
            if len(docs) >= 2:
                shared_context_keys.add(f"{entity_type}:{key}")

    conflicts: list[dict[str, Any]] = []
    label_values: dict[str, dict[str, list[tuple[_DocContext, Entity]]]] = {}
    for ctx in contexts:
        for entity in ctx.by_type("document_identifier"):
            label = _identifier_label(entity)
            label_values.setdefault(label, {}).setdefault(
                (entity.normalized_value or entity.value).upper(), []
            ).append((ctx, entity))

    for label, value_map in label_values.items():
        if len(value_map) < 2:
            continue
        # Require that a person/organization is shared between the involved docs.
        involved_ids = {
            ctx.document.id for occurrences in value_map.values() for ctx, _ in occurrences
        }
        if not _shares_context(contexts, involved_ids, shared_context_keys):
            continue
        value_entries = []
        for value, occurrences in value_map.items():
            value_entries.append(
                {
                    "value": occurrences[0][1].value,
                    "documents": [
                        {
                            "document_id": ctx.document.id,
                            "document_name": ctx.document.original_filename,
                            "page_number": entity.page_number,
                            "source_text": entity.source_text,
                        }
                        for ctx, entity in occurrences
                    ],
                }
            )
        conflicts.append(
            {
                "conflict_type": "identifier_label_mismatch",
                "field": label,
                "values": value_entries,
                "explanation": (
                    f"The '{label}' label carries different values across documents that "
                    "also share person/organization entities: "
                    + "; ".join(
                        f"'{entry['value']}' in "
                        + ", ".join(d["document_name"] for d in entry["documents"])
                        for entry in value_entries
                    )
                    + ". Review in context before drawing conclusions."
                ),
                "severity": "medium",
            }
        )
    return conflicts


def _shares_context(
    contexts: list[_DocContext],
    involved_ids: set[str],
    shared_context_keys: set[str],
) -> bool:
    """True when a person/organization entity appears in every involved document."""
    if not shared_context_keys:
        return False
    for ctx in contexts:
        if ctx.document.id not in involved_ids:
            continue
    for key in shared_context_keys:
        docs_with_key: set[str] = set()
        for ctx in contexts:
            for entity in ctx.entities:
                prefix = f"{entity.entity_type}:"
                if not key.startswith(prefix):
                    continue
                if (entity.normalized_value or entity.value).lower() == key[len(prefix):]:
                    docs_with_key.add(ctx.document.id)
        if involved_ids <= docs_with_key:
            return True
    return False


def _identifier_label(entity: Entity) -> str:
    haystack = f"{entity.source_text or ''} {entity.value}".lower()
    for label in (
        "invoice", "bill", "receipt", "po", "purchase order", "ref", "reference",
        "order", "policy", "account", "passport", "license",
    ):
        if label in haystack:
            return label
    return entity.value.lower().split(":")[0].strip() or "identifier"


def _person_contact_conflicts(
    contexts: list[_DocContext], shared: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Same person appears with different email/phone values across documents."""
    shared_people = {
        item["normalized_value"]
        for item in shared
        if item["entity_type"] == "person_name"
    }
    if not shared_people:
        return []

    conflicts: list[dict[str, Any]] = []
    for person in sorted(shared_people):
        emails: dict[str, list[dict[str, Any]]] = {}
        phones: dict[str, list[dict[str, Any]]] = {}
        for ctx in contexts:
            person_present = any(
                (e.normalized_value or e.value).lower() == person for e in ctx.by_type("person_name")
            )
            if not person_present:
                continue
            for entity in ctx.by_type("email"):
                emails.setdefault((entity.normalized_value or entity.value).lower(), []).append(
                    _occurrence(ctx, entity)
                )
            for entity in ctx.by_type("phone"):
                phones.setdefault((entity.normalized_value or entity.value), []).append(
                    _occurrence(ctx, entity)
                )

        for field_name, mapping in (("email", emails), ("phone", phones)):
            if len(mapping) < 2:
                continue
            involved = {occ["document_id"] for occs in mapping.values() for occ in occs}
            if len(involved) < 2:
                continue
            values = [
                {
                    "value": key,
                    "documents": occs,
                }
                for key, occs in mapping.items()
            ]
            conflicts.append(
                {
                    "conflict_type": "person_contact_mismatch",
                    "field": field_name,
                    "subject": person,
                    "values": values,
                    "explanation": (
                        f"Documents mentioning the same person ('{person}') contain "
                        f"different {field_name} values: "
                        + "; ".join(f"'{entry['value']}'" for entry in values)
                        + ". Contact details frequently differ legitimately, so treat this "
                        "as a review prompt rather than evidence of wrongdoing."
                    ),
                    "severity": "low",
                }
            )
    return conflicts


def _occurrence(ctx: _DocContext, entity: Entity) -> dict[str, Any]:
    return {
        "document_id": ctx.document.id,
        "document_name": ctx.document.original_filename,
        "page_number": entity.page_number,
        "source_text": entity.source_text,
    }
