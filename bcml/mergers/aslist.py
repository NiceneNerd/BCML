from functools import reduce, partial
from multiprocessing import Pool
from pathlib import Path
from typing import Union, List, Set, ByteString, Optional, Dict, Any

from oead.aamp import ParameterIO, ParameterList, ParameterObject, Parameter
from oead import Sarc, SarcWriter, InvalidDataError, FixedSafeString64, FixedSafeString32
from bcml import util, mergers

HANDLES = {".baslist"}


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


def cfdefs_to_dict(
    cfdefs_plist: ParameterList
) -> Dict[str, Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]]:
    d: Dict[str, Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]] = {}
    for _, plist in cfdefs_plist.lists.items():
        cfdef = cfdef_to_dict(plist)
        d[str(plist.objects["CFPre"].params["Name"].v)] = cfdef
    return d


def cfdef_to_dict(
    cfdef_plist: ParameterList
) -> Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]:
    cfdef: Dict[str, Union[List[str], Dict[str, Dict[str, float]]]] = {}
    if "CFExcepts" in cfdef_plist.objects:
        l = []
        for _, param in cfdef_plist.objects["CFExcepts"].items():
            l.append(str(param.v))
        cfdef["CFExcepts"] = l
    if "CFPosts" in cfdef_plist.lists:
        cfposts = {}
        for _, pobj in cfdef_plist.lists["CFPosts"].items():
            cfpost = {
                "Frame": pobj.params["Frame"].v,
                "StartFrameRate": pobj.params["StartFrameRate"].v
            }
            cfposts[str(pobj.params["Name"].v)] = cfpost
        cfdef["CFPosts"] = cfposts
    return cfdef


def dict_to_cfdefs(
    d: Dict[str, Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]]
) -> ParameterList:
    cfdefs = ParameterList()
    for idx, (cfdef_name, cfdef_dict) in enumerate(d.items()):
        cfdef = dict_to_cfdef(cfdef_name, cfdef_dict)
        cfdefs.lists[f"CFDefine_{idx}"] = cfdef
    return cfdefs


def dict_to_cfdef(
    cfpre_name: str,
    cfdef_dict: Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]
) -> ParameterList:
    cfdef = ParameterList()
    cfpre = ParameterObject()
    cfpre.params["Name"] = Parameter(FixedSafeString32(cfpre_name))
    cfdef.objects["CFPre"] = cfpre
    for _, val in cfdef_dict.items():
        if isinstance(val, list):
            cfexcepts = ParameterObject()
            for i, except_name in enumerate(val):
                cfexcepts.params[f"Name_{i}"] = Parameter(
                    FixedSafeString32(except_name)
                )
            cfdef.objects["CFExcepts"] = cfexcepts
            continue
        cfposts = ParameterList()
        for i, (post_name, post) in enumerate(val.items()):
            cfpost = ParameterObject()
            cfpost.params["Name"] = Parameter(FixedSafeString32(post_name))
            for prop_name, prop_val in post.items():
                cfpost.params[prop_name] = Parameter(prop_val)
            cfposts.objects[f"CFPost_{i}"] = cfpost
        cfdef.lists["CFPosts"] = cfposts
    return cfdef


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
        def diff_cfdefine(
            cfdef: Dict[str, Union[List[str], Dict[str, Dict[str, float]]]],
            ref_cfdef: Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]
        ) -> Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]:
            d: Dict[str, Union[List[str], Dict[str, Dict[str, float]]]] = {}
            for key, val in cfdef.items():
                if key not in ref_cfdef:
                    d[key] = val
                    continue
                if isinstance(val, list):
                    d[key] = val - ref_cfdef[key]
                    continue
                tmp = {}
                for name, prop in d[key].items():
                    if name not in ref_cfdef[key]:
                        tmp = prop
                        continue
                    tmp2 = {}
                    for param, param_val in prop.items():
                        if (
                            param not in ref_cfdef[key][name] or
                            not param_val == ref_cfdef[key][name][param]
                        ):
                            tmp2[param] = param_val
                    if tmp2:
                        tmp[name] = tmp2
                if tmp:
                    d[key] = tmp
            return d

        diffs: Dict[str, Dict[str, Union[List[str], Dict[str, Dict[str, float]]]]] = {}
        defs = cfdefs_to_dict(cfdefs)
        ref_defs = cfdefs_to_dict(ref_cfdefs)
        for name, cfdef in defs.items():
            tmp = {}
            if name in ref_defs:
                tmp2 = diff_cfdefine(cfdef, ref_defs[name])
                if tmp2:
                    tmp = tmp2
            else:
                tmp = cfdef
            if tmp:
                diffs[name] = tmp
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
        bfres: Set[str] = set()
        for _, pobj in plist.objects.items():
            bfres.add(str(pobj.params["Anim"].v))
        for _, other_pobj in other_plist.objects.items():
            bfres.add(str(other_pobj.params["Anim"].v))
        for i, v in enumerate(bfres):
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
            defs[str(other_pobj.params["Name"].v)] = other_pobj.params["Filename"].v
        new_idx = len(listing)
        for k, v in defs.items():
            if k in listing:
                key = f"ASDefine_{listing[k]}"
            else:
                key = f"ASDefine_{new_idx}"
                plist.objects[key] = ParameterObject()
                plist.objects[key].params["Name"] = Parameter(FixedSafeString64(k))
                new_idx += 1
            plist.objects[key].params["Filename"] = Parameter(v)
    
    def merge_cfdefines(plist: ParameterList, other_plist: ParameterList):
        cfdef_diff = cfdefs_to_dict(other_plist)
        listing: Dict[str, int] = {}
        for i, (_, cfdef) in enumerate(plist.lists.items()):
            listing[str(cfdef.objects["CFPre"].params["Name"].v)] = i
        new_idx = len(listing)
        for cfpre, def_dict in cfdef_diff.items():
            if not cfpre in listing:
                key = f"CFDefine_{new_idx}"
                plist.lists[key] = dict_to_cfdef(cfpre, def_dict)
                new_idx += 1
                continue
            key = f"CFDefine_{listing[cfpre]}"
            for _, def_vals in def_dict.items():
                if isinstance(def_vals, list):
                    except_idx = 0
                    if "CFExcepts" in plist.lists[key].objects:
                        cfexcepts = plist.lists[key].objects["CFExcepts"]
                        except_idx = len(cfexcepts.params)
                        # old log compatibility
                        vanilla_excepts = []
                        for _, cfexcept in cfexcepts.params.items():
                            vanilla_excepts.append(str(cfexcept.v))
                        def_vals = def_vals - vanilla_excepts
                        # end old log compatibility
                    else:
                        cfexcepts = ParameterObject()
                        plist.lists[key].objects["CFExcepts"] = cfexcepts
                    for i, cfexcept in enumerate(def_vals):
                        except_key = f"Name_{except_idx + i}"
                        cfexcepts.params[except_key] = Parameter(
                            FixedSafeString32(cfexcept)
                        )
                    continue
                post_idx = 0
                if "CFPosts" in plist.lists[key].lists:
                    cfposts = plist.lists[key].lists["CFPosts"]
                    post_idx = len(cfposts.objects)
                else:
                    cfposts = ParameterList()
                    plist.lists[key].lists["CFPosts"] = cfposts
                posts_listing: Dict[str, int] = {}
                for i, (_, cfpost) in enumerate(cfposts.objects.items()):
                    posts_listing[str(cfpost.params["Name"].v)] = i
                for post_name, post in def_vals.items():
                    if not post_name in posts_listing:
                        key = f"CFPost_{post_idx}"
                        cfposts.objects[key] = ParameterObject()
                        cfposts.objects[key].params["Name"] = Parameter(
                            FixedSafeString32(post_name)
                        )
                        for post_key, post_val in post.items():
                            cfposts.objects[key].params[post_key] = Parameter(post_val)
                        post_idx += 1
                        continue
                    cfpost = cfposts.objects[f"CFPost_{posts_listing[post_name]}"]
                    for post_key, post_val in post.items():
                        cfpost.params[post_key] = Parameter(post_val)


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
