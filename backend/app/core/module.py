"""Lego module contract.

Every sub-module, always-on module and shared service implements `Module`.
Orchestrators look modules up by name in the registry and call `run` only
when they need them, so nothing loads or spends model calls unless invoked.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .context import CaseContext


@dataclass
class ModuleResult:
    status: str  # "ok" | "needs_approval" | "handoff" | "stub" | "error"
    data: dict[str, Any] = field(default_factory=dict)
    summary_en: str = ""
    summary_bm: str = ""
    handoff_to: str | None = None  # department key, only meaningful for status="handoff"


class Module(ABC):
    name: ClassVar[str]
    kind: ClassVar[str]  # "submodule" | "always_on" | "service"
    department: ClassVar[str | None] = None

    @abstractmethod
    async def run(self, ctx: CaseContext, **kwargs: Any) -> ModuleResult: ...


class Registry:
    def __init__(self) -> None:
        self._modules: dict[str, type[Module]] = {}

    def register(self, cls: type[Module]) -> type[Module]:
        if cls.name in self._modules:
            raise ValueError(f"duplicate module name: {cls.name}")
        self._modules[cls.name] = cls
        return cls

    def get(self, name: str) -> Module:
        return self._modules[name]()

    def names(self, kind: str | None = None, department: str | None = None) -> list[str]:
        return [
            n for n, c in self._modules.items()
            if (kind is None or c.kind == kind) and (department is None or c.department == department)
        ]


registry = Registry()
