"""Modèle de données de Rogier.

Toutes les dataclasses décrivant l'arbre d'un document, sa configuration
et son historique de versions. Conformes au §4 du SPEC.

Les structures sont sérialisables en JSON via les méthodes `to_dict`
(ou `dataclasses.asdict`), et reconstruites via les `from_dict` explicites.
Aucune auto-hydratation magique : chaque niveau imbriqué a son propre
constructeur depuis dict, pour garder le contrôle sur la migration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class NodeKind(StrEnum):
    """Types de nœuds de l'arbre hiérarchique belge."""

    DOCUMENT = "DOCUMENT"
    PARTIE = "PARTIE"
    LIVRE = "LIVRE"
    TITRE = "TITRE"
    CHAPITRE = "CHAPITRE"
    SECTION = "SECTION"
    SOUS_SECTION = "SOUS_SECTION"
    ARTICLE = "ARTICLE"


@dataclass
class ModificationMarker:
    """Marqueur [N...]N trouvé dans un contenu d'article.

    Ne contient pas la référence à la loi source (pas disponible inline
    dans le HTML Justel). Pour v0.1, on préserve juste le numéro et
    les positions. L'enrichissement avec la loi source viendra en v0.2.
    """

    number: int
    start_pos: int
    end_pos: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModificationMarker:
        return cls(
            number=int(data["number"]),
            start_pos=int(data["start_pos"]),
            end_pos=int(data["end_pos"]),
        )


@dataclass
class NodeMetadata:
    """Métadonnées attachées à un nœud de l'arbre."""

    source_range: tuple[int, int] | None = None
    warnings: list[str] = field(default_factory=list)
    modifications: list[ModificationMarker] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_range": list(self.source_range) if self.source_range else None,
            "warnings": list(self.warnings),
            "modifications": [asdict(m) for m in self.modifications],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NodeMetadata:
        if not data:
            return cls()
        raw_range = data.get("source_range")
        source_range: tuple[int, int] | None = (
            None if raw_range is None else (int(raw_range[0]), int(raw_range[1]))
        )
        return cls(
            source_range=source_range,
            warnings=list(data.get("warnings", [])),
            modifications=[ModificationMarker.from_dict(m) for m in data.get("modifications", [])],
        )


@dataclass
class Node:
    """Nœud de l'arbre document. Tous les niveaux partagent la même classe.

    Invariants :
    - Un ARTICLE n'a jamais d'enfants en v0.1.
    - Un non-ARTICLE a un `content` vide.
    """

    kind: NodeKind
    number: str = ""
    title: str = ""
    content: str = ""
    metadata: NodeMetadata = field(default_factory=NodeMetadata)
    children: list[Node] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == NodeKind.DOCUMENT:
            return self.title or "Document"
        if self.kind == NodeKind.ARTICLE:
            return f"Art. {self.number}"
        return f"{self.kind_label()} {self.number}"

    def kind_label(self) -> str:
        return {
            NodeKind.PARTIE: "Partie",
            NodeKind.LIVRE: "Livre",
            NodeKind.TITRE: "Titre",
            NodeKind.CHAPITRE: "Chapitre",
            NodeKind.SECTION: "Section",
            NodeKind.SOUS_SECTION: "Sous-section",
        }.get(self.kind, self.kind.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "number": self.number,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(
            kind=NodeKind(data["kind"]),
            number=data.get("number", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            metadata=NodeMetadata.from_dict(data.get("metadata")),
            children=[cls.from_dict(c) for c in data.get("children", [])],
        )


@dataclass
class ChunkingConfig:
    """Paramètres du chunker."""

    strategy: str = "per_article"  # 'per_article' ou 'hybrid'
    hybrid_threshold: int = 2000
    max_chunk_size: int = 5000
    include_breadcrumb: bool = True
    breadcrumb_levels: list[str] = field(default_factory=list)
    include_node_titles: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChunkingConfig:
        if not data:
            return cls()
        return cls(
            strategy=data.get("strategy", "per_article"),
            hybrid_threshold=int(data.get("hybrid_threshold", 2000)),
            max_chunk_size=int(data.get("max_chunk_size", 5000)),
            include_breadcrumb=bool(data.get("include_breadcrumb", True)),
            breadcrumb_levels=list(data.get("breadcrumb_levels", [])),
            include_node_titles=bool(data.get("include_node_titles", True)),
        )


@dataclass
class ValidationConfig:
    """Invariants sémantiques paramétrables par document."""

    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ValidationConfig:
        if not data:
            return cls()
        return cls(
            must_contain=list(data.get("must_contain", [])),
            must_not_contain=list(data.get("must_not_contain", [])),
        )


@dataclass
class DocumentConfig:
    """Configuration complète d'un document (versionnée)."""

    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    # Modifications manuelles : clé = chemin d'index dans l'arbre
    # ("0.2.1" = enfant 0 > enfant 2 > enfant 1), même format que le
    # paramètre ?node= des URLs de navigation. Valeur = nouveau contenu
    # (content pour ARTICLE, title pour les conteneurs).
    manual_edits: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunking": self.chunking.to_dict(),
            "validation": self.validation.to_dict(),
            "manual_edits": dict(self.manual_edits),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DocumentConfig:
        if not data:
            return cls()
        return cls(
            chunking=ChunkingConfig.from_dict(data.get("chunking")),
            validation=ValidationConfig.from_dict(data.get("validation")),
            manual_edits=dict(data.get("manual_edits", {})),
        )


@dataclass
class VersionRef:
    """Référence courte vers une version, stockée dans Document.versions."""

    id: str
    created_at: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionRef:
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            label=data["label"],
        )


@dataclass
class Version:
    """Version complète d'une configuration. Stockée séparément."""

    id: str
    document_hash: str
    created_at: str
    label: str
    note: str = ""
    config: DocumentConfig = field(default_factory=DocumentConfig)
    parent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_hash": self.document_hash,
            "created_at": self.created_at,
            "label": self.label,
            "note": self.note,
            "config": self.config.to_dict(),
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Version:
        return cls(
            id=data["id"],
            document_hash=data["document_hash"],
            created_at=data["created_at"],
            label=data["label"],
            note=data.get("note", ""),
            config=DocumentConfig.from_dict(data.get("config")),
            parent_id=data.get("parent_id"),
        )


@dataclass
class Document:
    """Document complet : arbre + métadonnées + historique."""

    hash: str
    name: str
    source_url: str | None = None
    source_filename: str | None = None
    created_at: str = ""
    family: str = "justel_html"
    tree: Node = field(default_factory=lambda: Node(kind=NodeKind.DOCUMENT))
    raw_html_path: str = ""
    current_version_id: str = ""
    versions: list[VersionRef] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "hash": self.hash,
            "name": self.name,
            "source_url": self.source_url,
            "source_filename": self.source_filename,
            "created_at": self.created_at,
            "family": self.family,
            "tree": self.tree.to_dict(),
            "raw_html_path": self.raw_html_path,
            "current_version_id": self.current_version_id,
            "versions": [v.to_dict() for v in self.versions],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        return cls(
            hash=data["hash"],
            name=data["name"],
            source_url=data.get("source_url"),
            source_filename=data.get("source_filename"),
            created_at=data.get("created_at", ""),
            family=data.get("family", "justel_html"),
            tree=Node.from_dict(data["tree"]),
            raw_html_path=data.get("raw_html_path", ""),
            current_version_id=data.get("current_version_id", ""),
            versions=[VersionRef.from_dict(v) for v in data.get("versions", [])],
            schema_version=int(data.get("schema_version", 1)),
        )
