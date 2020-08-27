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
from botw.rstb import guess_aamp_size, guess_bfres_size
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
        be = util.get_settings("wiiu")  # pylint: disable=invalid-name
        size = getattr(calculate_size, "calculator").calculate_file_size_with_ext(
            data, wiiu=be, ext=ext, force=False
        )
        if ext == ".bdmgparam":
            size = 0
        if ext == ".hkrb":
            size += 40
        if ext == ".baniminfo":
            size = int(
                (((len(data) + 31) & -32) * (1.5 if len(data) > 36864 else 4))
                + 0xE4
                + 0x24C
            )
            if not be:
                size = int(size * 1.5)
        if size == 0 and guess:
            if ext in util.AAMP_EXTS:
                size = guess_aamp_size(data, be, ext)
            elif ext in {".bfres", ".sbfres"}:
                size = guess_bfres_size(
                    data, be, path if isinstance(path, str) else path.name,
                )
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


def _get_modded_file_size(file: Path, mod_dir: Path, guess: bool) -> Dict[str, int]:
    try:
        canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
    except ValueError:
        return {}
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
    _table: rstb.ResourceSizeTable

    def __init__(self):
        super().__init__(
            "RSTB",
            "Merges changes to ResourceSizeTable.product.srsizetable",
            "rstb.json",
        )
        self._options = {"no_guess": False}
        self._table = None

    def should_exclude(self, canon: str, val: int) -> bool:
        if canon in EXCLUDE_NAMES:
            return True
        if canon[canon.rindex(".") :] in EXCLUDE_EXTS:
            return True
        if self._table.is_in_table(canon):
            if val == 0:
                return False
            else:
                return val < self._table.get_size(canon)
        return val == 0

    def generate_diff(self, mod_dir: Path, modded_files: List[Path]):
        diff = {}
        nested_files = {}
        if not self._table:
            self._table = get_stock_rstb()
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
                if r is not None and not self.should_exclude(k, v)
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
                if r is not None and not self.should_exclude(k, v)
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
            ("no_guess", "Don't estimate RSTB values for AAMP and BFRES files"),
        ]

    @util.timed
    def perform_merge(self):
        pool = self._pool or Pool()
        if not self._table:
            self._table = get_stock_rstb()
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
                if r is not None and not self.should_exclude(k, v)
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
                if r is not None and not self.should_exclude(k, v)
            }
        )
        table = self._table
        for canon, size in diffs.copy().items():
            if size == 0:
                if table.is_in_table(canon):
                    table.delete_entry(canon)
                else:
                    continue
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
