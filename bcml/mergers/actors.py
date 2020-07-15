# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from pathlib import Path
from typing import List, Union
from zlib import crc32

import oead

from bcml import util, mergers
from bcml.util import BcmlMod


def get_stock_actorinfo() -> oead.byml.Hash:
    actorinfo = util.get_game_file("Actor/ActorInfo.product.sbyml")
    return oead.byml.from_binary(util.decompress(actorinfo.read_bytes()))


class ActorInfoMerger(mergers.Merger):
    NAME: str = "actors"

    def __init__(self):
        super().__init__(
            "actor info", "Merges changes to ActorInfo.product.byml", "actorinfo.yml", {},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        try:
            actor_file = next(
                iter(
                    [
                        file
                        for file in modded_files
                        if Path(file).name == "ActorInfo.product.sbyml"
                    ]
                )
            )
        except StopIteration:
            return {}
        print("Detecting modified actor info entries...")
        data = util.decompress(actor_file.read_bytes())
        try:
            actorinfo = oead.byml.from_binary(data)
        except oead.InvalidDataError:
            data = bytearray(data)
            data[3] = 2
            try:
                actorinfo = oead.byml.from_binary(data)
            except oead.InvalidDataError as err:
                raise ValueError("This mod contains a corrupt actor info file.") from err
        del actor_file
        stock_actorinfo = get_stock_actorinfo()
        stock_actors = {actor["name"]: actor for actor in stock_actorinfo["Actors"]}
        del stock_actorinfo
        diff = oead.byml.Hash(
            {
                **{
                    str(crc32(actor["name"].encode("utf8"))): actor
                    for actor in actorinfo["Actors"]
                    if actor["name"] not in stock_actors
                },
                **{
                    str(crc32(actor["name"].encode("utf8"))): {
                        key: value
                        for key, value in actor.items()
                        if (
                            key not in stock_actors[actor["name"]]
                            or value != stock_actors[actor["name"]][key]
                        )
                    }
                    for actor in actorinfo["Actors"]
                    if actor["name"] in stock_actors
                    and actor != stock_actors[actor["name"]]
                },
            }
        )
        del actorinfo
        del stock_actors
        return diff

    def log_diff(self, mod_dir: Path, diff_material: Union[oead.byml.Hash, list]):
        if isinstance(diff_material, List):
            diff_material: oead.byml.Hash = self.generate_diff(Path, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )

    def get_mod_diff(self, mod: BcmlMod):
        diffs = {}
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
        all_diffs = {}
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        util.vprint("All actor info diffs:")
        util.vprint(oead.byml.to_text(all_diffs))
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

        print("Loading unmodded actor info...")
        actorinfo = get_stock_actorinfo()
        stock_actors = {
            crc32(actor["name"].encode("utf8")): actor for actor in actorinfo["Actors"]
        }

        print("Merging changes...")
        new_hashes = set()
        for actor_hash, actor_info in modded_actors.items():
            if isinstance(actor_hash, str):
                actor_hash = int(actor_hash)
            if actor_hash in stock_actors:
                util.dict_merge(
                    stock_actors[actor_hash], actor_info, overwrite_lists=True
                )
            else:
                actorinfo["Actors"].append(actor_info)
                new_hashes.add(actor_hash)

        print("Sorting new actor info...")
        actorinfo["Hashes"] = oead.byml.Array(
            [
                oead.S32(x) if x < 2147483648 else oead.U32(x)
                for x in sorted(new_hashes | set(stock_actors.keys()))
            ]
        )
        try:
            actorinfo["Actors"] = sorted(
                actorinfo["Actors"], key=lambda x: crc32(x["name"].encode("utf-8"))
            )
        except KeyError as err:
            if str(err) == "":
                raise RuntimeError(
                    "Your actor info mods could not be merged. "
                    "This usually indicates a corrupt game dump."
                ) from err
            else:
                raise

        print("Saving new actor info...")
        actor_path.parent.mkdir(parents=True, exist_ok=True)
        actor_path.write_bytes(
            util.compress(
                oead.byml.to_binary(actorinfo, big_endian=util.get_settings("wiiu"))
            )
        )
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
