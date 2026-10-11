"""ordersvc — implement per SPEC.md. Graded by a hidden acceptance suite."""
from ordersvc.errors import (  # noqa: F401
    Forbidden,
    InvalidTransition,
    OrderNotFound,
    TokenExpired,
    TokenRevoked,
    TransientError,
    ValidationError,
)
