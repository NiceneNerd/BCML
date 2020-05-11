"""Provides functions for diffing and merging the BotW Resource Size Table"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import csv
import io
import os
import multiprocessing
import struct
import zlib
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import List, Union

import oead
import rstb
from rstb import ResourceSizeTable
from rstb.util import read_rstb

from bcml import util, install, mergers
from bcml.util import BcmlMod

RSTB_EXCLUDE_EXTS = {
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
RSTB_EXCLUDE_NAMES = {"Actor/ActorInfo.product.byml"}


def generate_rstb_for_mod(mod: Path):
    files = install.find_modded_files(mod)
    merger = RstbMerger()
    diff = merger.generate_diff(mod, files)
    print("Creating RSTB...")
    table = get_stock_rstb()
    for file, value in diff.items():
        canon: str
        if isinstance(file, Path):
            canon = util.get_canon_name(file.relative_to(mod))
        else:
            canon = file.split("//")[-1].replace(".s", ".")
        if (
            not (table.is_in_table(canon) and value <= table.get_size(canon))
            and value > 0
        ):
            table.set_size(canon, value)
    print("Writing RSTB...")
    rstb_path = (
        mod
        / util.get_content_path()
        / "System"
        / "Resource"
        / "ResourceSizeTable.srsizetable"
    )
    rstb_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    table.write(buf, util.get_settings("wiiu"))
    rstb_path.write_bytes(util.compress(buf.getvalue()))
    del buf
    del table


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


def calculate_size(path: Path) -> int:
    try:
        return calculate_size.rstb_calc.calculate_file_size(
            file_name=str(path), wiiu=util.get_settings("wiiu"), force=False
        )
    except struct.error:
        return 0


setattr(calculate_size, "rstb_calc", rstb.SizeCalculator())


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


def guess_bfres_size(file: Union[Path, bytes], name: str = "") -> int:
    real_bytes = file if isinstance(file, bytes) else file.read_bytes()
    if real_bytes[0:4] == b"Yaz0":
        real_bytes = util.decompress(real_bytes)
    real_size = int(len(real_bytes) * 1.05)
    del real_bytes
    if name == "":
        if isinstance(file, Path):
            name = file.name
        else:
            raise ValueError("BFRES name must not be blank if passing file as bytes.")
    if util.get_settings("wiiu"):
        if ".Tex" in name:
            if real_size < 100:
                return real_size * 9
            elif 100 < real_size <= 2000:
                return real_size * 7
            elif 2000 < real_size <= 3000:
                return real_size * 5
            elif 3000 < real_size <= 4000:
                return real_size * 4
            elif 4000 < real_size <= 8500:
                return real_size * 3
            elif 8500 < real_size <= 12000:
                return real_size * 2
            elif 12000 < real_size <= 17000:
                return int(real_size * 1.75)
            elif 17000 < real_size <= 30000:
                return int(real_size * 1.5)
            elif 30000 < real_size <= 45000:
                return int(real_size * 1.3)
            elif 45000 < real_size <= 100000:
                return int(real_size * 1.2)
            elif 100000 < real_size <= 150000:
                return int(real_size * 1.1)
            elif 150000 < real_size <= 200000:
                return int(real_size * 1.07)
            elif 200000 < real_size <= 250000:
                return int(real_size * 1.045)
            elif 250000 < real_size <= 300000:
                return int(real_size * 1.035)
            elif 300000 < real_size <= 600000:
                return int(real_size * 1.03)
            elif 600000 < real_size <= 1000000:
                return int(real_size * 1.015)
            elif 1000000 < real_size <= 1800000:
                return int(real_size * 1.009)
            elif 1800000 < real_size <= 4500000:
                return int(real_size * 1.005)
            elif 4500000 < real_size <= 6000000:
                return int(real_size * 1.002)
            else:
                return int(real_size * 1.0015)
        else:
            if real_size < 500:
                return real_size * 7
            elif 500 < real_size <= 750:
                return real_size * 4
            elif 750 < real_size <= 2000:
                return real_size * 3
            elif 2000 < real_size <= 400000:
                return int(real_size * 1.75)
            elif 400000 < real_size <= 600000:
                return int(real_size * 1.7)
            elif 600000 < real_size <= 1500000:
                return int(real_size * 1.6)
            elif 1500000 < real_size <= 3000000:
                return int(real_size * 1.5)
            else:
                return int(real_size * 1.25)
    else:
        if ".Tex" in name:
            if 50000 < real_size:
                return int(real_size * 1.2)
            elif 30000 < real_size:
                return int(real_bytes * 1.3)
            elif 10000 < real_size:
                return int(real_size * 1.5)
            else:
                return real_size * 2
        else:
            if 4000000 < real_size:
                return int(real_size * 1.5)
            elif 3000000 < real_size:
                return int(real_size * 1.667)
            elif 2000000 < real_size:
                return real_size * 2
            elif 800000 < real_size:
                return int(real_size * 2.367)
            elif 100000 < real_size:
                return int(real_size * 2.5)
            elif 50000 < real_size:
                return int(real_size * 3.4)
            elif 2500 < real_size:
                return real_size * 4
            elif 1250 < real_size:
                return real_size * 5
            else:
                return int(real_size * 9.5)


def guess_aamp_size(file: Union[Path, bytes], ext: str = "") -> int:
    real_bytes = (
        file
        if isinstance(file, bytes)
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
            raise ValueError(
                "AAMP extension must not be blank if passing file as bytes."
            )
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
        value = (((-0.0018 * real_size) + 6.6273) * real_size) + 500
    else:
        value = 0
    if not util.get_settings("wiiu"):
        value = value * 1.5
    return int(value)


def get_mod_rstb_values(
    mod: Union[Path, str, BcmlMod], log_name: str = "rstb.log"
) -> {}:
    """ Gets all of the RSTB values for a given mod """
    path = (
        mod
        if isinstance(mod, Path)
        else Path(mod)
        if isinstance(mod, str)
        else mod.path
    )
    changes = {}
    leave = (path / "logs" / ".leave").exists()
    shrink = (path / "logs" / ".shrink").exists()
    with (path / "logs" / log_name).open("r") as l_file:
        log_loop = csv.reader(l_file)
        for row in log_loop:
            if row[0] != "name":
                changes[row[0]] = {"size": row[1], "leave": leave, "shrink": shrink}
    return changes


def merge_rstb(table: ResourceSizeTable, changes: dict) -> ResourceSizeTable:
    spaces = "  "
    change_count = {"updated": 0, "deleted": 0, "added": 0, "warning": 0}
    for change in changes:
        if zlib.crc32(change.encode()) in table.crc32_map:
            newsize = int(changes[change]["size"])
            if newsize == 0:
                if not changes[change]["leave"]:
                    if change.endswith(".bas") or change.endswith(".baslist"):
                        print(
                            f"{spaces}WARNING: Could not calculate or safely remove RSTB size for"
                            f"{change}. This may need to be corrected manually, or the game could "
                            "become unstable"
                        )
                        change_count["warning"] += 1
                        continue
                    else:
                        table.delete_entry(change)
                        util.vprint(f"{spaces}Deleted RSTB entry for {change}")
                        change_count["deleted"] += 1
                        continue
                else:
                    util.vprint(f"{spaces}Skipped deleting RSTB entry for {change}")
                    continue
            oldsize = table.get_size(change)
            if newsize <= oldsize:
                if changes[change]["shrink"]:
                    table.set_size(change, newsize)
                    util.vprint(
                        f"{spaces}Updated RSTB entry for {change} from {oldsize} to {newsize}"
                    )
                    change_count["updated"] += 1
                    continue
                else:
                    util.vprint(f"{spaces}Skipped updating RSTB entry for {change}")
                    continue
            elif newsize > oldsize:
                table.set_size(change, newsize)
                util.vprint(
                    f"{spaces}Updated RSTB entry for {change} from {oldsize} to {newsize}"
                )
                change_count["updated"] += 1
        else:
            try:
                newsize = int(changes[change]["size"])
            except ValueError:
                newsize = int(float(changes[change]["size"]))
            if newsize == 0:
                util.vprint(
                    f"{spaces}Could not calculate size for new entry {change}, skipped"
                )
                continue
            table.set_size(change, newsize)
            util.vprint(
                f"{spaces}Added new RSTB entry for {change} with value {newsize}"
            )
            change_count["added"] += 1
    print(
        f'RSTB merge complete: updated {change_count["updated"]} entries, deleted'
        f' {change_count["deleted"]} entries, added {change_count["added"]} entries'
    )
    return table


def _get_sizes_in_sarc(file: Union[Path, oead.Sarc]) -> {}:
    calc = rstb.SizeCalculator()
    sizes = {}
    no_guess = util.get_settings("no_guess")
    if isinstance(file, Path):
        try:
            file = oead.Sarc(file.read_bytes())
        except (RuntimeError, oead.InvalidDataError):
            return {}
    for nest_file, data in [(file.name, file.data) for file in file.get_files()]:
        canon = nest_file.replace(".s", ".")
        if data[0:4] == b"Yaz0":
            data = util.decompress(data)
        ext = Path(canon).suffix
        if (
            util.is_file_modded(canon, data)
            and ext not in RSTB_EXCLUDE_EXTS
            and canon not in RSTB_EXCLUDE_NAMES
        ):
            size = calc.calculate_file_size_with_ext(
                data, wiiu=util.get_settings("wiiu"), ext=ext
            )
            if ext == ".bdmgparam":
                size = 0
            if size == 0 and not no_guess:
                if ext in util.AAMP_EXTS:
                    size = guess_aamp_size(data, ext)
                elif ext in {".bfres", ".sbfres"}:
                    size = guess_bfres_size(data, canon)
            sizes[canon] = size
            if ext in util.SARC_EXTS and not ext not in {
                ".sarc",
                ".blarc",
                ".bfarc",
                ".ssarc",
                ".sbfarc",
                ".sblarc",
            }:
                try:
                    nest_sarc = oead.Sarc(data)
                except (ValueError, RuntimeError, oead.InvalidDataError):
                    continue
                sizes.update(_get_sizes_in_sarc(nest_sarc))
                del nest_sarc
        del data
    del file
    return sizes


def _calculate_rstb_size(file: Path, root: Path, no_guess: bool = False) -> dict:
    canon = util.get_canon_name(file.relative_to(root))
    if not (file.suffix in RSTB_EXCLUDE_EXTS or canon in RSTB_EXCLUDE_NAMES):
        size = calculate_size(file)
        if size == 0 and not no_guess:
            if file.suffix in util.AAMP_EXTS:
                size = guess_aamp_size(file)
            elif file.suffix in {".bfres", ".sbfres"}:
                size = guess_bfres_size(file)
        if canon:
            return {canon: size}
    return {}


def log_merged_files_rstb(pool: multiprocessing.Pool = None):
    p: multiprocessing.Pool = pool or multiprocessing.Pool()
    print("Updating RSTB for merged files...")
    diffs = {}
    files = {
        f
        for f in util.get_master_modpack_dir().rglob("**/*")
        if f.is_file() and f.parent != "logs"
    }
    no_guess = util.get_settings("no_guess")
    results = p.map(
        partial(
            _calculate_rstb_size, root=util.get_master_modpack_dir(), no_guess=no_guess
        ),
        files,
    )
    for result in results:
        diffs.update(result)
    print("Updating RSTB for merged SARCs...")
    sarc_files = {
        f
        for f in files
        if (f.suffix in (util.SARC_EXTS - {".ssarc", ".sblarc", ".sbfarc"}))
    }
    if sarc_files:
        results = p.map(_get_sizes_in_sarc, sarc_files)
        for result in results:
            diffs.update(result)
    if not pool:
        p.close()
        p.join()
    (util.get_master_modpack_dir() / "logs").mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / "logs" / "rstb.log").open(
        "w", encoding="utf-8"
    ) as log:
        log.write("name,size,path\n")
        for canon, size in diffs.items():
            log.write(f"{canon},{size},//\n")


def generate_master_rstb():
    print("Merging RSTB changes...")
    if (util.get_master_modpack_dir() / "logs" / "master-rstb.log").exists():
        (util.get_master_modpack_dir() / "logs" / "master-rstb.log").unlink()

    table = get_stock_rstb()
    rstb_values = {}
    for mod in util.get_installed_mods():
        rstb_values.update(get_mod_rstb_values(mod))
    if (util.get_master_modpack_dir() / "logs" / "rstb.log").exists():
        rstb_values.update(get_mod_rstb_values(util.get_master_modpack_dir()))

    table = merge_rstb(table, rstb_values)

    for bootup_pack in util.get_master_modpack_dir().glob(
        f"{util.get_content_path()}/Pack/Bootup_*.pack"
    ):
        lang = util.get_file_language(bootup_pack)
        if table.is_in_table(f"Message/Msg_{lang}.product.sarc"):
            table.delete_entry(f"Message/Msg_{lang}.product.sarc")

    rstb_path = (
        util.get_master_modpack_dir()
        / util.get_content_path()
        / "System"
        / "Resource"
        / "ResourceSizeTable.product.srsizetable"
    )
    if not rstb_path.exists():
        rstb_path.parent.mkdir(parents=True, exist_ok=True)
    with rstb_path.open("wb") as r_file:
        with io.BytesIO() as buf:
            table.write(buf, util.get_settings("wiiu"))
            r_file.write(util.compress(buf.getvalue()))

    rstb_log = util.get_master_modpack_dir() / "logs" / "master-rstb.log"
    rstb_log.parent.mkdir(parents=True, exist_ok=True)
    from json import dumps

    rstb_log.write_text(dumps(rstb_values))


class RstbMerger(mergers.Merger):
    """ A merger for the ResourceSizeTable.product.srsizetable """

    NAME: str = "rstb"

    def __init__(self):
        super().__init__(
            "RSTB",
            "Merges changes to ResourceSizeTable.product.srsizetable",
            "rstb.log",
        )
        self._options = {"no_guess": False, "leave": False, "shrink": False}

    def generate_diff(self, mod_dir: Path, modded_files: List[Path]):
        rstb_diff = {}
        open_sarcs = {}
        for file in modded_files:
            if isinstance(file, Path):
                canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
                if (
                    Path(canon).suffix not in RSTB_EXCLUDE_EXTS
                    and canon not in RSTB_EXCLUDE_NAMES
                ):
                    size = calculate_size(file)
                    if file.suffix == ".bdmgparam":
                        size = 0
                    if size == 0 and not self._options.get("no_guess", False):
                        if file.suffix in util.AAMP_EXTS:
                            size = guess_aamp_size(file)
                        elif file.suffix in [".bfres", ".sbfres"]:
                            size = guess_bfres_size(file)
                    rstb_diff[file] = size
            elif isinstance(file, str):
                parts = file.split("//")
                if any(
                    Path(p).suffix in {".ssarc", ".sblarc", ".sbfarc"}
                    for p in parts[0:-1]
                ):
                    continue
                name = parts[-1]
                if parts[0] not in open_sarcs:
                    open_sarcs[parts[0]] = oead.Sarc(
                        util.unyaz_if_needed((mod_dir / parts[0]).read_bytes())
                    )
                for part in parts[1:-1]:
                    if part not in open_sarcs:
                        open_sarcs[part] = oead.Sarc(
                            util.unyaz_if_needed(
                                open_sarcs[parts[parts.index(part) - 1]]
                                .get_file(part)
                                .data
                            )
                        )
                ext = Path(name).suffix
                data = util.unyaz_if_needed(open_sarcs[parts[-2]].get_file(name).data)
                rstb_val = rstb.SizeCalculator().calculate_file_size_with_ext(
                    bytes(data), wiiu=util.get_settings("wiiu"), ext=ext
                )
                if ext == ".bdmgparam":
                    rstb_val = 0
                if rstb_val == 0 and not self._options.get("no_guess", False):
                    if ext in util.AAMP_EXTS:
                        rstb_val = guess_aamp_size(data, ext)
                    elif ext in {".bfres", ".sbfres"}:
                        rstb_val = guess_bfres_size(data, name)
                rstb_diff[file] = rstb_val
        for open_sarc in open_sarcs:
            del open_sarc
        return rstb_diff

    def log_diff(self, mod_dir: Path, diff_material):
        diffs = {}
        if isinstance(diff_material, dict):
            diffs = diff_material
        elif isinstance(diff_material, List):
            diffs = self.generate_diff(mod_dir, diff_material)

        log_path = mod_dir / "logs" / self._log_name
        with log_path.open("w", encoding="utf-8") as log:
            log.write("name,rstb,path\n")
            for diff, value in diffs.items():
                ext = Path(diff).suffix
                if isinstance(diff, Path):
                    canon = util.get_canon_name(str(diff.relative_to(mod_dir)))
                    path = diff.relative_to(mod_dir).as_posix()
                elif isinstance(diff, str):
                    canon = diff.split("//")[-1].replace(".s", ".")
                    path = diff
                if ext not in RSTB_EXCLUDE_EXTS and canon not in RSTB_EXCLUDE_NAMES:
                    log.write(f"{canon},{value},{path}\n")

        if "leave" in self._options and self._options["leave"]:
            (mod_dir / "logs" / ".leave").write_bytes(b"")
        if "shrink" in self._options and self._options["shrink"]:
            (mod_dir / "logs" / ".shrink").write_bytes(b"")

    def get_mod_diff(self, mod: util.BcmlMod):
        if not self._options:
            self._options["leave"] = (mod.path / "logs" / ".leave").exists()
            self._options["shrink"] = (mod.path / "logs" / ".shrink").exists()
        stock_rstb = get_stock_rstb()

        mod_diffs = {}

        def read_log(log_path: Path) -> {}:
            diffs = {}
            with log_path.open("r", encoding="utf-8") as log:
                for line in log.readlines()[1:]:
                    row = line.split(",")
                    name = row[0]
                    size = int(row[1])
                    old_size = 0
                    if stock_rstb.is_in_table(name):
                        old_size = stock_rstb.get_size(name)
                    if (size == 0 and self._options["leave"]) or (
                        size < old_size and self._options["shrink"]
                    ):
                        continue
                    diffs[row[0]] = int(row[1])
            return diffs

        if self.is_mod_logged(mod):
            mod_diffs.update(read_log(mod.path / "logs" / self._log_name))
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                mod_diffs.update(read_log(opt / "logs" / self._log_name))
        return mod_diffs

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
            ("shrink", "Shrink RSTB values when smaller than the base game"),
            ("no_guess", "Don't estimate RSTB values for AAMP and BFRES files"),
        ]

    @util.timed
    def perform_merge(self):
        print("Perfoming RSTB merge...")
        log_merged_files_rstb(self._pool)
        generate_master_rstb()

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return set(self.get_mod_diff(mod).keys())
