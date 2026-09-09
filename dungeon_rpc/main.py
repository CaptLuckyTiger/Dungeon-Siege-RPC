import argparse
from pathlib import Path
from typing import Dict, Optional

from .models import SaveInfo
from .parser.info_gas import parse_save
from .parser.tank import TankError
from .save_detector import discover_save_folder, iter_save_files, newest_save
from .save_monitor import print_save_info, run_monitor


def test_single_save(path: Path) -> int:
    if not path.exists():
        print(f"[ERRO] Save não encontrado: {path}")
        return 1

    try:
        info = parse_save(path)
    except (OSError, TankError) as exc:
        print(f"[ERRO] Não foi possível ler o save: {exc}")
        return 1

    print("==========================================")
    print(" Dungeon Siege RPC - Teste de Save")
    print("==========================================")
    print_save_info(info, "TESTE")
    print(f"Nome do save: {info.save_name}")
    print(f"Mapa: {info.map_name or 'desconhecido'}")
    print(f"Mapa exibido: {info.map_screen_name or 'desconhecido'}")
    print(f"Autosave: {info.is_auto_save}")
    print(f"Quicksave: {info.is_quick_save}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dungeon Siege Rich Presence baseado em region do info.gas"
    )
    parser.add_argument(
        "--test-save",
        type=Path,
        help="Lê um .dssave e imprime as informações detectadas, sem conectar ao Discord.",
    )
    parser.add_argument(
        "--save-folder",
        type=Path,
        help=(
            "Sobrescreve a descoberta automática da pasta de saves. "
            "Use apenas se sua instalação estiver fora do local padrão."
        ),
    )
    args = parser.parse_args()

    if args.test_save:
        return test_single_save(args.test_save)

    print("==========================================")
    print(" Dungeon Siege RPC - Region Detector")
    print("==========================================")

    save_folder = discover_save_folder(args.save_folder)
    if save_folder is None:
        print("[ERRO] Não encontrei a pasta de saves do Dungeon Siege.")
        print("       Local padrão: <Documents>\\Dungeon Siege\\Save")
        print("       Para uma instalação incomum, use --save-folder.")
        return 1

    paths = iter_save_files(save_folder)
    if not paths:
        print(f"[ERRO] Nenhum save encontrado em: {save_folder}")
        return 1

    save_infos: Dict[str, SaveInfo] = {}
    for path in paths:
        try:
            info = parse_save(path)
            save_infos[str(path)] = info
        except (OSError, TankError) as exc:
            print(f"[AVISO] Não foi possível analisar {path.name}: {exc}")

    if not save_infos:
        print("[ERRO] Nenhum save pôde ser analisado.")
        return 1

    from .save_detector import snapshot_save_access_times, most_recently_accessed_save

    initial_access = snapshot_save_access_times(save_folder)
    initial_candidate = most_recently_accessed_save(initial_access)

    current_info: Optional[SaveInfo] = None
    if initial_candidate is not None:
        current_info = save_infos.get(str(initial_candidate))

    if current_info is None:
        fallback = newest_save(save_folder)
        if fallback is not None:
            current_info = save_infos.get(str(fallback))

    if current_info is None:
        current_info = next(iter(save_infos.values()))

    print(f"[PASTA] {save_folder}")
    print_save_info(current_info, "INICIAL")

    return run_monitor(save_folder, current_info, save_infos)


if __name__ == "__main__":
    raise SystemExit(main())
