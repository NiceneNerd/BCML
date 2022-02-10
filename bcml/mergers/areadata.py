import rstb
import oead

from functools import lru_cache
from pathlib import Path
from typing import List, Union
from bcml import mergers, util
from bcml.util import BcmlMod
from bcml.mergers import rstable


def get_stock_areadata() -> oead.byml.Hash:
    if not hasattr(get_stock_areadata, "areadata"):
        get_stock_areadata.areadata = oead.byml.to_text(
            oead.byml.Hash(
                {
                    str(area["AreaNumber"].v): area
                    for area in oead.byml.from_binary(
                        util.get_nested_file_bytes(
                            str(util.get_game_file("Pack/Bootup.pack"))
                            + "//Ecosystem/AreaData.sbyml",
                            unyaz=True,
                        )
                    )
                }
            )
        )
    return oead.byml.from_text(get_stock_areadata.areadata)


def get_modded_areadata(areadata: oead.byml.Array) -> oead.byml.Hash:
    stock_areadata = get_stock_areadata()
    mod_areadata = oead.byml.Hash(
        {str(area["AreaNumber"].v): area for area in areadata}
    )
    modified = oead.byml.Hash()
    try:
        for area_num in [
            k for k in mod_areadata if mod_areadata[k] != stock_areadata[k]
        ]:
            modified[area_num] = oead.byml.Hash(
                {
                    k: v
                    for k, v in mod_areadata[area_num].items()
                    if v != stock_areadata[area_num][k]
                }
            )
    except KeyError as err:
        raise RuntimeError(
            f"Invalid AreaData.sbyml. One or more areas missing key: {err.args}"
        )
    return modified


class AreaDataMerger(mergers.Merger):
    NAME: str = "areadata"

    def __init__(self):
        super().__init__(
            "area data",
            "Merges changes to AreaData.byml",
            "areadata.yml",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if (
            f"{util.get_content_path()}/Pack/Bootup.pack//Ecosystem/AreaData.sbyml"
            in modded_files
        ):
            print("Logging modded areadata...")
            bootup_sarc = oead.Sarc(
                (
                    mod_dir / util.get_content_path() / "Pack" / "Bootup.pack"
                ).read_bytes()
            )
            areadata = oead.byml.from_binary(
                util.decompress(bootup_sarc.get_file("Ecosystem/AreaData.sbyml").data)
            )
            diff = get_modded_areadata(areadata)
            del bootup_sarc
            del areadata
            return diff
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

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
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs: list):
        if not diffs:
            return {}
        all_diffs = oead.byml.Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        merged_areadata = util.get_master_modpack_dir() / "logs" / "areadata.byml"
        areadata_merge_log = util.get_master_modpack_dir() / "logs" / "areadata.log"

        print("Loading area data mods...")
        modded_areadata = self.consolidate_diffs(self.get_all_diffs())
        areadata_mod_hash = hash(str(modded_areadata))
        if not modded_areadata:
            print("No area data merging necessary")
            if merged_areadata.exists():
                merged_areadata.unlink()
                areadata_merge_log.unlink()
                try:
                    stock_areadata = util.get_nested_file_bytes(
                        (
                            str(util.get_game_file("Pack/Bootup.pack"))
                            + "//Ecosystem/AreaData.sbyml"
                        ),
                        unyaz=False,
                    )
                    util.inject_file_into_sarc(
                        "Ecosystem/AreaData.sbyml",
                        stock_areadata,
                        "Pack/Bootup.pack",
                    )
                except FileNotFoundError:
                    pass
            return
        if (
            areadata_merge_log.exists()
            and areadata_merge_log.read_text() == areadata_mod_hash
        ):
            print("No area data merging necessary")
            return

        new_areadata = get_stock_areadata()
        util.dict_merge(new_areadata, modded_areadata, overwrite_lists=True)

        print("Writing new area data...")
        areadata_bytes = oead.byml.to_binary(
            oead.byml.Array(
                [v for _, v in sorted(new_areadata.items(), key=lambda x: int(x[0]))]
            ),
            big_endian=util.get_settings("wiiu"),
        )
        del new_areadata
        util.inject_file_into_sarc(
            "Ecosystem/AreaData.sbyml",
            util.compress(areadata_bytes),
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        print("Saving area data merge log...")
        areadata_merge_log.parent.mkdir(parents=True, exist_ok=True)
        areadata_merge_log.write_text(str(areadata_mod_hash))
        merged_areadata.write_bytes(areadata_bytes)

        print("Updating RSTB...")
        rstb_size = rstb.SizeCalculator().calculate_file_size_with_ext(
            bytes(areadata_bytes), True, ".byml"
        )
        del areadata_bytes
        rstable.set_size("Ecosystem/AreaData.byml", rstb_size)

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "areadata.byml"
        if tmp_sarc.exists():
            return (
                "Ecosystem/AreaData.sbyml",
                util.compress(tmp_sarc.read_bytes()),
            )
        else:
            return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_diff(mod).keys()
