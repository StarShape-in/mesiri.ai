"""Redis-backed "waiting for a project-setup offer answer" hint.

After a Project or Site is created via WhatsApp, Mesiri offers the natural
next step as tappable Yes/Skip buttons (see channel/replies.py's
render_project_site_offer/render_project_member_offer) -- a fresh Project
has no site yet, and a fresh Site has no team yet. This remembers WHICH
project the offer was about and WHICH step it offered, so the button tap
(handled in runtime/message_journey.py, before any other fast path) knows
what to start without re-asking.

Mirrors interactions/team_photo_hint.py exactly, including its "Redis is a
hint, never authoritative" stance and pop-once contract: a missing or
expired hint just means the tap is treated as stale (see
render_setup_offer_expired_reply) -- never a broken journey. The offer is
also never load-bearing for the underlying record: the Project/Site is
already saved by the time this offer is even shown.

Key layout (the client prepends the ``mesiri`` namespace):

    mesiri:user:{user_id}:project_setup_offer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

#: Short: this is a reply to a question just asked, not a physical errand
#: like the team-photo hint -- if they haven't answered in 10 minutes they've
#: moved on, and a stale tap should read as expired rather than resurrect an
#: old offer against whatever they're doing now.
_DEFAULT_TTL_SECONDS = 600  # 10 minutes

SetupStage = Literal["site", "member"]


@dataclass(frozen=True, slots=True)
class ProjectSetupOffer:
    stage: SetupStage
    project_id: str


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class ProjectSetupOfferStore:
    """One pending "which project, and which setup step" offer per user,
    consumed at most once."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    @staticmethod
    def _key(user_id: str) -> str:
        return f"user:{user_id}:project_setup_offer"

    async def set_offer(
        self,
        *,
        user_id: str,
        stage: SetupStage,
        project_id: str,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        await self._redis.set_json(
            self._key(user_id),
            {"stage": stage, "project_id": project_id},
            ttl_seconds=ttl_seconds,
        )

    async def pop_offer(self, *, user_id: str) -> ProjectSetupOffer | None:
        """Read the pending offer and clear it in the same call.

        Pop-once matters here: without it, tapping the same stale button
        twice (or a delayed double-delivery) would start the follow-up
        workflow a second time.
        """
        key = self._key(user_id)
        raw = await self._redis.get_json(key)
        if not raw or not raw.get("project_id") or not raw.get("stage"):
            return None
        await self._redis.set_json(key, {}, ttl_seconds=1)
        return ProjectSetupOffer(stage=raw["stage"], project_id=str(raw["project_id"]))

    async def clear(self, *, user_id: str) -> None:
        """Drop the offer without acting on it -- used when the user taps
        Skip, so a stray later tap on the same (already-expired) button
        cannot resurrect it."""
        await self._redis.set_json(self._key(user_id), {}, ttl_seconds=1)
