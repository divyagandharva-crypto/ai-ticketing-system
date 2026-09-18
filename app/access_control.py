"""
Access-control helpers for ticket visibility.

Design: every ticket carries an access_level, every user carries a
clearance_level, both drawn from the same ordered scale. A user may see
a ticket only if their clearance rank is >= the ticket's access rank.

Fail-closed by design: an unrecognized level value (a typo, a future
migration that adds a level this code doesn't know about yet, a bad
manual DB write) is never treated as permissive. It denies access
rather than guessing.

This module is deliberately the *only* place the ordering and the
comparison logic live, so the same rule can't drift between endpoints.
"""

from typing import List

ACCESS_LEVELS = ["standard", "elevated", "restricted"]


def user_can_access(user_clearance: str, ticket_access: str) -> bool:
    """Can a user with this clearance see a ticket at this access level?"""
    if user_clearance not in ACCESS_LEVELS or ticket_access not in ACCESS_LEVELS:
        return False
    return ACCESS_LEVELS.index(user_clearance) >= ACCESS_LEVELS.index(ticket_access)


def allowed_levels_for(user_clearance: str) -> List[str]:
    """
    The set of access_level values a user is cleared to see, for use
    directly in a WHERE ... IN (...) filter. Used by any endpoint that
    retrieves or ranks a *set* of tickets, so that a ticket the user
    isn't cleared for is excluded from the query itself — never
    fetched, never ranked, never handed to a model call.
    """
    if user_clearance not in ACCESS_LEVELS:
        return []
    return ACCESS_LEVELS[: ACCESS_LEVELS.index(user_clearance) + 1]