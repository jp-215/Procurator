# Orders Service — Specification (the Mandate)

Implement the `ordersvc` Python package in `src/ordersvc/`. Each section below is an
acceptance criterion (AC). Work is graded by a hidden acceptance suite mapped 1:1 to
these AC numbers — you cannot see the tests, only this spec.

## Auth (`auth.py`)
- **AC-01** `issue_token(user_id: str, ttl_seconds: int = 3600, *, now: float | None = None) -> str`
  returns an opaque token string bound to the user. `now` (epoch seconds) defaults to current time.
- **AC-02** `verify_token(token: str, *, now: float | None = None) -> str` returns the `user_id`
  for a valid, unexpired, unrevoked token.
- **AC-03** A token past its TTL raises `TokenExpired`.
- **AC-04** `revoke_token(token: str) -> None`; a revoked token raises `TokenRevoked` on verify.

## Orders (`orders.py`, backed by `store.py`)
- **AC-05** `create_order(user_id, items, idempotency_key=None) -> Order` creates an order with a
  unique `id`, `status == "pending"`, and `created_at` (epoch float). `items` is a list of
  `{"sku": str, "qty": int, "unit_price": float}` dicts.
- **AC-06** Calling `create_order` twice with the same `idempotency_key` returns the SAME order
  (same `id`); no duplicate is stored.
- **AC-07** Empty `items` raises `ValidationError`.
- **AC-08** `Order.total` equals the sum of `qty * unit_price` over items, rounded to 2 decimals.
- **AC-09** `get_order(order_id) -> Order` returns the stored order.
- **AC-10** Unknown id raises `OrderNotFound`.
- **AC-11** `cancel_order(order_id)` on a `pending` order sets status `cancelled`.
- **AC-12** Cancelling a `shipped` order raises `InvalidTransition`.
- **AC-13** Status machine is strict: pending→paid (via `pay_order`), paid→shipped (via
  `ship_order`). Any other transition raises `InvalidTransition`.
- **AC-14** `list_orders(user_id=None, status=None) -> list[Order]` filters by either/both.
- **AC-15** `pay_order(order_id, token)` verifies the token and requires the token's user to be
  the order's owner, else raises `Forbidden`.

## Pagination (`pagination.py`)
- **AC-16** `paginate(items: list, limit: int, cursor: str | None = None) -> Page` returns at most
  `limit` items in `page.items`.
- **AC-17** Passing `page.next_cursor` back returns the next slice, with no overlap or gaps.
- **AC-18** Ordering is stable: sort by `created_at` ascending, tie-broken by `id` ascending,
  regardless of input order.
- **AC-19** When the collection is exhausted, `next_cursor` is `None`.

## Retry (`retry.py`)
- **AC-20** `retry_with_backoff(fn, max_attempts=3, base_delay=0.1, sleep=time.sleep)` calls `fn`
  until it succeeds, retrying only on `TransientError`.
- **AC-21** After `max_attempts` failures it re-raises the last `TransientError`.
- **AC-22** A non-transient exception propagates immediately (no retry).
- **AC-23** Delays follow exponential backoff: base_delay * 2**attempt for attempt 0,1,...
  (observable via the injectable `sleep`).

## Store (`store.py`)
- **AC-24** `MemoryStore` supports `put(key, value)` / `get(key)` roundtrip; missing key raises `KeyError`.
- **AC-25** `delete(key)` removes the key; subsequent `get` raises `KeyError`.
