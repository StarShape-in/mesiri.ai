"""Event bus (#14) -- multi-consumer outbox fan-out.

See interface.py (the EventConsumer contract) and dispatcher.py
(drain_for_consumer, the generic per-consumer read/checkpoint loop).
timeline_projector.py is NOT a consumer of this bus -- it predates it and
keeps using outbox_events.published_at directly; this module is for every
consumer after the first (#9 Notifications, #17 Search Index, ...).
"""

from __future__ import annotations

from .dispatcher import DrainResult, drain_for_consumer
from .interface import EventConsumer

__all__ = ["EventConsumer", "DrainResult", "drain_for_consumer"]
