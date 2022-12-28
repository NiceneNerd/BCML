from functools import reduce, partial
from multiprocessing import Pool
from pathlib import Path
from typing import Union, List, Set, ByteString, Optional, Dict, Any

from oead.aamp import ParameterIO, ParameterList, ParameterObject, Parameter
from oead import Sarc, SarcWriter, InvalidDataError, FixedSafeString64, FixedSafeString32
from bcml import util, mergers

HANDLES = {".baslist"}


class CFDefine:
    def __init__(self, cfdef: ParameterList) -> None:
        self.name = str(cfdef.objects["CFPre"].params["Name"].v)
        self.excepts: List[str] = []
        self.posts: Dict[str, Dict[str, float]] = {}
        if "CFExcepts" in cfdef.objects:
            for _, except_val in cfdef.objects["CFExcepts"].params.items():
                self.excepts.append(str(except_val.v))
        if "CFPosts" in cfdef.lists:
            for _, cfpost in cfdef.lists["CFPosts"].objects.items():
                post_val: Dict[str, float] = {
                    "Frame": cfpost.params["Frame"].v,
                    "StartFrameRate": cfpost.params["StartFrameRate"].v
                }
                self.posts[str(cfpost.params["Name"].v)] = post_val

    def __eq__(self, __o: object) -> bool:
        if self is __o:
            return True
        if (
            not isinstance(__o, CFDefine) or
            not self.name == __o.name or
            not set(self.excepts) == set(__o.excepts) or
            not self.posts == __o.posts
        ):
            return False
        return True

    def to_plist(self) -> ParameterList:
        """Converts the CFDefine to an oead.aamp.ParameterList, for writing"""
        plist = ParameterList()
        cfpre = ParameterObject()
        cfpre.params["Name"] = Parameter(FixedSafeString32(self.name))
        plist.objects["CFPre"] = cfpre
        if self.excepts:
            cfexcepts = ParameterObject()
            for i, cfexcept in enumerate(self.excepts):
                cfexcepts.params[f"Name_{i}"] = Parameter(FixedSafeString32(cfexcept))
            plist.objects["CFExcepts"] = cfexcepts
        if self.posts:
            cfposts = ParameterList()
            for i, (post_name, post_params) in enumerate(self.posts.items()):
                cfpost = ParameterObject()
                cfpost.params["Name"] = Parameter(FixedSafeString32(post_name))
                for param_name, param in post_params.items():
                    cfpost.params[param_name] = Parameter(param)
                cfposts.objects[f"CFPost_{i}"] = cfpost
            plist.lists["CFPosts"] = cfposts
        return plist

    def diff_against(self, other) -> None:
        """Diffs self against other, removing any properties that self shares with other"""
        if self == other:
            self.excepts.clear()
            self.posts.clear()
        if not self.name == other.name:
            raise ValueError(f"CFDefine {self.name} was diffed against {other.name}")
        self.excepts = [item for item in self.excepts if item not in other.excepts]
        new_posts = {}
        for post_name, post_params in self.posts.items():
            if post_name not in other.posts:
                new_posts[post_name] = post_params
                continue
            for param_name, param_val in post_params.items():
                if not other.posts[post_name][param_name] == param_val:
                    if not post_name in new_posts:
                        new_posts[post_name] = {}
                    new_posts[post_name][param_name] == param_val
        self.posts = new_posts

    def update_from(self, other) -> None:
        """Updates self from other/merges other into self"""
        if not self.name == other.name:
            raise ValueError(f"CFDefine {self.name} was updated from {other.name}")
        tmp = dict.fromkeys(self.excepts)
        tmp.update(dict.fromkeys(other.excepts))
        self.excepts = tmp.keys()
        del tmp
        for post_name, post_params in other.posts.items():
            if post_name not in self.posts:
                self.posts[post_name] = post_params
                continue
            self.posts[post_name].update(post_params)

    def is_empty(self) -> bool:
        """Checks if the CFDefine has any data. To be used after diffing"""
        if self.excepts or self.posts:
            return False
        return True


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
                raise ValueError(f"Failed to parse AAMP file:\n{path}//{file}") from err
            diffs.update({full_path: get_aamp_diff(pio, ref_pio)})
    return diffs


def cfdefs_to_dict(cfdefs_plist: ParameterList) -> Dict[str, CFDefine]:
    d: Dict[str, CFDefine] = {}
    for _, plist in cfdefs_plist.lists.items():
        cfdef = CFDefine(plist)
        d[cfdef.name] = cfdef
    return d


def dict_to_cfdefs(d: Dict[str, CFDefine]) -> ParameterList:
    cfdefs = ParameterList()
    for i, (_, cfdef) in enumerate(d.items()):
        cfdefs.lists[f"CFDefine_{i}"] = cfdef.to_plist()
    return cfdefs


def get_aamp_diff(pio: ParameterIO, ref_pio: ParameterIO) -> ParameterList:
    def diff_plist(
        plist: Union[ParameterList, ParameterIO],
        ref_plist: Union[ParameterIO, ParameterList],
    ) -> ParameterList:
        diff = ParameterList()
        for key, sublist in plist.lists.items():
            if key.hash == 2777926231:  # "AddReses"
                diff.lists[key] = diff_addres(sublist, ref_plist.lists[key])
            elif key.hash == 3752287078:  # "ASDefines"
                diff.lists[key] = diff_asdefine(sublist, ref_plist.lists[key])
            elif key.hash == 3305786543:  # "CFDefines"
                diff.lists[key] = diff_cfdefines(sublist, ref_plist.lists[key])
            elif key not in ref_plist.lists:
                diff.lists[key] = sublist
            elif ref_plist.lists[key] != sublist:
                diff.lists[key] = diff_plist(sublist, ref_plist.lists[key])
        for key, obj in plist.objects.items():
            if key not in ref_plist.objects:
                diff.objects[key] = obj
            elif ref_plist.objects[key] != obj:
                diff.objects[key] = diff_pobj(obj, ref_plist.objects[key])
        return diff

    def diff_addres(addres: ParameterList, ref_addres: ParameterList) -> ParameterList:
        diff = ParameterList()
        bfres: List[str] = []
        for _, pobj in addres.objects.items():
            bfres.append(pobj.params["Anim"].v)
        for _, ref_pobj in ref_addres.objects.items():
            try:
                bfres.remove(ref_pobj.params["Anim"].v)
            except ValueError:
                continue
        for i, v in enumerate(bfres):
            key = f"AddRes_{i}"
            diff.objects[key] = ParameterObject()
            diff.objects[key].params["Anim"] = Parameter(v)
        return diff

    def diff_asdefine(asdef: ParameterList, ref_asdef: ParameterList) -> ParameterList:
        diff = ParameterList()
        defs: Dict[str, str] = {}
        for _, pobj in asdef.objects.items():
            defs[str(pobj.params["Name"].v)] = str(pobj.params["Filename"].v)
        for _, ref_pobj in ref_asdef.objects.items():
            key = str(ref_pobj.params["Name"].v)
            try:
                if defs[key] == str(ref_pobj.params["Filename"].v):
                    defs.pop(key)
            except (ValueError, KeyError):
                continue
        for i, (k, v) in enumerate(defs.items()):
            key = f"ASDefine_{i}"
            diff.objects[key] = ParameterObject()
            diff.objects[key].params["Name"] = Parameter(FixedSafeString64(k))
            diff.objects[key].params["Filename"] = Parameter(FixedSafeString64(v))
        return diff
    
    def diff_cfdefines(cfdefs: ParameterList, ref_cfdefs: ParameterList) -> ParameterList:
        diffs: Dict[str, CFDefine] = {}
        defs = cfdefs_to_dict(cfdefs)
        ref_defs = cfdefs_to_dict(ref_cfdefs)
        for name, cfdef in defs.items():
            if name in ref_defs:
                ref_def = ref_defs[name]
                if not cfdef == ref_def:
                    cfdef.diff_against(ref_def)
                    if not cfdef.is_empty():
                        diffs[name] = cfdef
        return dict_to_cfdefs(diffs)

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
    def merge_addres(plist: ParameterList, other_plist: ParameterList):
        bfres: Dict[str, Any] = {}
        for _, pobj in plist.objects.items():
            bfres[str(pobj.params["Anim"].v)] = None
        for _, other_pobj in other_plist.objects.items():
            bfres[str(other_pobj.params["Anim"].v)] = None
        for i, v in enumerate(bfres.keys()):
            key = f"AddRes_{i}"
            if not key in plist.objects:
                plist.objects[key] = ParameterObject()
            plist.objects[key].params["Anim"] = Parameter(FixedSafeString64(v))

    def merge_asdefine(plist: ParameterList, other_plist: ParameterList):
        listing: Dict[str, int] = {}
        defs: Dict[str, str] = {}
        for i, (_, pobj) in enumerate(plist.objects.items()):
            listing[str(pobj.params["Name"].v)] = i
        for _, other_pobj in other_plist.objects.items():
            defs[str(other_pobj.params["Name"].v)] = str(other_pobj.params["Filename"].v)
        new_idx = len(listing)
        for k, v in defs.items():
            if k in listing:
                key = f"ASDefine_{listing[k]}"
            else:
                key = f"ASDefine_{new_idx}"
                plist.objects[key] = ParameterObject()
                plist.objects[key].params["Name"] = Parameter(FixedSafeString64(k))
                new_idx += 1
            plist.objects[key].params["Filename"] = Parameter(FixedSafeString64(v))
    
    def merge_cfdefines(plist: ParameterList, other_plist: ParameterList):
        cfdef_diff = cfdefs_to_dict(other_plist)
        listing: Dict[str, int] = {}
        for i, (_, cfdef) in enumerate(plist.lists.items()):
            listing[str(cfdef.objects["CFPre"].params["Name"].v)] = i
        new_idx = len(listing)
        for cfdef_name, cfdef in cfdef_diff.items():
            if cfdef_name in listing:
                def_key = f"CFDefine_{listing[cfdef_name]}"
                vanilla_cfdef = CFDefine(plist.lists[def_key])
                vanilla_cfdef.update_from(cfdef)
                plist.lists[def_key] = vanilla_cfdef.to_plist()
                continue
            def_key = f"CFDefine_{new_idx}"
            plist.lists[def_key] = cfdef.to_plist()
            new_idx += 1

    def merge_pobj(pobj: ParameterObject, other_pobj: ParameterObject):
        for param, value in other_pobj.params.items():
            pobj.params[param] = value

    for key, sublist in other_plist.lists.items():
        if key.hash == 2777926231:  # "AddReses"
            merge_addres(plist.lists[key], sublist)
        elif key.hash == 3752287078:  # "ASDefines"
            merge_asdefine(plist.lists[key], sublist)
        elif key.hash == 3305786543:  # "CFDefines"
            merge_cfdefines(plist.lists[key], sublist)
        elif key in plist.lists:
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
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    else:
        try:
            base_file = util.get_game_file(file)
        except FileNotFoundError:
            util.vprint(f"Skipping {file}, not found in dump")
            return
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


class ASListMerger(mergers.Merger):
    NAME: str = "aslist"

    def __init__(self):
        super().__init__(
            "AS list merger",
            "Merges changes to animation lists",
            "aslist.aamp",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        print("Detecting general changes to AS lists...")
        aamps = {
            m
            for m in modded_files
            if isinstance(m, str) and m[m.rindex(".") :] in HANDLES
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
        this_pool = self._pool or util.start_pool()
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
        print("Loading AS list merge logs...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No AS list merge needed")
            return
        pool = self._pool or util.start_pool()
        pool.starmap(merge_aamp_files, diffs.items())
        if not self._pool:
            pool.close()
            pool.join()
        print("Finished AS list merge")

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod):
        diff = self.get_mod_diff(mod)
        if not diff:
            return set()
        return set(file.v for _, file in diff.objects["FileTable"].params.items())
