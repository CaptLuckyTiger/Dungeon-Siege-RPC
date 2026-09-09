import ctypes
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import DEFAULT_GAME_SAVE_SUBPATH
from .models import SaveInfo
from .parser.info_gas import parse_save
from .parser.tank import TankError


def iter_save_files(save_folder: Path) -> list[Path]:
    if not save_folder.exists():
        return []

    extensions = {".dssave", ".dsasave", ".dsg"}
    result = []

    for path in save_folder.rglob("*"):
        if path.is_file() and path.suffix.casefold() in extensions:
            result.append(path)

    return result


def save_signature(path: Path) -> Tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def snapshot_saves(save_folder: Path) -> Dict[str, Tuple[int, int]]:
    snapshot: Dict[str, Tuple[int, int]] = {}
    for path in iter_save_files(save_folder):
        try:
            snapshot[str(path)] = save_signature(path)
        except OSError:
            pass
    return snapshot


def newest_save(save_folder: Path) -> Optional[Path]:
    saves = iter_save_files(save_folder)
    if not saves:
        return None

    try:
        return max(saves, key=lambda p: p.stat().st_mtime_ns)
    except OSError:
        return None


FOLDERID_DOCUMENTS = bytes.fromhex("FDD39AD0238F46AFADB46C85480369C7")


def get_windows_documents_folder() -> Optional[Path]:
    """Retorna a pasta Documents configurada para o usuário atual."""
    if os.name != "nt":
        return None

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    guid_bytes = FOLDERID_DOCUMENTS
    guid = GUID.from_buffer_copy(guid_bytes)

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32

    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long

    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None

    path_ptr = ctypes.c_wchar_p()
    hr = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(path_ptr),
    )

    if hr != 0 or not path_ptr.value:
        return None

    try:
        return Path(path_ptr.value)
    finally:
        ole32.CoTaskMemFree(ctypes.cast(path_ptr, ctypes.c_void_p))


def candidate_save_folders() -> list[Path]:
    """Retorna caminhos candidatos sem exigir configuração manual."""
    candidates: list[Path] = []

    documents = get_windows_documents_folder()
    if documents:
        candidates.append(documents / DEFAULT_GAME_SAVE_SUBPATH)

    home = Path.home()
    candidates.extend(
        [
            home / "Documents" / DEFAULT_GAME_SAVE_SUBPATH,
            home / "My Documents" / DEFAULT_GAME_SAVE_SUBPATH,
            home / "Documentos" / DEFAULT_GAME_SAVE_SUBPATH,
            home / "OneDrive" / "Documents" / DEFAULT_GAME_SAVE_SUBPATH,
            home / "OneDrive" / "Documentos" / DEFAULT_GAME_SAVE_SUBPATH,
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()

    for path in candidates:
        key = os.path.normcase(os.path.normpath(str(path)))
        if key not in seen:
            seen.add(key)
            unique.append(path)

    return unique


def discover_save_folder(explicit: Optional[Path] = None) -> Optional[Path]:
    """Descobre automaticamente a pasta de saves do Dungeon Siege."""
    if explicit:
        return explicit.expanduser()

    candidates = candidate_save_folders()
    extensions = {".dssave", ".dsasave", ".dsg"}

    for path in candidates:
        if not path.is_dir():
            continue
        try:
            if any(
                p.is_file() and p.suffix.casefold() in extensions
                for p in path.rglob("*")
            ):
                return path
        except OSError:
            continue

    for path in candidates:
        if path.is_dir():
            return path

    return None


def save_access_signature(path: Path) -> int:
    return path.stat().st_atime_ns


def snapshot_save_access_times(save_folder: Path) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for path in iter_save_files(save_folder):
        try:
            result[str(path)] = save_access_signature(path)
        except OSError:
            pass
    return result


def most_recently_accessed_save(access_times: Dict[str, int]) -> Optional[Path]:
    if not access_times:
        return None

    path_str = max(access_times, key=access_times.get)
    return Path(path_str)


def detect_recently_accessed_save(
    save_folder: Path,
    baseline: Dict[str, int],
    infos: Dict[str, SaveInfo],
) -> Optional[Tuple[SaveInfo, Dict[str, int]]]:
    current = snapshot_save_access_times(save_folder)
    changed: list[Tuple[str, int]] = []

    for path_str, access_time in current.items():
        old = baseline.get(path_str)
        if old is not None and access_time > old:
            changed.append((path_str, access_time))

    if not changed:
        return None

    changed.sort(key=lambda item: item[1], reverse=True)
    path_str, _ = changed[0]
    path = Path(path_str)

    try:
        info = infos.get(path_str)
        if info is None:
            info = parse_save(path)
            infos[path_str] = info
    except (OSError, TankError) as exc:
        print(f"[ACESSO] Não foi possível analisar {path.name}: {exc}")
        return None

    return info, current


def query_last_access_mode() -> Optional[str]:
    """Consulta o estado do Last Access Time sem alterar configuração do Windows."""
    if os.name != "nt":
        return None

    try:
        output = subprocess.check_output(
            ["fsutil", "behavior", "query", "disablelastaccess"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    match = re.search(r"disablelastaccess\s*=\s*(\d+)", output.casefold())
    if not match:
        match = re.search(r"disablelastaccess[^0-9]*(\d+)", output.casefold())
    if not match:
        return None

    value = int(match.group(1))
    if value in (0, 2):
        return "enabled"
    if value in (1, 3):
        return "disabled"
    return None
