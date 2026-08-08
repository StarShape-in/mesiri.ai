"""A minimal ``Result`` type for explicit success/failure without exceptions.

Used where callers should handle failure as data (health checks, provider
calls) rather than by propagating exceptions across boundaries. The error arm
is always a :class:`MesiriError`.

Ownership: SHARED ARCHITECTURE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .errors import MesiriError

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    """Either a value (``ok``) or a :class:`MesiriError` (``err``)."""

    _value: T | None = None
    _error: MesiriError | None = None

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(_value=value, _error=None)

    @classmethod
    def err(cls, error: MesiriError) -> Result[T]:
        return cls(_value=None, _error=error)

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def is_err(self) -> bool:
        return self._error is not None

    @property
    def error(self) -> MesiriError | None:
        return self._error

    def unwrap(self) -> T:
        if self._error is not None:
            raise self._error
        return self._value  # type: ignore[return-value]

    def unwrap_or(self, default: T) -> T:
        return default if self._error is not None else self._value  # type: ignore[return-value]
