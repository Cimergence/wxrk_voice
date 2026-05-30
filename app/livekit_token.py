"""Mint a LiveKit join token for the browser mic client.

Lazy-imports livekit.api so the API boots even when the package isn't installed
(e.g. the slim test env). With no LiveKit creds configured it returns a clearly
marked dev placeholder so /sessions still satisfies the contract shape.
"""
from __future__ import annotations

from app.config import Settings


def mint_join_token(settings: Settings, room: str, identity: str) -> tuple[str, str]:
    """Return (join_token, ws_url). Falls back to a dev placeholder offline."""
    if not (settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_url):
        return (f"dev-token-{room}", settings.livekit_url)
    try:
        from livekit import api  # type: ignore
    except Exception:
        return (f"dev-token-{room}", settings.livekit_url)

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return (token, settings.livekit_url)
