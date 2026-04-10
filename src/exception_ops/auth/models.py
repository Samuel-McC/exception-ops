from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperatorRole(str, Enum):
    REVIEWER = "reviewer"
    APPROVER = "approver"
    EXECUTOR = "executor"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class ConfiguredOperator:
    username: str
    password_hash: str
    roles: frozenset[OperatorRole]


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    username: str
    roles: frozenset[OperatorRole]

    def has_any_role(self, *roles: OperatorRole) -> bool:
        return OperatorRole.ADMIN in self.roles or any(role in self.roles for role in roles)
