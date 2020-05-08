"""Provides functions for diffing and merging AAMP files"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import multiprocessing
import os
from copy import deepcopy
from functools import partial, reduce
from pathlib import Path
from typing import List, Union

import aamp
import aamp.converters
from aamp.parameters import ParameterList, ParameterIO, ParameterObject
import aamp.yaml_util
import oead

import bcml.mergers.rstable
from bcml import util, install, mergers
from bcml.util import BcmlMod


AAMP_EXTS_HANDLED = {
    '.brecipe', '.sbrecipe', '.bshop', '.sbshop'
}


def _aamp_diff(
    base: Union[ParameterIO, ParameterList], modded: Union[ParameterIO, ParameterList]
) -> ParameterList:
    diffs = ParameterList()
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            diffs.lists[crc] = plist
        else:
            diff = _aamp_diff(base.lists[crc], plist)
            if diff.lists or diff.objects:
                diffs.lists[crc] = diff
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            diffs.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            diff_obj = ParameterObject()
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or str(value) != str(
                    base_obj.params[param]
                ):
                    changed = True
                    diff_obj.params[param] = value
            if changed:
                diffs.objects[crc] = diff_obj
    return diffs


def _aamp_merge(
    base: Union[ParameterIO, ParameterList], modded: Union[ParameterIO, ParameterList]
) -> ParameterIO:
    merged = deepcopy(base)
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            merged.lists[crc] = plist
        else:
            merge = _aamp_merge(base.lists[crc], plist)
            if merge.lists or merge.objects:
                merged.lists[crc] = merge
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            merged.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            merge_obj = deepcopy(base_obj)
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or value != base_obj.params[param]:
                    changed = True
                    merge_obj.params[param] = value
            if changed:
                merged.objects[crc] = merge_obj
    return merged


def get_aamp_diff(file: Union[Path, str], tmp_dir: Path):
    """
    Diffs a modded AAMP file from the stock game version

    :param file: The modded AAMP file to diff
    :type file: class:`typing.Union[class:pathlib.Path, str]`
    :param tmp_dir: The temp directory containing the mod
    :type tmp_dir: class:`pathlib.Path`
    :return: Returns a string representation of the AAMP file diff
    """
    if isinstance(file, str):
        nests = file.split("//")
        mod_bytes = util.get_nested_file_bytes(file)
        ref_path = (
            str(util.get_game_file(Path(nests[0]).relative_to(tmp_dir)))
            + "//"
            + "//".join(nests[1:])
        )
        ref_bytes = util.get_nested_file_bytes(ref_path)
    else:
        with file.open("rb") as m_file:
            mod_bytes = m_file.read()
        mod_bytes = util.unyaz_if_needed(mod_bytes)
        with util.get_game_file(file.relative_to(tmp_dir)).open("rb") as r_file:
            ref_bytes = r_file.read()
        ref_bytes = util.unyaz_if_needed(ref_bytes)

    ref_aamp = aamp.Reader(ref_bytes).parse()
    mod_aamp = aamp.Reader(mod_bytes).parse()

    diff = _aamp_diff(ref_aamp, mod_aamp)
    del mod_aamp
    del mod_bytes
    del ref_aamp
    del ref_bytes
    return diff


def get_deepmerge_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that use deep merge """
    dmods = [
        mod
        for mod in util.get_installed_mods()
        if (mod.path / "logs" / "deepmerge.yml").exists()
    ]
    return sorted(dmods, key=lambda mod: mod.priority)


def nested_patch(pack: oead.Sarc, nest: dict) -> (oead.SarcWriter, dict):
    new_sarc = oead.SarcWriter.from_sarc(pack)
    failures = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file(file).data
        yazd = file_bytes[0:4] == b"Yaz0"
        file_bytes = util.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = oead.Sarc(file_bytes)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + "//" + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = bytes(new_sub_sarc.write()[1])
            new_sarc.files[file] = new_bytes if not yazd else util.compress(new_bytes)

        elif isinstance(stuff, list):
            try:
                if file_bytes[0:4] == b"AAMP":
                    aamp_contents = aamp.Reader(bytes(file_bytes)).parse()
                    try:
                        for change in stuff:
                            aamp_contents = _aamp_merge(aamp_contents, change)
                        aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                    except:  # pylint: disable=bare-except
                        raise RuntimeError(f"AAMP file {file} could be merged.")
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
                    cache_merged_aamp(file, new_bytes)
                else:
                    raise ValueError("Wait, what the heck, this isn't an AAMP file?!")
            except ValueError:
                new_bytes = pack.get_file(file).data
                print(f"Deep merging {file} failed. No changes were made.")

            new_sarc.files[file] = oead.Bytes(new_bytes)
    return new_sarc, failures


def cache_merged_aamp(file: str, data: bytes):
    out = Path(util.get_master_modpack_dir() / "logs" / "dm" / file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def get_merged_files() -> List[str]:
    """Gets a list of all currently deep merged files"""
    log = util.get_master_modpack_dir() / "logs" / "deepmerge.log"
    if not log.exists():
        return []
    else:
        with log.open("r") as l_file:
            return l_file.readlines()


def threaded_merge(item) -> (str, dict):
    """Deep merges an individual file, suitable for multiprocessing"""
    file, stuff = item
    failures = {}

    base_file = util.get_game_file(file, file.startswith(util.get_dlc_path()))
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    file_ext = os.path.splitext(file)[1]
    if file_ext in util.SARC_EXTS and (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    file_bytes = base_file.read_bytes()
    yazd = file_bytes[0:4] == b"Yaz0"
    file_bytes = file_bytes if not yazd else util.decompress(file_bytes)
    magic = file_bytes[0:4]

    if magic == b"SARC":
        new_sarc, sub_failures = nested_patch(oead.Sarc(file_bytes), stuff)
        del file_bytes
        new_bytes = bytes(new_sarc.write()[1])
        for failure, contents in sub_failures.items():
            print(f"Some patches to {failure} failed to apply.")
            failures[failure] = contents
    else:
        try:
            if magic == b"AAMP":
                aamp_contents = aamp.Reader(file_bytes).parse()
                try:
                    for change in stuff:
                        aamp_contents = _aamp_merge(aamp_contents, change)
                    aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                except:  # pylint: disable=bare-except
                    raise RuntimeError(f"AAMP file {file} could be merged.")
                del aamp_contents
                new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
            else:
                raise ValueError(f"{file} is not a SARC or AAMP file.")
        except ValueError:
            new_bytes = file_bytes
            del file_bytes
            print(f"Deep merging file {file} failed. No changes were made.")

    new_bytes = new_bytes if not yazd else util.compress(new_bytes)
    output_file = util.get_master_modpack_dir() / file
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(new_bytes)
    del new_bytes
    if magic == b"SARC":
        util.vprint(f"Finished patching files inside {file}")
    else:
        util.vprint(f"Finished patching {file}")
    return util.get_canon_name(file), failures


class DeepMerger(mergers.Merger):
    NAME: str = "deepmerge"

    def __init__(self):
        super().__init__(
            "AAMP files",
            "Merges changes within arbitrary AAMP files",
            "deepmerge.aamp",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        print("Logging changes to AAMP files...")
        diffs = {}
        for file in {f for f in modded_files if Path(f).suffix in (util.AAMP_EXTS - AAMP_EXTS_HANDLED)}:
            try:
                diffs[file] = get_aamp_diff(str(mod_dir) + "/" + file, mod_dir)
            except (FileNotFoundError, KeyError, TypeError, AttributeError) as e:
                continue
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            from aamp import ParameterIO, ParameterObject, ParameterList, Writer

            pio = ParameterIO("log", 0)
            root = ParameterList()
            for file, plist in diff_material.items():
                root.set_list(file, plist)
            pio.set_list("param_root", root)
            file_table = ParameterObject()
            for i, f in enumerate(diff_material):
                file_table.set_param(f"File{i}", f)
            root.set_object("FileTable", file_table)
            aamp_bytes = Writer(pio).get_bytes()
            (mod_dir / "logs" / self._log_name).write_bytes(aamp_bytes)
            del diff_material
            del pio
            del root
            del file_table

    def can_partial_remerge(self):
        return True

    def get_mod_affected(self, mod):
        files = set()
        for diff in self.get_mod_diff(mod):
            files |= set(diff.keys())
        return files

    def get_mod_diff(self, mod: BcmlMod):
        diffs = []
        if self.is_mod_logged(mod):
            pio = aamp.Reader((mod.path / "logs" / self._log_name).read_bytes()).parse()
            diffs.append(
                {
                    file: pio.list("param_root").list(file)
                    for i, file in pio.list("param_root")
                    .object("FileTable")
                    .params.items()
                }
            )
            del pio
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                pio = aamp.Reader((opt / "logs" / self._log_name).read_bytes()).parse()
                diffs.append(
                    {
                        file: pio.list("param_root").list(file)
                        for i, file in pio.list("param_root")
                        .object("FileTable")
                        .params.items()
                    }
                )
                del pio
        return diffs

    def get_all_diffs(self):
        aamp_diffs = {}
        for mod in util.get_installed_mods():
            mod_diffs = self.get_mod_diff(mod)
            for mod_diff in mod_diffs:
                for file in [
                    diff
                    for diff in mod_diff
                    if not self._options.get("only_these", False)
                ]:
                    if file not in aamp_diffs:
                        aamp_diffs[file] = []
                    aamp_diffs[file].append(mod_diff[file])
        return aamp_diffs

    def consolidate_diffs(self, diffs: list):
        consolidated_diffs = {}
        for file, diff_list in diffs.items():
            nest = reduce(
                lambda res, cur: {cur: res}, reversed(file.split("//")), diff_list
            )
            util.dict_merge(consolidated_diffs, nest)
        return consolidated_diffs

    def perform_merge(self):
        print("Loading deep merge data...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No deep merge necessary.")
            return
        if (util.get_master_modpack_dir() / "logs" / "rstb.log").exists():
            (util.get_master_modpack_dir() / "logs" / "rstb.log").unlink()
        merge_log = util.get_master_modpack_dir() / "logs" / "deepmerge.log"
        old_merges = []
        if merge_log.exists():
            if "only_these" in self._options:
                old_merges = merge_log.read_text().splitlines()
            merge_log.unlink()
        del old_merges

        print("Performing deep merge...")
        pool = self._pool or multiprocessing.Pool()
        pool.map(partial(threaded_merge), diffs.items())
        if not self._pool:
            pool.close()
            pool.join()

        (util.get_master_modpack_dir() / "logs").mkdir(parents=True, exist_ok=True)
        with merge_log.open("w", encoding="utf-8") as l_file:
            for file_type in diffs:
                for file in diffs[file_type]:
                    l_file.write(f"{file}\n")
                    if "only_these" in self._options and file in old_merges:
                        old_merges.remove(file)
            if "only_these" in self._options:
                for file in old_merges:
                    l_file.write(f"{file}\n")
        del diffs

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_affected(mod)
