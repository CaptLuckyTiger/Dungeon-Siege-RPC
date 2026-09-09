import math
import struct
import zlib
from pathlib import Path
from typing import Optional, Tuple

from ..config import TANK_FORMAT_LZO, TANK_FORMAT_RAW, TANK_FORMAT_ZLIB


class TankError(Exception):
    pass


class TankReader:
    """Leitor mínimo de Tank suficiente para extrair info.gas de .dssave."""

    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.size = len(self.data)
        self.data_offset: Optional[int] = None
        self.fileset_offset: Optional[int] = None

    def _unpack(self, fmt: str, offset: int):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > self.size:
            raise TankError(
                f"Leitura fora do arquivo: offset={offset}, tamanho={size}"
            )
        return struct.unpack_from(fmt, self.data, offset)

    def _read_nstring(self, offset: int) -> Tuple[str, int]:
        """Lê NSTRING do formato Tank e retorna (texto, novo_offset)."""
        (length,) = self._unpack("<H", offset)
        offset += 2

        if length == 0:
            if offset + 2 > self.size:
                raise TankError("NSTRING vazio truncado")
            offset += 2
            return "", offset

        padded = ((length + 2 + 3) // 4) * 4
        payload_len = padded - 2

        raw = self.data[offset: offset + payload_len]
        if len(raw) != payload_len:
            raise TankError("NSTRING truncado")

        offset += payload_len

        text = raw[:length].split(b"\x00", 1)[0].decode(
            "latin-1", errors="replace"
        )
        return text, offset

    def _read_header(self):
        if self.size < 28:
            raise TankError("Arquivo pequeno demais para ser um Tank")

        product_id = self.data[0:4]
        tank_id = self.data[4:8]

        if product_id not in (b"DSig", b"DSg2"):
            raise TankError(f"Product ID inválido: {product_id!r}")
        if tank_id != b"Tank":
            raise TankError(f"Tank ID inválido: {tank_id!r}")

        (_, _, _, dirset_offset, fileset_offset, _, data_offset) = self._unpack(
            "<4s4s5I", 0
        )

        self.fileset_offset = fileset_offset
        self.data_offset = data_offset
        return dirset_offset

    def extract(self, target_name: str = "info.gas") -> bytes:
        self._read_header()
        assert self.fileset_offset is not None
        assert self.data_offset is not None

        base = self.fileset_offset
        (num_files,) = self._unpack("<I", base)
        cursor = base + 4

        if num_files > 10000:
            raise TankError(f"Número de arquivos absurdo: {num_files}")

        file_offsets = []
        for _ in range(num_files):
            (relative,) = self._unpack("<I", cursor)
            cursor += 4
            file_offsets.append(relative)

        wanted = target_name.casefold()

        for relative in file_offsets:
            entry_offset = base + relative

            parent, file_size, file_offset, _crc = self._unpack(
                "<4I", entry_offset
            )
            cursor = entry_offset + 16

            cursor += 8

            file_format, flags = self._unpack("<HH", cursor)
            cursor += 4

            file_name, cursor = self._read_nstring(cursor)

            if file_name.casefold() != wanted:
                continue

            if flags & 0x8000:
                raise TankError(f"Arquivo interno inválido: {file_name}")

            absolute_data_base = self.data_offset + file_offset

            if file_format == TANK_FORMAT_RAW:
                end = absolute_data_base + file_size
                if end > self.size:
                    raise TankError("Dados RAW truncados")
                return self.data[absolute_data_base:end]

            if file_format == TANK_FORMAT_LZO:
                raise TankError(
                    "info.gas está em LZO; este leitor não implementa LZO."
                )

            if file_format != TANK_FORMAT_ZLIB:
                raise TankError(f"Formato interno desconhecido: {file_format}")

            compressed_size, chunk_size = self._unpack("<II", cursor)
            cursor += 8

            if chunk_size == 0:
                raise TankError(
                    "Tank Zlib sem chunk_size; não consigo interpretar este save."
                )

            num_chunks = math.ceil(file_size / chunk_size)
            chunks = []

            for _ in range(num_chunks):
                uncompressed_size, compressed_bytes, extra_bytes, chunk_offset = (
                    self._unpack("<4I", cursor)
                )
                cursor += 16
                chunks.append(
                    (
                        uncompressed_size,
                        compressed_bytes,
                        extra_bytes,
                        chunk_offset,
                    )
                )

            result = bytearray()

            for uncompressed_size, compressed_bytes, extra_bytes, chunk_offset in chunks:
                source = absolute_data_base + chunk_offset
                read_size = compressed_bytes + extra_bytes
                end = source + read_size

                if end > self.size:
                    raise TankError("Chunk Zlib truncado")

                chunk_data = self.data[source:end]

                if compressed_bytes == uncompressed_size:
                    plain = chunk_data[:uncompressed_size]
                else:
                    compressed_payload = chunk_data[:compressed_bytes]
                    try:
                        plain = zlib.decompress(compressed_payload)
                    except zlib.error as exc:
                        raise TankError(
                            f"Falha ao descomprimir info.gas: {exc}"
                        ) from exc

                    if len(plain) < uncompressed_size:
                        raise TankError(
                            "Chunk descomprimido menor que o tamanho esperado"
                        )
                    plain = plain[:uncompressed_size]

                result.extend(plain)

                if extra_bytes:
                    result.extend(chunk_data[compressed_bytes: compressed_bytes + extra_bytes])

            if len(result) < file_size:
                raise TankError(
                    f"info.gas extraído incompleto: {len(result)} < {file_size}"
                )

            return bytes(result[:file_size])

        raise TankError(f"Arquivo interno não encontrado: {target_name}")
