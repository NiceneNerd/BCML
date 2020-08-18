"""Provides functions for diffing and merging the BotW Resource Size Table"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=no-member
import json
import io
import math
import struct
from copy import deepcopy
from functools import partial, reduce
from multiprocessing import Pool
from pathlib import Path
from typing import List, Union, ByteString, Dict

# pylint: disable=wrong-import-order
import oead
import rstb
from rstb.util import read_rstb

from bcml import util, mergers

Contents = Union[List[str], Dict[str, Union[Dict, List[str]]]]

EXCLUDE_EXTS = {
    ".pack",
    ".bgdata",
    ".txt",
    ".bgsvdata",
    ".yml",
    ".msbt",
    ".bat",
    ".ini",
    ".png",
    ".bfstm",
    ".py",
    ".sh",
}
EXCLUDE_NAMES = {"Actor/ActorInfo.product.byml"}
SARC_EXCLUDES = {
    ".sarc",
    ".ssarc",
    ".blarc",
    ".sblarc",
    ".bfarc",
    ".sbfarc",
}


def calculate_size(
    path: Union[Path, str], data: ByteString = None, guess: bool = True
) -> int:
    ext = path.suffix if isinstance(path, Path) else path[path.rindex(".") :]
    data = util.unyaz_if_needed(path.read_bytes() if isinstance(path, Path) else data)
    try:
        size = getattr(calculate_size, "calculator").calculate_file_size_with_ext(
            data, wiiu=util.get_settings("wiiu"), ext=ext, force=False
        )
        if ext == ".bdmgparam":
            size = 0
        if ext == ".hkrb":
            size += 40
        if size == 0 and guess:
            if ext in util.AAMP_EXTS:
                size = guess_aamp_size(data, ext)
            elif ext in {".bfres", ".sbfres"}:
                size = guess_bfres_size(data, str(path))
        return size
    except struct.error:
        return 0


def get_stock_rstb() -> rstb.ResourceSizeTable:
    if not hasattr(get_stock_rstb, "table"):
        get_stock_rstb.table = read_rstb(
            str(
                util.get_game_file(
                    "System/Resource/ResourceSizeTable.product.srsizetable"
                )
            ),
            util.get_settings("wiiu"),
        )
    return deepcopy(get_stock_rstb.table)


def set_size(entry: str, size: int):
    rstb_path = (
        util.get_master_modpack_dir()
        / util.get_content_path()
        / "System"
        / "Resource"
        / "ResourceSizeTable.product.srsizetable"
    )
    if rstb_path.exists():
        table = read_rstb(rstb_path, be=util.get_settings("wiiu"))
    else:
        table = get_stock_rstb()
        rstb_path.parent.mkdir(parents=True, exist_ok=True)
    table.set_size(entry, size)
    buf = io.BytesIO()
    table.write(buf, be=util.get_settings("wiiu"))
    rstb_path.write_bytes(util.compress(buf.getvalue()))


def guess_bfres_size(file: Union[Path, ByteString], name: str = "") -> int:
    real_bytes = (
        file
        if isinstance(file, bytes)
        else file.tobytes()
        if isinstance(file, memoryview)
        else file.read_bytes()
    )
    if real_bytes[0:4] == b"Yaz0":
        real_size = oead.yaz0.get_header(real_bytes[0:16]).uncompressed_size
    else:
        real_size = int(len(real_bytes) * 1.05)
    del real_bytes
    if name == "":
        if isinstance(file, Path):
            name = file.name
        else:
            raise ValueError("BFRES name must not be blank if passing file as bytes.")
    value: int
    if util.get_settings("wiiu"):
        if ".Tex" in name:
            if real_size < 100:
                value = real_size * 9
            elif 100 < real_size <= 2000:
                value = real_size * 7
            elif 2000 < real_size <= 3000:
                value = real_size * 5
            elif 3000 < real_size <= 4000:
                value = real_size * 4
            elif 4000 < real_size <= 8500:
                value = real_size * 3
            elif 8500 < real_size <= 12000:
                value = real_size * 2
            elif 12000 < real_size <= 17000:
                value = real_size * 1.75
            elif 17000 < real_size <= 30000:
                value = real_size * 1.5
            elif 30000 < real_size <= 45000:
                value = real_size * 1.3
            elif 45000 < real_size <= 100000:
                value = real_size * 1.2
            elif 100000 < real_size <= 150000:
                value = real_size * 1.1
            elif 150000 < real_size <= 200000:
                value = real_size * 1.07
            elif 200000 < real_size <= 250000:
                value = real_size * 1.045
            elif 250000 < real_size <= 300000:
                value = real_size * 1.035
            elif 300000 < real_size <= 600000:
                value = real_size * 1.03
            elif 600000 < real_size <= 1000000:
                value = real_size * 1.015
            elif 1000000 < real_size <= 1800000:
                value = real_size * 1.009
            elif 1800000 < real_size <= 4500000:
                value = real_size * 1.005
            elif 4500000 < real_size <= 6000000:
                value = real_size * 1.002
            else:
                value = real_size * 1.0015
        else:
            if real_size < 500:
                value = real_size * 7
            elif 500 < real_size <= 750:
                value = real_size * 5
            elif 750 < real_size <= 1250:
                value = real_size * 4
            elif 1250 < real_size <= 2000:
                value = real_size * 3.5
            elif 2000 < real_size <= 400000:
                value = real_size * 2.25
            elif 400000 < real_size <= 600000:
                value = real_size * 2.1
            elif 600000 < real_size <= 1000000:
                value = real_size * 1.95
            elif 1000000 < real_size <= 1500000:
                value = real_size * 1.85
            elif 1500000 < real_size <= 3000000:
                value = real_size * 1.66
            else:
                value = real_size * 1.45
    else:
        if ".Tex" in name:
            if real_size > 50000:
                value = real_size * 1.2
            elif real_size > 30000:
                value = real_size * 1.3
            elif real_size > 10000:
                value = real_size * 1.5
            else:
                value = real_size * 2
        else:
            if real_size > 4000000:
                value = real_size * 1.5
            elif real_size > 3000000:
                value = real_size * 1.667
            elif real_size > 2000000:
                value = real_size * 2.5
            elif real_size > 800000:
                value = real_size * 3.15
            elif real_size > 100000:
                value = real_size * 3.5
            elif real_size > 50000:
                value = real_size * 3.66
            elif real_size > 2500:
                value = real_size * 4.25
            elif real_size > 1250:
                value = real_size * 6
            else:
                value = real_size * 9.5
    return int(value)


def guess_aamp_size(file: Union[Path, ByteString], ext: str = "") -> int:
    real_bytes = (
        file
        if isinstance(file, bytes) or isinstance(file, oead.Bytes)
        else file.tobytes()
        if isinstance(file, memoryview)
        else file.read_bytes()
    )
    if real_bytes[0:4] == b"Yaz0":
        real_bytes = util.decompress(real_bytes)
    real_size = len(real_bytes) * 1.05
    del real_bytes
    if ext == "":
        if isinstance(file, Path):
            ext = file.suffix
        else:
            raise ValueError("AAMP extension must not be blank if passing file as bytes.")
    ext = ext.replace(".s", ".")
    value: int
    if ext == ".baiprog":
        if real_size <= 380:
            value = real_size * 7
        elif 380 < real_size <= 400:
            value = real_size * 6
        elif 400 < real_size <= 450:
            value = real_size * 5.5
        elif 450 < real_size <= 600:
            value = real_size * 5
        elif 600 < real_size <= 1000:
            value = real_size * 4
        elif 1000 < real_size <= 1750:
            value = real_size * 3.5
        else:
            value = real_size * 3
    elif ext == ".bgparamlist":
        if real_size <= 100:
            value = real_size * 20
        elif 100 < real_size <= 150:
            value = real_size * 12
        elif 150 < real_size <= 250:
            value = real_size * 10
        elif 250 < real_size <= 350:
            value = real_size * 8
        elif 350 < real_size <= 450:
            value = real_size * 7
        else:
            value = real_size * 6
    elif ext == ".bdrop":
        if real_size < 200:
            value = real_size * 8.5
        elif 200 < real_size <= 250:
            value = real_size * 7
        elif 250 < real_size <= 350:
            value = real_size * 6
        elif 350 < real_size <= 450:
            value = real_size * 5.25
        elif 450 < real_size <= 850:
            value = real_size * 4.5
        else:
            value = real_size * 4
    elif ext == ".bxml":
        if real_size < 350:
            value = real_size * 6
        elif 350 < real_size <= 450:
            value = real_size * 5
        elif 450 < real_size <= 550:
            value = real_size * 4.5
        elif 550 < real_size <= 650:
            value = real_size * 4
        elif 650 < real_size <= 800:
            value = real_size * 3.5
        else:
            value = real_size * 3
    elif ext == ".brecipe":
        if real_size < 100:
            value = real_size * 12.5
        elif 100 < real_size <= 160:
            value = real_size * 8.5
        elif 160 < real_size <= 200:
            value = real_size * 7.5
        elif 200 < real_size <= 215:
            value = real_size * 7
        else:
            value = real_size * 6.5
    elif ext == ".bshop":
        if real_size < 200:
            value = real_size * 7.25
        elif 200 < real_size <= 400:
            value = real_size * 6
        elif 400 < real_size <= 500:
            value = real_size * 5
        else:
            value = real_size * 4.05
    elif ext == ".bas":
        real_size = real_size * 1.05
        if real_size < 100:
            value = real_size * 20
        elif 100 < real_size <= 200:
            value = real_size * 12.5
        elif 200 < real_size <= 300:
            value = real_size * 10
        elif 300 < real_size <= 600:
            value = real_size * 8
        elif 600 < real_size <= 1500:
            value = real_size * 6
        elif 1500 < real_size <= 2000:
            value = real_size * 5.5
        elif 2000 < real_size <= 15000:
            value = real_size * 5
        else:
            value = real_size * 4.5
    elif ext == ".baslist":
        if real_size < 100:
            value = real_size * 15
        elif 100 < real_size <= 200:
            value = real_size * 10
        elif 200 < real_size <= 300:
            value = real_size * 8
        elif 300 < real_size <= 500:
            value = real_size * 6
        elif 500 < real_size <= 800:
            value = real_size * 5
        elif 800 < real_size <= 4000:
            value = real_size * 4
        else:
            value = real_size * 3.5
    elif ext == ".bdmgparam":
        value = (((-0.0018 * real_size) + 6.6273) * real_size) + 750
    elif ext == ".bphysics":
        value = int(
            (((int(real_size) + 32) & -32) + 0x4E + 0x324)
            * max(4 * math.floor(real_size / 1388), 3)
        )
    else:
        value = 0
    if not util.get_settings("wiiu"):
        value *= 1.5
    return int(value)


def _get_modded_file_size(file: Path, mod_dir: Path, guess: bool) -> Dict[str, int]:
    canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
    if file.suffix not in EXCLUDE_EXTS and canon not in EXCLUDE_NAMES:
        return {
            canon: calculate_size(
                file, guess=guess or file.suffix in {".bas", ".baslist"},
            )
        }
    return {}


def _get_nest_file_sizes(
    file: str, contents: Contents, mod_dir: Path, guess: bool,
) -> Dict[str, int]:
    def get_sizes_in_sarc(
        sarc: oead.Sarc, contents: Contents, guess: bool, dlc: bool
    ) -> Dict[str, int]:
        prefix = "" if not dlc else "Aoc/0010/"
        vals = {}
        if isinstance(contents, list):
            for file in contents:
                if file[file.rindex(".") :] in EXCLUDE_EXTS:
                    continue
                canon = prefix + file.replace(".s", ".")
                vals[canon] = calculate_size(canon, sarc.get_file(file).data, guess)
        elif isinstance(contents, dict):
            for subpath, subcontents in contents.items():
                ext = subpath[subpath.rindex(".") :]
                if ext in EXCLUDE_EXTS:
                    continue
                data = util.unyaz_if_needed(sarc.get_file(subpath).data)
                canon = prefix + subpath.replace(".s", ".")
                vals[canon] = calculate_size(canon, data, guess)
                if ext not in SARC_EXCLUDES:
                    try:
                        subsarc = oead.Sarc(data)
                    except (ValueError, RuntimeError, oead.InvalidDataError):
                        continue
                    vals.update(get_sizes_in_sarc(subsarc, subcontents, guess, dlc))
        return vals

    dlc = util.get_dlc_path() in file
    vals = {}
    try:
        sarc = oead.Sarc(util.unyaz_if_needed((mod_dir / file).read_bytes()))
    except (ValueError, RuntimeError, oead.InvalidDataError):
        return {}
    vals.update(get_sizes_in_sarc(sarc, contents, guess, dlc))
    return vals


def _get_sizes_in_sarc(
    file: Union[Path, oead.Sarc], guess: bool, is_aoc: bool = False
) -> {}:
    sizes = {}
    if isinstance(file, Path):
        is_aoc = util.get_dlc_path() in file.as_posix()
        try:
            file = oead.Sarc(util.unyaz_if_needed(file.read_bytes()))
        except (RuntimeError, oead.InvalidDataError):
            print(f"{file} could not be opened")
            return {}
    for nest_file, data in [(file.name, file.data) for file in file.get_files()]:
        canon = nest_file.replace(".s", ".")
        if data[0:4] == b"Yaz0":
            data = util.decompress(data)
        ext = Path(canon).suffix
        if (
            util.is_file_modded(canon, data)
            and ext not in EXCLUDE_EXTS
            and canon not in EXCLUDE_NAMES
        ):
            sizes[canon] = calculate_size(canon, data, guess=guess)
            if ext in util.SARC_EXTS - SARC_EXCLUDES:
                try:
                    nest_sarc = oead.Sarc(data)
                except (ValueError, RuntimeError, oead.InvalidDataError):
                    continue
                sizes.update(_get_sizes_in_sarc(nest_sarc, guess, is_aoc=is_aoc))
                del nest_sarc
        del data
    del file
    return sizes


class RstbMerger(mergers.Merger):
    """ A merger for the ResourceSizeTable.product.srsizetable """

    NAME: str = "rstb"

    def __init__(self):
        super().__init__(
            "RSTB",
            "Merges changes to ResourceSizeTable.product.srsizetable",
            "rstb.json",
        )
        self._options = {"no_guess": False, "leave": False, "shrink": False}

    def generate_diff(self, mod_dir: Path, modded_files: List[Path]):
        diff = {}
        nested_files = {}
        pool = self._pool or Pool()
        for nest in {n for n in modded_files if isinstance(n, str)}:
            util.dict_merge(
                nested_files,
                reduce(
                    lambda res, cur: {cur: res} if res is not None else [cur],
                    reversed(nest.split("//")),
                    None,
                ),
            )
        table = get_stock_rstb()
        diff.update(
            {
                k: v
                for r in pool.map(
                    partial(
                        _get_modded_file_size,
                        mod_dir=mod_dir,
                        guess=not self._options.get("no_guess", False),
                    ),
                    {f for f in modded_files if isinstance(f, Path)},
                )
                for k, v in r.items()
                if r is not None
                and not (
                    table.is_in_table(k)
                    and (
                        (v == 0 and self._options.get("leave", False))
                        or (
                            v < table.get_size(k)
                            and not self._options.get("shrink", False)
                        )
                    )
                )
            }
        )
        diff.update(
            {
                k: v
                for r in pool.starmap(
                    partial(
                        _get_nest_file_sizes,
                        guess=not self._options.get("no_guess", False),
                        mod_dir=mod_dir,
                    ),
                    nested_files.items(),
                )
                for k, v in r.items()
                if r is not None
                and not (
                    table.is_in_table(k)
                    and (
                        (v == 0 and self._options.get("leave", False))
                        or (
                            v < table.get_size(k)
                            and not self._options.get("shrink", False)
                        )
                    )
                )
            }
        )
        if not self._pool:
            pool.close()
            pool.join()
        return diff

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                json.dumps(diff_material, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = {}
        if self.is_mod_logged(mod):
            diff.update(
                json.loads((mod.path / "logs" / self._log_name).read_text("utf-8"))
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                diff.update(
                    json.loads((opt / "logs" / self._log_name).read_text("utf-8"))
                )
        return diff

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: List[dict]):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    def get_checkbox_options(self) -> List[tuple]:
        return [
            ("leave", "Don't remove RSTB entries for complex file types"),
            ("shrink", "Shrink RSTB values when smaller than stock"),
            ("no_guess", "Don't estimate RSTB values for AAMP and BFRES files"),
        ]

    @util.timed
    def perform_merge(self):
        pool = self._pool or Pool()
        table = get_stock_rstb()
        diffs = self.consolidate_diffs(self.get_all_diffs())
        master = util.get_master_modpack_dir()
        master_files = {
            f for f in master.rglob("**/*") if f.is_file() and "logs" not in f.parts
        }
        diffs.update(
            {
                k: v
                for r in pool.map(
                    partial(
                        _get_modded_file_size,
                        mod_dir=master,
                        guess=not self._options.get("no_guess", False),
                    ),
                    {f for f in master_files if f.suffix not in EXCLUDE_EXTS},
                )
                for k, v in r.items()
                if r is not None
                and not (
                    table.is_in_table(k)
                    and (
                        (v == 0 and self._options.get("leave", False))
                        or (
                            v < table.get_size(k)
                            and not self._options.get("shrink", False)
                        )
                    )
                )
            }
        )

        diffs.update(
            {
                k: v
                for r in pool.map(
                    partial(_get_sizes_in_sarc, guess=not util.get_settings("no_guess"),),
                    {
                        f
                        for f in master_files
                        if f.suffix in util.SARC_EXTS - SARC_EXCLUDES
                    },
                )
                for k, v in r.items()
                if r is not None
                and not (
                    table.is_in_table(k)
                    and (
                        (v == 0 and self._options.get("leave", False))
                        or (
                            v < table.get_size(k)
                            and not self._options.get("shrink", False)
                        )
                    )
                )
            }
        )

        for canon, size in diffs.copy().items():
            if size == 0 and table.is_in_table(canon):
                table.delete_entry(canon)
            elif table.is_in_table(canon) and size < table.get_size(canon):
                del diffs[canon]
                continue
            else:
                table.set_size(canon, size)
        if table.is_in_table(f"Message/Msg_{util.get_settings('lang')}.product.sarc"):
            table.delete_entry(f"Message/Msg_{util.get_settings('lang')}.product.sarc")

        out = (
            master
            / util.get_content_path()
            / "System"
            / "Resource"
            / "ResourceSizeTable.product.srsizetable"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        with io.BytesIO() as buf:
            table.write(buf, util.get_settings("wiiu"))
            out.write_bytes(util.compress(buf.getvalue()))

        log = master / "logs" / "rstb.json"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps(diffs, ensure_ascii=False, indent=2, sort_keys=True))

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return set(self.get_mod_diff(mod).keys())


setattr(calculate_size, "calculator", rstb.SizeCalculator())
