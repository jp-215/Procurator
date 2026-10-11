"""Order lifecycle — see SPEC.md AC-05..AC-15."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Order:
    id: str = ""
    user_id: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    created_at: float = 0.0

    @property
    def total(self) -> float:
        raise NotImplementedError  # TODO: AC-08


def create_order(user_id: str, items: list[dict[str, Any]], idempotency_key: str | None = None) -> Order:
    raise NotImplementedError  # TODO: AC-05, AC-06, AC-07


def get_order(order_id: str) -> Order:
    raise NotImplementedError  # TODO: AC-09, AC-10


def cancel_order(order_id: str) -> Order:
    raise NotImplementedError  # TODO: AC-11, AC-12


def pay_order(order_id: str, token: str) -> Order:
    raise NotImplementedError  # TODO: AC-13, AC-15


def ship_order(order_id: str) -> Order:
    raise NotImplementedError  # TODO: AC-13


def list_orders(user_id: str | None = None, status: str | None = None) -> list[Order]:
    raise NotImplementedError  # TODO: AC-14


def _reset() -> None:
    """Test hook: clear all stored orders and idempotency records."""
    raise NotImplementedError
