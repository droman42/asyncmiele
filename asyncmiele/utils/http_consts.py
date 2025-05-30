"""Shared HTTP header constants used across asyncmiele.

These values are aligned with MieleRESTServer reference implementation.
"""

# Accept header value - matches MieleRESTServer exactly
ACCEPT_HEADER = "application/vnd.miele.v1+json"
"""Default *Accept:* value used by all requests."""

# User-Agent header - matches MieleRESTServer exactly  
USER_AGENT = "Miele@mobile 2.3.3 iOS"
"""User-Agent string that matches MieleRESTServer implementation."""

# Content-Type header for PUT requests - matches MieleRESTServer exactly
# Note: The spaces around '/' are intentional and match the reference implementation
CONTENT_TYPE_JSON = "application / vnd.miele.v1 + json; charset = utf - 8"
"""Content-Type for encrypted JSON bodies (PUT) - matches MieleRESTServer exactly.""" 