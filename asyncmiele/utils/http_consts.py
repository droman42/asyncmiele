"""Shared HTTP header constants used across asyncmiele.

Keeping the strings in **one** place guarantees future version bumps (e.g.
API version update) only need a single change.
"""

ACCEPT_HEADER: str = "application/vnd.miele.v1+json"
"""Default *Accept:* value used by all requests."""

USER_AGENT: str = "Miele@mobile 2.3.3 Android"
"""User-agent string copied from the original Android application."""

CONTENT_TYPE_JSON: str = "application/vnd.miele.v1+json; charset=utf-8"
"""Content-Type for encrypted JSON bodies (PUT).""" 