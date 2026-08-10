"""Identifier value objects shared across bounded contexts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantId:
    value: uuid.UUID

    @staticmethod
    def new() -> TenantId:
        return TenantId(uuid.uuid4())

    @staticmethod
    def parse(raw: str) -> TenantId:
        return TenantId(uuid.UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UserId:
    value: uuid.UUID

    @staticmethod
    def new() -> UserId:
        return UserId(uuid.uuid4())

    @staticmethod
    def parse(raw: str) -> UserId:
        return UserId(uuid.UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class MembershipId:
    value: uuid.UUID

    @staticmethod
    def new() -> MembershipId:
        return MembershipId(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class RefreshTokenId:
    value: uuid.UUID

    @staticmethod
    def new() -> RefreshTokenId:
        return RefreshTokenId(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ToolId:
    value: uuid.UUID

    @staticmethod
    def new() -> ToolId:
        return ToolId(uuid.uuid4())

    @staticmethod
    def parse(raw: str) -> ToolId:
        return ToolId(uuid.UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class WorkflowId:
    value: uuid.UUID

    @staticmethod
    def new() -> WorkflowId:
        return WorkflowId(uuid.uuid4())

    @staticmethod
    def parse(raw: str) -> WorkflowId:
        return WorkflowId(uuid.UUID(raw))

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class WorkflowVersionId:
    value: uuid.UUID

    @staticmethod
    def new() -> WorkflowVersionId:
        return WorkflowVersionId(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class RunExecutionId:
    value: uuid.UUID

    @staticmethod
    def new() -> RunExecutionId:
        return RunExecutionId(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class StepExecutionId:
    value: uuid.UUID

    @staticmethod
    def new() -> StepExecutionId:
        return StepExecutionId(uuid.uuid4())

    def __str__(self) -> str:
        return str(self.value)
