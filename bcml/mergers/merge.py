from functools import reduce, partial
from multiprocessing import Pool
from pathlib import Path
from typing import Union, List, ByteString, Optional, Dict, Any

from oead.aamp import ParameterIO, ParameterList, ParameterObject, Parameter
from oead import Sarc, SarcWriter, InvalidDataError
from bcml import util, mergers

HANDLED = {".bdrop", ".bshop", ".baslist"}


def get_aamp_diffs(file: str, tree: Union[dict, list], tmp_dir: Path) -> Optional[dict]:
    try:
        ref_sarc = Sarc(util.unyaz_if_needed(util.get_game_file(file).read_bytes()))
    except (FileNotFoundError, InvalidDataError, ValueError, RuntimeError) as err:
        util.vprint(f"{file} ignored on stock side, cuz {err}")
        return None
    try:
        sarc = Sarc(util.unyaz_if_needed((tmp_dir / file).read_bytes()))
    except (FileNotFoundError, InvalidDataError, ValueError, RuntimeError):
        util.vprint(f"{file} corrupt, ignored")
        return None
    diffs = _get_diffs_from_sarc(sarc, ref_sarc, tree, file)
    del sarc
    del ref_sarc
    return diffs


def _get_diffs_from_sarc(sarc: Sarc, ref_sarc: Sarc, edits: dict, path: str) -> dict:
    diffs = {}
    for file, edits in edits.items():
        if edits:
            try:
                rsub_sarc = Sarc(util.unyaz_if_needed(ref_sarc.get_file(file).data))
            except (AttributeError, InvalidDataError, ValueError, RuntimeError) as err:
                util.vprint(f'Skipping "{path}//{file}", {err}')
                continue
            sub_sarc = Sarc(util.unyaz_if_needed(sarc.get_file(file).data))
            diffs.update(
                _get_diffs_from_sarc(sub_sarc, rsub_sarc, edits, path + "//" + file)
            )
            del sub_sarc
            del rsub_sarc
        else:
            full_path = f"{path}//{file}"
            try:
                ref_pio = ParameterIO.from_binary(ref_sarc.get_file(file).data)
            except AttributeError:
                continue
            try:
                pio = ParameterIO.from_binary(sarc.get_file(file).data)
            except AttributeError as err:
                raise ValueError(
                    f"Failed to read nested file:\n{path}//{file}"
                ) from err
            except (ValueError, RuntimeError, InvalidDataError) as err:
                raise ValueError(f"Failed to parse AAMP file:\n{path}//{file}")
            diffs.update({full_path: get_aamp_diff(pio, ref_pio)})
    return diffs


def get_aamp_diff(pio: ParameterIO, ref_pio: ParameterIO) -> ParameterList:
    def diff_plist(
        plist: Union[ParameterList, ParameterIO],
        ref_plist: Union[ParameterIO, ParameterList],
    ) -> ParameterList:
        diff = ParameterList()
        for key, sublist in plist.lists.items():
            if key not in ref_plist.lists:
                diff.lists[key] = sublist
            elif ref_plist.lists[key] != sublist:
                diff.lists[key] = diff_plist(sublist, ref_plist.lists[key])
        for key, obj in plist.objects.items():
            if key not in ref_plist.objects:
                diff.objects[key] = obj
            elif ref_plist.objects[key] != obj:
                diff.objects[key] = diff_pobj(obj, ref_plist.objects[key])
        return diff

    def diff_pobj(pobj: ParameterObject, ref_pobj: ParameterObject) -> ParameterObject:
        diff = ParameterObject()
        for param, value in pobj.params.items():
            if param not in ref_pobj.params or ref_pobj.params[param] != value:
                diff.params[param] = value
        return diff

    return diff_plist(pio, ref_pio)


def merge_plists(
    plist: Union[ParameterList, ParameterIO],
    other_plist: Union[ParameterList, ParameterIO],
    file_table: bool = False,
):
    def merge_pobj(pobj: ParameterObject, other_pobj: ParameterObject):
        for param, value in other_pobj.params.items():
            pobj.params[param] = value

    for key, sublist in other_plist.lists.items():
        if key in plist.lists:
            merge_plists(plist.lists[key], sublist)
        else:
            plist.lists[key] = sublist
    for key, obj in other_plist.objects.items():
        if key in plist.objects:
            if key != "FileTable" or not file_table:
                merge_pobj(plist.objects[key], obj)
            else:
                file_list = {f.v for i, f in plist.objects[key].params.items()} | {
                    f.v for i, f in other_plist.objects[key].params.items()
                }
                for i, file in enumerate({f for f in file_list if f}):
                    plist.objects[key].params[f"File{i}"] = file
        else:
            plist.objects[key] = obj


def merge_aamp_files(file: str, tree: dict):
    try:
        base_file = util.get_game_file(file)
    except FileNotFoundError:
        util.vprint(f"Skipping {file}, not found in dump")
        return
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    try:
        sarc = Sarc(util.unyaz_if_needed(base_file.read_bytes()))
    except (ValueError, InvalidDataError, RuntimeError):
        return
    new_data = _merge_in_sarc(sarc, tree)
    if base_file.suffix.startswith(".s") and base_file.suffix != ".ssarc":
        new_data = util.compress(new_data)
    (util.get_master_modpack_dir() / file).parent.mkdir(parents=True, exist_ok=True)
    (util.get_master_modpack_dir() / file).write_bytes(bytes(new_data))


def _merge_in_sarc(sarc: Sarc, edits: dict) -> ByteString:
    new_sarc = SarcWriter.from_sarc(sarc)
    for file, stuff in edits.items():
        if isinstance(stuff, dict):
            try:
                if file not in {f.name for f in sarc.get_files()}:
                    raise FileNotFoundError(
                        f"Could not find nested file {file} in SARC"
                    )
                sub_sarc = Sarc(util.unyaz_if_needed(sarc.get_file(file).data))
            except (
                InvalidDataError,
                ValueError,
                AttributeError,
                RuntimeError,
                FileNotFoundError,
            ):
                util.vprint(f"Couldn't merge into nested SARC {file}")
                continue
            nsub_bytes = _merge_in_sarc(sub_sarc, stuff)
            new_sarc.files[file] = (
                util.compress(nsub_bytes)
                if file[file.rindex(".") :].startswith(".s")
                else nsub_bytes
            )
        elif isinstance(stuff, ParameterList):
            try:
                if file not in {f.name for f in sarc.get_files()}:
                    raise FileNotFoundError(
                        f"Could not find nested file {file} in SARC"
                    )
                pio = ParameterIO.from_binary(sarc.get_file(file).data)
            except (
                AttributeError,
                ValueError,
                InvalidDataError,
                FileNotFoundError,
            ) as err:
                util.vprint(f"Couldn't open {file}: {err}")
                continue
            merge_plists(pio, stuff)
            new_sarc.files[file] = pio.to_binary()
    return new_sarc.write()[1]


class DeepMerger(mergers.Merger):
    NAME: str = "aamp"

    def __init__(self):
        super().__init__(
            "AAMP merger",
            "Merges changes to arbitrary AAMP files",
            "deepmerge.aamp",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        print("Detecting general changes to AAMP files...")
        aamps = {
            m
            for m in modded_files
            if isinstance(m, str)
            and m[m.rindex(".") :] in (util.AAMP_EXTS - HANDLED)
            and "Dummy" not in m
        }
        if not aamps:
            return None

        consolidated: Dict[str, Any] = {}
        for aamp in aamps:
            util.dict_merge(
                consolidated,
                reduce(
                    lambda res, cur: {cur: res if res is not None else {}},  # type: ignore
                    reversed(aamp.split("//")),
                    None,
                ),
            )
        this_pool = self._pool or Pool(maxtasksperchild=500)
        results = this_pool.starmap(
            partial(get_aamp_diffs, tmp_dir=mod_dir), list(consolidated.items())
        )
        if not self._pool:
            this_pool.close()
            this_pool.join()
        del consolidated
        del aamps

        diffs = ParameterIO()
        diffs.objects["FileTable"] = ParameterObject()
        i: int = 0
        for file, diff in sorted(
            (k, v) for r in [r for r in results if r is not None] for k, v in r.items()
        ):
            diffs.objects["FileTable"].params[f"File{i}"] = Parameter(file)
            diffs.lists[file] = diff
            i += 1
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_bytes(diff_material.to_binary())
        del diff_material

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = None
        if self.is_mod_logged(mod):
            diff = ParameterIO.from_binary(
                (mod.path / "logs" / self._log_name).read_bytes()
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                if not diff:
                    diff = ParameterIO()
                merge_plists(
                    diff,
                    ParameterIO.from_binary(
                        (opt / "logs" / self._log_name).read_bytes()
                    ),
                    True,
                )
        return diff

    def get_all_diffs(self):
        diffs = None
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                if not diffs:
                    diffs = ParameterIO()
                merge_plists(diffs, diff, True)
        return diffs

    def consolidate_diffs(self, diffs: ParameterIO):
        if not diffs:
            return None
        consolidated: Dict[str, Any] = {}
        for _, file in diffs.objects["FileTable"].params.items():
            try:
                util.dict_merge(
                    consolidated,
                    reduce(
                        lambda res, cur: {cur: res},  # type: ignore
                        reversed(file.v.split("//")),
                        diffs.lists[file.v],
                    ),
                )
            except KeyError:
                util.vprint(diffs)
                raise Exception(f"{_}: {file} in diff lists: {file.v in diffs.lists}")
        return consolidated

    @util.timed
    def perform_merge(self):
        print("Loading deep merge logs...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No deep merge needed")
            return
        pool = self._pool or Pool(maxtasksperchild=500)
        pool.starmap(merge_aamp_files, diffs.items())
        if not self._pool:
            pool.close()
            pool.join()
        print("Finished deep merge")

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod):
        diff = self.get_mod_diff(mod)
        if not diff:
            return set()
        return set(file.v for _, file in diff.objects["FileTable"].params.items())
