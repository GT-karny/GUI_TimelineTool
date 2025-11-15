import json
from dataclasses import fields
from pathlib import Path
from typing import Iterable, List

from ..core.timeline import Timeline, Track, Keyframe, InterpMode, Handle


_HANDLE_FIELD_NAMES = tuple(f.name for f in fields(Handle))


def _serialize_handle(handle: Handle | None) -> dict | None:
    if handle is None:
        return None
    return {name: getattr(handle, name) for name in _HANDLE_FIELD_NAMES}


def _deserialize_handle(data, *, default_t: float, default_v: float) -> Handle | None:
    if data is None:
        return None
    if isinstance(data, Handle):
        return data.copy()
    if isinstance(data, dict):
        return Handle.from_mapping(data, default_t=default_t, default_v=default_v)
    if isinstance(data, (list, tuple)) and len(data) == 2:
        return Handle(float(data[0]), float(data[1]))
    return None


def _coerce_key_payload(key_payload: dict) -> dict:
    payload = dict(key_payload)
    default_t = float(payload.get("t", 0.0))
    default_v = float(payload.get("v", 0.0))
    if "handle_in" in payload:
        payload["handle_in"] = _deserialize_handle(
            payload.get("handle_in"), default_t=default_t, default_v=default_v
        )
    if "handle_out" in payload:
        payload["handle_out"] = _deserialize_handle(
            payload.get("handle_out"), default_t=default_t, default_v=default_v
        )
    return payload


def _serialize_track(track: Track) -> dict:
    return {
        "id": track.track_id,
        "name": track.name,
        "interp": track.interp.value,
        "keys": [
            {
                "t": k.t,
                "v": k.v,
                "handle_in": _serialize_handle(k.handle_in),
                "handle_out": _serialize_handle(k.handle_out),
            }
            for k in track.keys
        ],
    }


def save_project(path: str | Path, tl: Timeline, sample_rate_hz: float) -> None:
    tracks_payload = [_serialize_track(track) for track in tl.tracks]
    obj = {
        "duration_s": tl.duration_s,
        "sample_rate_hz": float(sample_rate_hz),
        "tracks": tracks_payload,
    }
    if tracks_payload:
        legacy_track = tracks_payload[0].copy()
        legacy_track.pop("id", None)
        obj["track"] = legacy_track
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_tracks(data: Iterable[dict]) -> List[Track]:
    tracks: List[Track] = []
    for idx, track_obj in enumerate(data):
        name = track_obj.get("name") or f"Track {idx + 1}"
        interp_raw = track_obj.get("interp", InterpMode.CUBIC.value)
        try:
            interp = InterpMode(interp_raw)
        except ValueError:
            interp = InterpMode.CUBIC
        keys = [Keyframe(**_coerce_key_payload(kv)) for kv in track_obj.get("keys", [])]
        if not keys:
            keys = [Keyframe(0.0, 0.0)]
        track = Track(
            name=name,
            interp=interp,
            keys=keys,
            track_id=track_obj.get("id"),
        )
        track.clamp_times()
        tracks.append(track)
    if not tracks:
        tracks.append(Track())
    return tracks


def load_project(path: str | Path) -> tuple[Timeline, float]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    sample_rate = float(obj.get("sample_rate_hz", 90.0))

    tracks_data = obj.get("tracks")
    if not tracks_data and "track" in obj:
        single = obj["track"]
        if isinstance(single, dict):
            tracks_data = [single]

    tracks = _load_tracks(tracks_data or [])
    timeline = Timeline(duration_s=float(obj.get("duration_s", 10.0)), tracks=tracks)
    return timeline, sample_rate
