from __future__ import annotations

from gryps.core.frame_store import FrameStore


class TestFrameStore:
    def test_store_and_get_frame(self) -> None:
        store = FrameStore()
        frame = object()
        store.store("mem://cam_01/0", frame)
        assert store.get("mem://cam_01/0") is frame

    def test_get_missing_ref_returns_none(self) -> None:
        store = FrameStore()
        assert store.get("mem://nonexistent") is None

    def test_clear_removes_all_frames(self) -> None:
        store = FrameStore()
        store.store("mem://cam_01/0", object())
        store.store("mem://cam_01/1", object())
        store.clear()
        assert store.get("mem://cam_01/0") is None
        assert store.get("mem://cam_01/1") is None

    def test_overwrite_ref_replaces_frame(self) -> None:
        store = FrameStore()
        frame_a = object()
        frame_b = object()
        store.store("mem://cam_01/0", frame_a)
        store.store("mem://cam_01/0", frame_b)
        assert store.get("mem://cam_01/0") is frame_b

    def test_empty_after_init(self) -> None:
        store = FrameStore()
        assert len(store) == 0

    def test_len_reflects_stored_frames(self) -> None:
        store = FrameStore()
        store.store("a", object())
        store.store("b", object())
        assert len(store) == 2

    def test_len_after_clear(self) -> None:
        store = FrameStore()
        store.store("a", object())
        store.clear()
        assert len(store) == 0

    def test_get_returns_none_after_clear(self) -> None:
        store = FrameStore()
        store.store("a", object())
        store.clear()
        assert store.get("a") is None
