import time
from pathlib import Path
from typing import Dict

from .config import POLL_INTERVAL, LARGE_IMAGE, LARGE_TEXT
from .integrations.discord_rpc import DiscordRPC
from .models import SaveInfo
from .parser.info_gas import parse_save
from .parser.tank import TankError
from .save_detector import (
    detect_recently_accessed_save,
    query_last_access_mode,
    snapshot_save_access_times,
    snapshot_saves,
)


def update_rpc(rpc: DiscordRPC, info: SaveInfo, region_start_time: int) -> None:
    """Atualiza o Rich Presence. O timestamp representa o tempo na região."""
    rpc.update(
        details=f"Aventurando por {info.region_name}",
        state=info.map_screen_name or "Kingdom of Ehb",
        large_image=LARGE_IMAGE,
        large_text=LARGE_TEXT,
        start=region_start_time,
    )


def print_save_info(info: SaveInfo, prefix: str = "SAVE") -> None:
    kind = "autosave" if info.is_auto_save else "save"
    if info.is_quick_save:
        kind = "quicksave"

    print(
        f"[{prefix}] {info.region_name} "
        f"(region={info.region_id}, tipo={kind}) "
        f"-> {info.path.name}"
    )

    if info.elapsed_text:
        print(f"        Tempo de jogo: {info.elapsed_text}")


def run_monitor(save_folder: Path, initial_info: SaveInfo, save_infos: Dict[str, SaveInfo]) -> int:
    try:
        rpc = DiscordRPC()
        rpc.connect()
        print("[DISCORD] Conectado com sucesso!")
    except Exception as exc:
        print(f"[DISCORD ERRO] {exc}")
        return 1

    region_start_time = int(time.time())
    current_info = initial_info

    try:
        print(f"[RPC] Estado inicial carregado: {initial_info.region_name} (sem atualizar o Discord)")

        previous = snapshot_saves(save_folder)
        access_baseline = snapshot_save_access_times(save_folder)

        access_mode = query_last_access_mode()
        if access_mode == "enabled":
            print("[ACESSO] Last Access Time do NTFS está habilitado.")
        elif access_mode == "disabled":
            print("[ACESSO] Last Access Time do NTFS está DESABILITADO.")
            print("         Carregar um save antigo pode não gerar nenhum sinal observável no arquivo.")
        else:
            print("[ACESSO] Não foi possível determinar o estado do Last Access Time.")

        print("\n[MONITORANDO] Saves + acesso aos arquivos... (Ctrl+C para sair)")
        print("[RPC] O cronômetro conta o tempo desde a entrada na região.")
        print("[ACESSO] O programa não usa mais strings da memória do Dungeon Siege para escolher o save.")

        while True:
            time.sleep(POLL_INTERVAL)

            current_snapshot = snapshot_saves(save_folder)
            changed_paths = []

            for path_str, signature in current_snapshot.items():
                old_signature = previous.get(path_str)
                if old_signature != signature:
                    changed_paths.append(Path(path_str))

            changed_paths.sort(
                key=lambda p: p.stat().st_mtime_ns if p.exists() else 0,
                reverse=True,
            )

            for path in changed_paths:
                try:
                    info = parse_save(path)
                except (OSError, TankError) as exc:
                    print(f"[AGUARDANDO] {path.name}: {exc}")
                    continue

                path_str = str(path)
                save_infos[path_str] = info

                old_region = current_info.region_name
                old_region_id = current_info.region_id
                old_path = str(current_info.path)
                current_info = info

                if current_info.region_id != old_region_id:
                    region_start_time = int(time.time())
                    update_rpc(rpc, current_info, region_start_time)
                    print(
                        f"\n[NOVA REGIÃO] {old_region} -> {current_info.region_name}"
                        f" (region={current_info.region_id})"
                    )
                else:
                    print(
                        f"\n[SAVE ATUALIZADO] {current_info.save_name}"
                        f" | permanece em {current_info.region_name}"
                    )

                if old_path != str(current_info.path):
                    print(f"        Arquivo ativo: {current_info.path.name}")

            previous = {key: value for key, value in current_snapshot.items()}

            detected_access = detect_recently_accessed_save(
                save_folder, access_baseline, save_infos
            )

            if detected_access is not None:
                detected, access_baseline = detected_access

                if (
                    str(detected.path) != str(current_info.path)
                    or detected.region_id != current_info.region_id
                ):
                    old_region = current_info.region_name
                    old_region_id = current_info.region_id
                    current_info = detected

                    if current_info.region_id != old_region_id:
                        region_start_time = int(time.time())
                        update_rpc(rpc, current_info, region_start_time)
                        arrow = f"{old_region} -> {current_info.region_name}"
                    else:
                        arrow = f"permanece em {current_info.region_name}"

                    print(
                        f"\n[SAVE CARREGADO] {current_info.save_name}"
                        f" | {arrow}"
                        f" (region={current_info.region_id})"
                    )
                    print_save_info(current_info, "ATIVO")
            else:
                access_baseline = snapshot_save_access_times(save_folder)

    except KeyboardInterrupt:
        print("\n[ENCERRADO] Monitor finalizado pelo usuário.")
    except Exception as exc:
        print(f"\n[ERRO FATAL] {exc}")
        return 1
    finally:
        rpc.close()

    return 0
