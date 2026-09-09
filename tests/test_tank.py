from dungeon_rpc.parser.tank import TankError


def test_tank_error_type():
    assert issubclass(TankError, Exception)
