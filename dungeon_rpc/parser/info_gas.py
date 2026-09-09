import re
from pathlib import Path
from typing import Optional

from ..models import SaveInfo
from ..regions import resolve_region_name
from .tank import TankError, TankReader


def _gas_value(text: str, key: str) -> Optional[str]:
    pattern = rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*;\s*$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None

    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]

    return value


def _gas_bool(text: str, key: str) -> bool:
    value = _gas_value(text, key)
    if value is None:
        return False
    return value.casefold() == "true"


def _parse_elapsed_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        if len(parts) == 2:
            m, s = map(float, parts)
            return m * 60 + s
        return float(value)
    except ValueError:
        return None


def parse_save(path: Path) -> SaveInfo:
    raw = TankReader(path).extract("info.gas")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    region_id = _gas_value(text, "region")
    if not region_id:
        raise TankError("info.gas não contém o campo 'region'")

    region_id = region_id.strip().lower()
    region_name = resolve_region_name(region_id)
    if region_name.startswith("Unknown"):
        print(
            f"[AVISO] ID de região desconhecido: {region_id}. "
            "Adicione-o a REGION_NAMES quando souber o nome."
        )

    elapsed_text = _gas_value(text, "time_elapsed_text")
    map_name = _gas_value(text, "map_name")
    map_screen_name = _gas_value(text, "map_screen_name")
    screen_name = _gas_value(text, "screen_name")

    return SaveInfo(
        path=path,
        region_id=region_id,
        region_name=region_name,
        save_name=screen_name or path.stem,
        screen_name=screen_name,
        elapsed_text=elapsed_text,
        elapsed_seconds=_parse_elapsed_seconds(elapsed_text),
        is_auto_save=_gas_bool(text, "is_auto_save"),
        is_quick_save=_gas_bool(text, "is_quick_save"),
        map_name=map_name,
        map_screen_name=map_screen_name,
    )
