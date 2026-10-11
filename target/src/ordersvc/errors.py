"""Exception taxonomy. Do not rename — the spec references these names."""


class ValidationError(Exception):
    pass


class OrderNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


class Forbidden(Exception):
    pass


class TokenExpired(Exception):
    pass


class TokenRevoked(Exception):
    pass


class TransientError(Exception):
    pass
