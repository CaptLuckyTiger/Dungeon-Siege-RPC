from pathlib import Path

from dungeon_rpc.parser.info_gas import parse_save


def test_parse_save_smoke():
    # Smoke test placeholder for a real save fixture.
    assert Path("dungeon_rpc").exists()
    assert callable(parse_save)
