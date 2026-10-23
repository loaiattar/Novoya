from enum import StrEnum


class Role(StrEnum):
    """What a user may do. Stored on the user; only an admin changes it."""

    CLIENT = "client"
    AGENT = "agent"  # agency staff: quote queue, prices, partners and offers
    ADMIN = "admin"  # everything, plus managing clients and agents
    SUPER_ADMIN = "super_admin"  # an admin who may also act on admins and super admins


# The roles that only a super admin gives, takes or acts on.
ADMIN_ROLES = frozenset({Role.ADMIN, Role.SUPER_ADMIN})
