# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from pathlib import Path
from typing import List, Union, Dict
from zlib import crc32

import oead

from bcml import util, mergers
from bcml.util import BcmlMod
from bcml import bcml as rsext


def get_stock_actorinfo() -> oead.byml.Hash:
    actorinfo = util.get_game_file("Actor/ActorInfo.product.sbyml")
    return oead.byml.from_binary(util.decompress(actorinfo.read_bytes()))


class ActorInfoMerger(mergers.Merger):
    NAME: str = "actors"

    def __init__(self):
        super().__init__(
            "actor info",
            "Merges changes to ActorInfo.product.byml",
            "actorinfo.yml",
            {},
        )

    @util.timed
    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        try:
            actor_file: Path = next(
                iter(
                    [
                        file
                        for file in modded_files
                        if isinstance(file, Path)
                        and file.name == "ActorInfo.product.sbyml"
                    ]
                )
            )
        except StopIteration:
            return None
        return rsext.mergers.actorinfo.diff_actorinfo(str(actor_file))

    def log_diff(self, mod_dir: Path, diff_material: Union[oead.byml.Hash, list]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_bytes(diff_material)

    def get_mod_diff(self, mod: BcmlMod):
        diffs: Dict[str, oead.Byml.Hash] = {}
        if self.is_mod_logged(mod):
            util.dict_merge(
                diffs,
                oead.byml.from_text(
                    (mod.path / "logs" / self._log_name).read_text(encoding="utf-8")
                ),
                overwrite_lists=True,
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diffs,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs: Dict[str, oead.Byml.Hash] = {}
        inst_sizes = {}
        for diff in diffs:
            for actor_hash, inst_size in [(h, a["instSize"].v) for h, a in diff.items() if "instSize" in a]:
                if inst_size > inst_sizes.get(actor_hash, 0):
                    inst_sizes[actor_hash] = inst_size
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        for actor_hash, inst_size in inst_sizes.items():
            all_diffs[actor_hash]["instSize"] = oead.S32(inst_size)
        return oead.byml.Hash(all_diffs)

    @util.timed
    def perform_merge(self):
        actor_path = (
            util.get_master_modpack_dir()
            / util.get_content_path()
            / "Actor"
            / "ActorInfo.product.sbyml"
        )
        print("Loading modded actor info...")
        modded_actors = self.consolidate_diffs(self.get_all_diffs())
        if not modded_actors:
            print("No actor info merging necessary.")
            if actor_path.exists():
                actor_path.unlink()
            return

        bin_data = oead.byml.to_binary(modded_actors, False)
        rsext.mergers.actorinfo.merge_actorinfo(bin_data)
        print("Actor info merged successfully")

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        log = {int(k): v for k, v in self.get_mod_diff(mod).items()}
        actors = get_stock_actorinfo()
        stock_names = {
            int(actors["Hashes"][i]): actors["Actors"][i]["name"]
            for i in range(len(actors["Hashes"]))
        }
        return {
            (stock_names[actor] if actor in stock_names else log[actor]["name"])
            for actor in log
        }
