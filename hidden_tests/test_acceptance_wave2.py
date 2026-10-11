"""Hidden wave 2: refund scope change (AC-26..AC-32). Graded from sprint 1 on."""
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


ITEMS = [{"sku": "A", "qty": 2, "unit_price": 3.50}]


def _shipped(user="alice"):
    from ordersvc.auth import issue_token
    from ordersvc.orders import create_order, pay_order, ship_order

    o = create_order(user, ITEMS)
    tok = issue_token(user)
    pay_order(o.id, tok)
    ship_order(o.id)
    return o, tok


def test_ac26_refund_shipped():
    from ordersvc.orders import refund_order

    o, tok = _shipped()
    assert refund_order(o.id, tok).status == "refunded"


def test_ac27_refund_requires_shipped():
    from ordersvc import InvalidTransition
    from ordersvc.auth import issue_token
    from ordersvc.orders import create_order, refund_order

    o = create_order("alice", ITEMS)
    with pytest.raises(InvalidTransition):
        refund_order(o.id, issue_token("alice"))


def test_ac28_refund_requires_owner():
    from ordersvc import Forbidden
    from ordersvc.auth import issue_token
    from ordersvc.orders import refund_order

    o, _ = _shipped("alice")
    with pytest.raises(Forbidden):
        refund_order(o.id, issue_token("mallory"))


def test_ac29_refund_amount():
    from ordersvc.orders import create_order, get_order, refund_order

    o, tok = _shipped()
    assert get_order(o.id).refund_amount == 0.0
    refund_order(o.id, tok)
    assert get_order(o.id).refund_amount == 7.00


def test_ac30_list_refunded():
    from ordersvc.orders import list_orders, refund_order

    a, tok = _shipped("alice")
    _shipped("alice")
    refund_order(a.id, tok)
    assert [o.id for o in list_orders(status="refunded")] == [a.id]


def test_ac31_cancel_refunded_forbidden():
    from ordersvc import InvalidTransition
    from ordersvc.orders import cancel_order, refund_order

    o, tok = _shipped()
    refund_order(o.id, tok)
    with pytest.raises(InvalidTransition):
        cancel_order(o.id)


def test_ac32_double_refund_forbidden():
    from ordersvc import InvalidTransition
    from ordersvc.orders import refund_order

    o, tok = _shipped()
    refund_order(o.id, tok)
    with pytest.raises(InvalidTransition):
        refund_order(o.id, tok)
