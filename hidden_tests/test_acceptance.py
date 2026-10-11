"""Hidden acceptance suite. Agents NEVER see this file.

Each test maps 1:1 to an AC in target/SPEC.md via its name: test_ac<NN>_*.
The sandbox runner parses names to report per-AC pass/fail.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def fresh_state():
    import ordersvc.orders as orders

    try:
        orders._reset()
    except NotImplementedError:
        pass
    yield


ITEMS = [
    {"sku": "A", "qty": 2, "unit_price": 3.50},
    {"sku": "B", "qty": 1, "unit_price": 10.00},
]


# ---------- Auth ----------

def test_ac01_issue_token_returns_opaque_string():
    from ordersvc.auth import issue_token

    tok = issue_token("alice", now=1000.0)
    assert isinstance(tok, str) and len(tok) >= 16
    assert "alice" not in tok  # opaque


def test_ac02_verify_token_returns_user():
    from ordersvc.auth import issue_token, verify_token

    tok = issue_token("bob", ttl_seconds=60, now=1000.0)
    assert verify_token(tok, now=1030.0) == "bob"


def test_ac03_expired_token_rejected():
    from ordersvc import TokenExpired
    from ordersvc.auth import issue_token, verify_token

    tok = issue_token("carol", ttl_seconds=60, now=1000.0)
    with pytest.raises(TokenExpired):
        verify_token(tok, now=1061.0)


def test_ac04_revoked_token_rejected():
    from ordersvc import TokenRevoked
    from ordersvc.auth import issue_token, revoke_token, verify_token

    tok = issue_token("dave", now=1000.0)
    revoke_token(tok)
    with pytest.raises(TokenRevoked):
        verify_token(tok, now=1001.0)


# ---------- Orders ----------

def test_ac05_create_order_pending_with_id():
    from ordersvc.orders import create_order

    o = create_order("alice", ITEMS)
    assert o.id and o.status == "pending" and o.user_id == "alice"
    assert isinstance(o.created_at, float) and o.created_at > 0


def test_ac06_idempotency_key_dedupes():
    from ordersvc.orders import create_order, list_orders

    o1 = create_order("alice", ITEMS, idempotency_key="k1")
    o2 = create_order("alice", ITEMS, idempotency_key="k1")
    assert o1.id == o2.id
    assert len(list_orders(user_id="alice")) == 1


def test_ac07_empty_items_rejected():
    from ordersvc import ValidationError
    from ordersvc.orders import create_order

    with pytest.raises(ValidationError):
        create_order("alice", [])


def test_ac08_total_computed():
    from ordersvc.orders import create_order

    o = create_order("alice", ITEMS)
    assert o.total == 17.00
    o2 = create_order("bob", [{"sku": "C", "qty": 3, "unit_price": 0.10}])
    assert o2.total == 0.30


def test_ac09_get_order_roundtrip():
    from ordersvc.orders import create_order, get_order

    o = create_order("alice", ITEMS)
    assert get_order(o.id).id == o.id


def test_ac10_get_unknown_raises():
    from ordersvc import OrderNotFound
    from ordersvc.orders import get_order

    with pytest.raises(OrderNotFound):
        get_order("nope-404")


def test_ac11_cancel_pending():
    from ordersvc.orders import cancel_order, create_order

    o = create_order("alice", ITEMS)
    assert cancel_order(o.id).status == "cancelled"


def test_ac12_cancel_shipped_forbidden():
    from ordersvc import InvalidTransition
    from ordersvc.auth import issue_token
    from ordersvc.orders import cancel_order, create_order, pay_order, ship_order

    o = create_order("alice", ITEMS)
    pay_order(o.id, issue_token("alice"))
    ship_order(o.id)
    with pytest.raises(InvalidTransition):
        cancel_order(o.id)


def test_ac13_strict_status_machine():
    from ordersvc import InvalidTransition
    from ordersvc.auth import issue_token
    from ordersvc.orders import create_order, get_order, pay_order, ship_order

    o = create_order("alice", ITEMS)
    with pytest.raises(InvalidTransition):
        ship_order(o.id)  # pending -> shipped is illegal
    tok = issue_token("alice")
    assert pay_order(o.id, tok).status == "paid"
    with pytest.raises(InvalidTransition):
        pay_order(o.id, tok)  # paid -> paid is illegal
    assert ship_order(o.id).status == "shipped"
    assert get_order(o.id).status == "shipped"


def test_ac14_list_filters():
    from ordersvc.orders import cancel_order, create_order, list_orders

    a = create_order("alice", ITEMS)
    create_order("bob", ITEMS)
    cancel_order(a.id)
    assert {o.user_id for o in list_orders(user_id="alice")} == {"alice"}
    assert [o.id for o in list_orders(status="cancelled")] == [a.id]
    assert len(list_orders()) == 2


def test_ac15_pay_requires_owner():
    from ordersvc import Forbidden
    from ordersvc.auth import issue_token
    from ordersvc.orders import create_order, pay_order

    o = create_order("alice", ITEMS)
    with pytest.raises(Forbidden):
        pay_order(o.id, issue_token("mallory"))


# ---------- Pagination ----------

def _rows(n):
    # deliberately shuffled input to catch ordering bugs
    rows = [{"id": f"r{i:02d}", "created_at": float(100 + (i % 5)), "v": i} for i in range(n)]
    return rows[::-1]


def test_ac16_limit_respected():
    from ordersvc.pagination import paginate

    page = paginate(_rows(10), limit=4)
    assert len(page.items) == 4


def test_ac17_cursor_walk_no_overlap_no_gap():
    from ordersvc.pagination import paginate

    rows = _rows(11)
    seen, cursor = [], None
    for _ in range(10):
        page = paginate(rows, limit=4, cursor=cursor)
        seen.extend(r["id"] for r in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert sorted(seen) == sorted(r["id"] for r in rows)
    assert len(seen) == len(set(seen))


def test_ac18_stable_ordering():
    from ordersvc.pagination import paginate

    rows = _rows(10)
    page = paginate(rows, limit=10)
    keys = [(r["created_at"], r["id"]) for r in page.items]
    assert keys == sorted(keys)


def test_ac19_exhausted_cursor_is_none():
    from ordersvc.pagination import paginate

    page = paginate(_rows(3), limit=5)
    assert page.next_cursor is None
    rows = _rows(4)
    p1 = paginate(rows, limit=2)
    p2 = paginate(rows, limit=2, cursor=p1.next_cursor)
    assert p2.next_cursor is None


# ---------- Retry ----------

class Flaky:
    def __init__(self, fail_times, exc_factory):
        self.calls = 0
        self.fail_times = fail_times
        self.exc_factory = exc_factory

    def __call__(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc_factory()
        return "ok"


def test_ac20_retries_on_transient():
    from ordersvc import TransientError
    from ordersvc.retry import retry_with_backoff

    f = Flaky(2, TransientError)
    assert retry_with_backoff(f, max_attempts=3, sleep=lambda s: None) == "ok"
    assert f.calls == 3


def test_ac21_raises_after_exhaustion():
    from ordersvc import TransientError
    from ordersvc.retry import retry_with_backoff

    f = Flaky(99, TransientError)
    with pytest.raises(TransientError):
        retry_with_backoff(f, max_attempts=3, sleep=lambda s: None)
    assert f.calls == 3


def test_ac22_non_transient_propagates_immediately():
    from ordersvc.retry import retry_with_backoff

    f = Flaky(99, ValueError)
    with pytest.raises(ValueError):
        retry_with_backoff(f, max_attempts=5, sleep=lambda s: None)
    assert f.calls == 1


def test_ac23_exponential_backoff_schedule():
    from ordersvc import TransientError
    from ordersvc.retry import retry_with_backoff

    delays = []
    f = Flaky(3, TransientError)
    retry_with_backoff(f, max_attempts=4, base_delay=0.1, sleep=delays.append)
    assert delays == pytest.approx([0.1, 0.2, 0.4])


# ---------- Store ----------

def test_ac24_store_roundtrip():
    from ordersvc.store import MemoryStore

    s = MemoryStore()
    s.put("k", {"v": 1})
    assert s.get("k") == {"v": 1}
    with pytest.raises(KeyError):
        s.get("missing")


def test_ac25_store_delete():
    from ordersvc.store import MemoryStore

    s = MemoryStore()
    s.put("k", 1)
    s.delete("k")
    with pytest.raises(KeyError):
        s.get("k")
