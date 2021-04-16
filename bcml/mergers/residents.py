"""Provides features for diffing and merging EventInfo.product.byml """
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from pathlib import Path
from typing import List, Union

import oead
import rstb
from bcml import util, mergers
from bcml.util import BcmlMod
from bcml.mergers import rstable
from oead.byml import Hash


def get_stock_residents() -> Hash:
    bootup_sarc = oead.Sarc(util.get_game_file("Pack/Bootup.pack").read_bytes())
    residents = oead.byml.from_binary(
        bytes(bootup_sarc.get_file("Actor/ResidentActors.byml").data)
    )
    return Hash({actor["name"]: actor for actor in residents})


class ResidentsMerger(mergers.Merger):
    NAME: str = "residents"

    def __init__(self):
        super().__init__(
            "resident actors",
            "Merges changes to ResidentActors.byml",
            "residents.yml",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        needle = (
            f"{util.get_content_path()}/Pack/Bootup.pack//Actor/ResidentActors.byml"
        )
        if needle not in modded_files:
            return {}
        bootup_sarc = oead.Sarc(
            (mod_dir / util.get_content_path() / "Pack" / "Bootup.pack").read_bytes()
        )
        mod_residents = Hash(
            {
                actor["name"]: actor
                for actor in oead.byml.from_binary(
                    bootup_sarc.get_file("Actor/ResidentActors.byml").data
                )
            }
        )
        stock_residents = get_stock_residents()
        diff = Hash(
            {
                actor: data
                for actor, data in mod_residents.items()
                if actor not in stock_residents or data != stock_residents[actor]
            }
        )
        for actor in {actor for actor in stock_residents if actor not in mod_residents}:
            data = oead.byml.from_text(oead.byml.to_text(stock_residents[actor]))
            data["remove"] = True
            diff[actor] = data
        return diff

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = oead.byml.Hash()
        if self.is_mod_logged(mod):
            diff = oead.byml.from_text(
                (mod.path / "logs" / self._log_name).read_text("utf-8")
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diff,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diff

    def get_all_diffs(self):
        diffs = []
        for m in util.get_installed_mods():
            diff = self.get_mod_diff(m)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs):
        if not diffs:
            return {}
        all_diffs = oead.byml.Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        merged_residents = util.get_master_modpack_dir() / "logs" / "residents.byml"
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            if merged_residents.exists():
                merged_residents.unlink()
                try:
                    stock_residents = util.get_nested_file_bytes(
                        (
                            str(util.get_game_file("Pack/Bootup.pack"))
                            + "//Actor/ResidentActors.byml"
                        ),
                        unyaz=False,
                    )
                    util.inject_file_into_sarc(
                        "Actor/ResidentActors.byml",
                        stock_residents,
                        "Pack/Bootup.pack",
                    )
                    del stock_residents
                except FileNotFoundError:
                    pass
            return

        residents = get_stock_residents()
        util.dict_merge(residents, diffs, overwrite_lists=True)
        residents = Hash(
            {actor: data for actor, data in residents.items() if "remove" not in data}
        )

        resident_bytes = oead.byml.to_binary(
            oead.byml.Array([data for _, data in residents.items()]),
            big_endian=util.get_settings("wiiu"),
        )
        del residents
        util.inject_file_into_sarc(
            "Actor/ResidentActors.byml",
            resident_bytes,
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        merged_residents.parent.mkdir(parents=True, exist_ok=True)
        merged_residents.write_bytes(resident_bytes)

        rstb_size = rstb.SizeCalculator().calculate_file_size_with_ext(
            resident_bytes, True, ".byml"
        )
        del resident_bytes
        rstable.set_size("Actor/ResidentActors.byml", rstb_size)

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "residents.byml"
        if tmp_sarc.exists():
            return (
                "Actor/ResidentActors.byml",
                util.compress(tmp_sarc.read_bytes()),
            )
        return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_diff(mod).keys()
