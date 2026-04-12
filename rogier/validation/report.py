"""Rapport de validation — SPEC §11.3.

Orchestre les invariants structurels et sémantiques, produit un
ValidationReport avec un statut global.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from rogier.parsing.tree import Node, ValidationConfig
from rogier.validation.semantic import run_semantic
from rogier.validation.structural import collect_all_warnings, run_structural


@dataclass
class InvariantResult:
    """Résultat d'un invariant individuel."""

    id: str
    level: int  # 1 (structurel) ou 2 (sémantique)
    description: str
    status: str  # 'pass' | 'fail'
    detail: str
    data: dict | None = None  # champ structuré optionnel (ex: S008 count)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "level": self.level,
            "description": self.description,
            "status": self.status,
            "detail": self.detail,
        }
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass
class ValidationReport:
    """Rapport de validation complet."""

    structural: list[InvariantResult] = field(default_factory=list)
    semantic: list[InvariantResult] = field(default_factory=list)
    overall: str = "pass"  # 'pass' | 'fail'
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "structural": [r.to_dict() for r in self.structural],
            "semantic": [r.to_dict() for r in self.semantic],
            "overall": self.overall,
            "generated_at": self.generated_at,
        }


def _dict_to_result(d: dict) -> InvariantResult:
    """Convertir un dict brut (retourné par structural/semantic) en InvariantResult."""
    return InvariantResult(
        id=d["id"],
        level=d["level"],
        description=d["description"],
        status=d["status"],
        detail=d["detail"],
        data=d.get("data"),
    )


def build_report(
    root: Node,
    validation_config: ValidationConfig | None = None,
    manual_edits: dict[str, str] | None = None,
) -> ValidationReport:
    """Construire le rapport de validation complet.

    Exécute les invariants structurels (S001–S008), puis les invariants
    sémantiques si une ValidationConfig est fournie.

    Pour S008, le check final vérifie que tous les warnings de parsing
    de l'arbre sont bien référencés dans le rapport.
    """
    if validation_config is None:
        validation_config = ValidationConfig()
    if manual_edits is None:
        manual_edits = {}

    # Structurels
    raw_structural = run_structural(root, manual_edits)
    structural_results = [_dict_to_result(d) for d in raw_structural]

    # S008 cross-check : vérifier que le nombre de warnings collecté par
    # check_s008 correspond au nombre réel dans l'arbre.
    tree_warnings = collect_all_warnings(root)
    s008 = next((r for r in structural_results if r.id == "S008"), None)
    if s008 and tree_warnings:
        expected_count = len(tree_warnings)
        s008_count = (s008.data or {}).get("count", -1)
        if s008_count != expected_count:
            s008.status = "fail"
            s008.detail = (
                f"Incohérence : {expected_count} warning(s) dans l'arbre, "
                f"mais S008 en a compté {s008_count}."
            )

    # Sémantiques
    raw_semantic = run_semantic(root, validation_config, manual_edits)
    semantic_results = [_dict_to_result(d) for d in raw_semantic]

    # Statut global
    all_results = structural_results + semantic_results
    has_fail = any(r.status == "fail" for r in all_results)
    overall = "fail" if has_fail else "pass"

    return ValidationReport(
        structural=structural_results,
        semantic=semantic_results,
        overall=overall,
        generated_at=datetime.now(tz=UTC).isoformat(),
    )
