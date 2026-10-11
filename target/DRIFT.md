## Scope change — Refunds (mandate v2, injected at sprint 1)

The stakeholder requires refund support on top of the existing order lifecycle.
All original acceptance criteria (AC-01..AC-25) must KEEP passing.

- **AC-26** `refund_order(order_id, token) -> Order` on a `shipped` order sets
  status `refunded`.
- **AC-27** Refunding an order that is not `shipped` raises `InvalidTransition`.
- **AC-28** `refund_order` verifies the token and requires the token's user to be
  the order's owner, else raises `Forbidden`.
- **AC-29** A refunded order exposes `refund_amount` equal to `Order.total` at
  the moment of refund; non-refunded orders expose `refund_amount == 0.0`.
- **AC-30** `list_orders(status="refunded")` returns exactly the refunded orders.
- **AC-31** Cancelling a `refunded` order raises `InvalidTransition`.
- **AC-32** Refunding twice raises `InvalidTransition` (refunds are not repeatable).
