# interaction/clipboard.py
"""Clipboard management for keyframe values."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.timeline import TrackType


@dataclass
class KeyframeClipboard:
    """Clipboard data for keyframe values."""
    
    value: float  # For scalar tracks
    vx: Optional[float] = None  # For vector2 tracks
    vy: Optional[float] = None  # For vector2 tracks
    track_type: TrackType = TrackType.SCALAR
    
    @classmethod
    def from_keyframe(cls, key, track_type: TrackType) -> "KeyframeClipboard":
        """Create clipboard data from a keyframe."""
        if track_type == TrackType.VECTOR2:
            vx = key.vx if key.vx is not None else 0.0
            vy = key.vy if key.vy is not None else 0.0
            return cls(value=key.v, vx=vx, vy=vy, track_type=TrackType.VECTOR2)
        else:
            return cls(value=key.v, track_type=TrackType.SCALAR)
    
    def to_keyframe_value(self) -> tuple[float, Optional[float], Optional[float]]:
        """Get keyframe values as tuple (v, vx, vy)."""
        if self.track_type == TrackType.VECTOR2:
            return (self.value, self.vx, self.vy)
        else:
            return (self.value, None, None)


# グローバルクリップボード（アプリケーション全体で共有）
_clipboard: Optional[KeyframeClipboard] = None


def copy_keyframe(key, track_type: TrackType) -> None:
    """Copy keyframe value to clipboard."""
    global _clipboard
    _clipboard = KeyframeClipboard.from_keyframe(key, track_type)


def get_clipboard() -> Optional[KeyframeClipboard]:
    """Get current clipboard data."""
    return _clipboard


def clear_clipboard() -> None:
    """Clear clipboard data."""
    global _clipboard
    _clipboard = None

