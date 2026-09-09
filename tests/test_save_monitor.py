from pathlib import Path

from dungeon_rpc.models import SaveInfo
from dungeon_rpc.save_monitor import run_monitor


class FakeRPC:
    def __init__(self):
        self.update_calls = 0

    def connect(self):
        return None

    def update(self, **kwargs):
        self.update_calls += 1

    def close(self):
        return None


def test_run_monitor_does_not_update_rpc_before_any_save_event(monkeypatch, tmp_path):
    fake_rpc = FakeRPC()

    monkeypatch.setattr(
        "dungeon_rpc.save_monitor.DiscordRPC",
        lambda *args, **kwargs: fake_rpc,
    )

    def fake_snapshot_saves(save_folder):
        return {}

    monkeypatch.setattr(
        "dungeon_rpc.save_monitor.snapshot_saves",
        fake_snapshot_saves,
    )

    monkeypatch.setattr(
        "dungeon_rpc.save_monitor.snapshot_save_access_times",
        lambda save_folder: {},
    )

    monkeypatch.setattr(
        "dungeon_rpc.save_monitor.query_last_access_mode",
        lambda: "enabled",
    )

    monkeypatch.setattr(
        "dungeon_rpc.save_monitor.detect_recently_accessed_save",
        lambda save_folder, baseline, save_infos: None,
    )

    def fake_sleep(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("dungeon_rpc.save_monitor.time.sleep", fake_sleep)

    initial_info = SaveInfo(
        path=tmp_path / "save.dssave",
        region_id="fh_r1",
        region_name="Farmlands",
        save_name="save1",
        screen_name=None,
        elapsed_text=None,
        elapsed_seconds=None,
        is_auto_save=False,
        is_quick_save=False,
        map_name=None,
        map_screen_name=None,
    )

    result = run_monitor(tmp_path, initial_info, {})

    assert result == 0
    assert fake_rpc.update_calls == 0
