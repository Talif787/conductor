"""Value objects for the Governance context."""

from __future__ import annotations

from enum import StrEnum


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    @property
    def is_decided(self) -> bool:
        return self in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
