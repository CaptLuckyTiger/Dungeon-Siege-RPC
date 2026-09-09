from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SaveInfo:
    path: Path
    region_id: str
    region_name: str
    save_name: str
    screen_name: Optional[str]
    elapsed_text: Optional[str]
    elapsed_seconds: Optional[float]
    is_auto_save: bool
    is_quick_save: bool
    map_name: Optional[str]
    map_screen_name: Optional[str]
