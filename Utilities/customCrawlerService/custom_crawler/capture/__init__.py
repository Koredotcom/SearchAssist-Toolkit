"""Interactive Chrome profile capture (VNC) shared by the HTTP API and CLI warmup."""

from .persist import on_target_site, page_is_cleared, persist_profile, profile_is_warmed, snapshot

__all__ = [
    "on_target_site",
    "page_is_cleared",
    "persist_profile",
    "profile_is_warmed",
    "snapshot",
]
