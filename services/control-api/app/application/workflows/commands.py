from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateWorkflow:
    tenant_id: str
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class UpdateDraft:
    tenant_id: str
    workflow_id: str
    version: int
    definition: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PublishVersion:
    tenant_id: str
    workflow_id: str
    version: int


@dataclass(frozen=True, slots=True)
class CreateDraft:
    tenant_id: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class ArchiveWorkflow:
    tenant_id: str
    workflow_id: str
