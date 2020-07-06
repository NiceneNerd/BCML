"""Provides functions for diffing and merging SARC packs"""
# pylint: disable=unsupported-assignment-operation
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import json
from multiprocessing import Pool
from pathlib import Path
from typing import List, Union

import oead

from bcml import util, mergers

SPECIAL = {
    "GameData/gamedata.ssarc",
    "GameData/savedataformat.ssarc",
    # "Layout/Common.sblarc", We'll try doing this
    "Terrain/System/tera_resource.Nin_NX_NVN.release.ssarc",
}

EXCLUDE_EXTS = {".sbeventpack"}


def merge_sarcs(file_name: str, sarcs: List[Union[Path, bytes]]) -> (str, bytes):
    opened_sarcs: List[oead.Sarc] = []
    if "Bootup.pack" in file_name:
        print()
    if isinstance(sarcs[0], Path):
        for i, sarc_path in enumerate(sarcs):
            sarcs[i] = sarc_path.read_bytes()
    for sarc_bytes in sarcs:
        sarc_bytes = util.unyaz_if_needed(sarc_bytes)
        try:
            opened_sarcs.append(oead.Sarc(sarc_bytes))
        except (ValueError, RuntimeError, oead.InvalidDataError):
            continue

    all_files = {
        file.name for open_sarc in opened_sarcs for file in open_sarc.get_files()
    }
    nested_sarcs = {}
    new_sarc = oead.SarcWriter(
        endian=oead.Endianness.Big
        if util.get_settings("wiiu")
        else oead.Endianness.Little
    )
    files_added = set()

    for opened_sarc in reversed(opened_sarcs):
        for file in [f for f in opened_sarc.get_files() if f.name not in files_added]:
            file_data = oead.Bytes(file.data)
            if util.is_file_modded(
                file.name.replace(".s", "."), file_data, count_new=True
            ):
                if (
                    not file.name[file.name.rindex(".") :]
                    in util.SARC_EXTS - EXCLUDE_EXTS
                ) or file.name in SPECIAL:
                    new_sarc.files[file.name] = file_data
                    files_added.add(file.name)
                else:
                    if file.name not in nested_sarcs:
                        nested_sarcs[file.name] = []
                    nested_sarcs[file.name].append(util.unyaz_if_needed(file_data))
    util.vprint(set(nested_sarcs.keys()))
    for file, sarcs in nested_sarcs.items():
        if not sarcs:
            continue
        merged_bytes = merge_sarcs(file, sarcs)[1]
        if Path(file).suffix.startswith(".s") and not file.endswith(".sarc"):
            merged_bytes = util.compress(merged_bytes)
        new_sarc.files[file] = merged_bytes
        files_added.add(file)
    for file in [file for file in all_files if file not in files_added]:
        for opened_sarc in [
            open_sarc
            for open_sarc in opened_sarcs
            if (file in [f.name for f in open_sarc.get_files()])
        ]:
            new_sarc.files[file] = oead.Bytes(opened_sarc.get_file(file).data)
            break

    if "Bootup.pack" in file_name:
        for merger in [
            merger() for merger in mergers.get_mergers() if merger.is_bootup_injector()
        ]:
            inject = merger.get_bootup_injection()
            if not inject:
                continue
            file, data = inject
            new_sarc.files[file] = data

    return (file_name, bytes(new_sarc.write()[1]))


class PackMerger(mergers.Merger):
    """ A merger for modified pack files """

    NAME: str = "packs"

    def __init__(self):
        super().__init__("packs", "Merges modified files within SARCs", "packs.json", {})

    def can_partial_remerge(self):
        return True

    def get_mod_affected(self, mod):
        return self.get_mod_diff(mod)

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        print("Finding modified SARCs...")
        packs = {}
        for file in [
            file
            for file in modded_files
            if isinstance(file, Path) and file.suffix in util.SARC_EXTS
        ]:
            canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
            if canon and not any(
                ex in file.name
                for ex in ["Dungeon", "Bootup_", "AocMainField", "beventpack"]
            ):
                packs[canon] = file.relative_to(mod_dir).as_posix()
        return packs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        (mod_dir / "logs" / self._log_name).write_text(
            json.dumps(diff_material, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_mod_diff(self, mod: util.BcmlMod):
        diffs = set()
        if self.is_mod_logged(mod):
            diffs |= {
                Path(path.replace("\\", "/")).as_posix()
                for _, path in json.loads(
                    (mod.path / "logs" / self._log_name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                ).items()
            }
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                diffs |= {
                    Path(path.replace("\\", "/")).as_posix()
                    for _, path in json.loads(
                        (opt / "logs" / self._log_name).read_text(encoding="utf-8"),
                        encoding="utf-8",
                    ).items()
                }
        return diffs

    def get_all_diffs(self):
        diffs = {}
        for mod in util.get_installed_mods():
            diffs[mod] = self.get_mod_diff(mod)
        return diffs

    def consolidate_diffs(self, diffs):
        all_sarcs = set()
        all_diffs = {}
        for mod in sorted(diffs.keys(), key=lambda mod: mod.priority):
            all_sarcs |= set(diffs[mod])
        for modded_sarc in all_sarcs:
            for mod, diff in diffs.items():
                if modded_sarc in diff:
                    if not modded_sarc in all_diffs:
                        all_diffs[modded_sarc] = []
                    if (mod.path / modded_sarc).exists():
                        all_diffs[modded_sarc].append(mod.path / modded_sarc)
        util.vprint("All SARC diffs:")
        util.vprint(all_diffs)
        return all_diffs

    @util.timed
    def perform_merge(self):
        print("Loading modded SARC list...")
        sarcs = {
            s: ss for s, ss in self.consolidate_diffs(self.get_all_diffs()).items() if ss
        }
        if "only_these" in self._options:
            for sarc_file in self._options["only_these"]:
                master_path = util.get_master_modpack_dir() / sarc_file
                if master_path.exists():
                    master_path.unlink()
            for sarc_file in [
                file for file in sarcs if file not in self._options["only_these"]
            ]:
                del sarcs[sarc_file]
        else:
            for file in [
                file
                for file in util.get_master_modpack_dir().rglob("**/*")
                if file.suffix in util.SARC_EXTS
            ]:
                file.unlink()
        for sarc_file in sarcs:
            try:
                sarcs[sarc_file].insert(0, util.get_game_file(sarc_file))
            except FileNotFoundError:
                continue
        if not sarcs:
            print("No SARC merging necessary")
            return
        print(f"Merging {len(sarcs)} SARC files...")
        pool = self._pool or Pool()
        results = pool.starmap(merge_sarcs, sarcs.items())
        for result in results:
            file, file_data = result
            output_path = util.get_master_modpack_dir() / file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.startswith(".s"):
                file_data = util.compress(file_data)
            output_path.write_bytes(file_data)
        if not self._pool:
            pool.close()
            pool.join()
        print("Finished merging SARCs")

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_affected(mod)
