from fnmatch import fnmatch
import multiprocessing
import os
import sys
from copy import deepcopy
from functools import partial, reduce
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Union

import aamp
from aamp.parameters import ParameterList, ParameterIO, ParameterObject
import aamp.yaml_util
import aamp.converters
import bcml.rstable
import byml
import rstb
import rstb.util
import sarc
import wszst_yaz0
import yaml
from bcml import util, install
from bcml.util import BcmlMod
from byml import yaml_util
from diff_match_patch import diff_match_patch


def _byml_diff(base: dict, modded: dict) -> {}:
    diff = {}
    for key, value in modded.items():
        if key not in base:
            diff[key] = value
        elif value != base[key]:
            if isinstance(value, dict):
                diff[key] = _byml_diff(base[key], value)
            elif isinstance(value, list):
                diff[key] = [item for item in value if item not in base[key]]
            else:
                diff[key] = value
    return diff


def _aamp_diff(base: Union[ParameterIO, ParameterList],
               modded: Union[ParameterIO, ParameterList]) -> ParameterList:
    diffs = ParameterList()
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            diffs.lists[crc] = plist
        else:
            diff = _aamp_diff(base.lists[crc], plist)
            if len(diff.lists) > 0 or len(diff.objects) > 0:
                diffs.lists[crc] = diff
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            diffs.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            diff_obj = deepcopy(base_obj)
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or value != base_obj.params[param]:
                    changed = True
                    diff_obj.params[param] = value
            if changed:
                diffs.objects[crc] = diff_obj
    return diffs


def _aamp_merge(base: Union[ParameterIO, ParameterList],
               modded: Union[ParameterIO, ParameterList]) -> ParameterIO:
    merged = deepcopy(base)
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            merged.lists[crc] = plist
        else:
            merge = _aamp_merge(base.lists[crc], plist)
            if len(merge.lists) > 0 or len(merge.objects) > 0:
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


def get_byml_diff(file: Union[Path, str], tmp_dir: Path) -> str:
    """
    Diffs a modded BYML file from the stock game version

    :param file: The modded BYML file to diff
    :type file: :class:`typing.Union[:class:pathlib.Path, str]`
    :param tmp_dir: The temp directory containing the mod
    :type tmp_dir: :class:`pathlib.Path`
    :return: Returns a string representation of the BYML file diff
    """
    if isinstance(file, str):
        nests = file.split('//')
        mod_bytes = util.get_nested_file_bytes(file)
        ref_path = str(util.get_game_file(Path(nests[0]).relative_to(tmp_dir))) + '//' + '//'.join(nests[1:])
        ref_bytes = util.get_nested_file_bytes(ref_path)
    else:
        with file.open('rb') as mf:
            mod_bytes = mf.read()
        mod_bytes = util.unyaz_if_needed(mod_bytes)

        with util.get_game_file(file.relative_to(tmp_dir)).open('rb') as rf:
            ref_bytes = rf.read()
        ref_bytes = util.unyaz_if_needed(ref_bytes)

    dumper = yaml.CSafeDumper
    yaml_util.add_representers(dumper)

    mod_yml = byml.Byml(mod_bytes).parse()
    mod_str = StringIO()
    yaml.dump(mod_yml, mod_str, Dumper=dumper)
    mod_str = mod_str.getvalue()

    ref_yml = byml.Byml(ref_bytes).parse()
    ref_str = StringIO()
    yaml.dump(ref_yml, ref_str, Dumper=dumper)
    ref_str = ref_str.getvalue()

    dmp = diff_match_patch()
    patches = dmp.patch_make(ref_str, mod_str)
    return dmp.patch_toText(patches)


def get_aamp_diff(file: Union[Path, str], tmp_dir: Path):
    """
    Diffs a modded AAMP file from the stock game version

    :param file: The modded AAMP file to diff
    :type file: :class:`typing.Union[:class:pathlib.Path, str]`
    :param tmp_dir: The temp directory containing the mod
    :type tmp_dir: :class:`pathlib.Path`
    :return: Returns a string representation of the AAMP file diff
    """
    if isinstance(file, str):
        nests = file.split('//')
        mod_bytes = util.get_nested_file_bytes(file)
        ref_path = str(util.get_game_file(Path(nests[0]).relative_to(tmp_dir))) + '//' + '//'.join(nests[1:])
        ref_bytes = util.get_nested_file_bytes(ref_path)
    else:
        with file.open('rb') as mf:
            mod_bytes = mf.read()
        mod_bytes = util.unyaz_if_needed(mod_bytes)
        with util.get_game_file(file.relative_to(tmp_dir)).open('rb') as rf:
            ref_bytes = rf.read()
        ref_bytes = util.unyaz_if_needed(ref_bytes)

    ref_aamp = aamp.Reader(ref_bytes).parse()
    mod_aamp = aamp.Reader(mod_bytes).parse()

    return _aamp_diff(ref_aamp, mod_aamp)


def get_deepmerge_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that use deep merge """
    dmods = [mod for mod in util.get_installed_mods() if (mod.path / 'logs' / 'deepmerge.yml').exists()]
    return sorted(dmods, key=lambda mod: mod.priority)


def get_deepmerge_diffs() -> dict:
    """
    Gets the logged file diffs for installed deep merge mods

    :return: Returns a dict containing modified AAMP and BYML file paths and a list of diffs for each.
    :rtype: dict of str: dict of str: list of str
    """
    diffs = {
        'aamp': {},
        'byml': {}
    }
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    aamp.yaml_util.register_constructors(loader)
    for mod in get_deepmerge_mods():
        with (mod.path / 'logs' / 'deepmerge.yml').open('r', encoding='utf-8') as df:
            mod_diffs = yaml.load(df, Loader=loader)
            for file in mod_diffs['aamp']:
                if file not in diffs['aamp']:
                    diffs['aamp'][file] = []
                diffs['aamp'][file].append(mod_diffs['aamp'][file])
            for file in mod_diffs['byml']:
                if file not in diffs['byml']:
                    diffs['byml'][file] = []
                diffs['byml'][file].append(mod_diffs['byml'][file])
    for file_type, files in diffs.items():
        for file, items in list(files.items()):
            if len(items) < 2:
                del diffs[file_type][file]
    return diffs


def consolidate_diff_files(diffs: dict) -> dict:
    """ Consolidates the files which need to be deep merged to avoid any need to repeatedly open the same files. """
    consolidated_diffs = {}
    for file_type, files in diffs.items():
        consolidated_diffs[file_type] = {}
        for file, diff_list in files.items():
            nest = reduce(lambda res, cur: {cur: res}, reversed(file.split("//")), diff_list)
            util.dict_merge(consolidated_diffs[file_type], nest)
    return consolidated_diffs


def apply_patches(patches: List[str], base_text: str) -> (str, bool):
    """
    Patches a file and returns the patched text and an indication whether all patches applied successfully. If any
    part of patch in the list of patches fails, that patch is rolled back entirely, but any fullly successul patches
    are kept intact.

    :param patches: A list of text patches to apply.
    :type patches: str
    :param base_text: The test onto which the patches will be applied.
    :return: Returns a tuple containing the patched text and whether all patches applied successfully.
    :rtype: (str, bool)
    """
    dmp = diff_match_patch()
    patched_text = base_text
    for patch in patches:
        dmp_patch = dmp.patch_fromText(patch)
        tmp_text, failures = dmp.patch_apply(dmp_patch, patched_text)
        if False in failures:
            return patched_text, False
        else:
            patched_text = tmp_text
    return patched_text, True


def nested_patch(pack: sarc.SARC, nest: dict) -> (sarc.SARCWriter, dict):
    """
    Recursively patches deep merge files in a SARC

    :param pack: The SARC in which to recursively patch.
    :type pack: :class:`sarc.SARC`
    :param nest: A dict of nested patches to apply.
    :type nest: dict
    :return: Returns a new SARC with patches applied and a dict of any failed patches.
    :rtype: (:class:`sarc.SARCWriter`, dict, dict)
    """
    new_sarc = sarc.make_writer_from_sarc(pack)
    failures = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file_data(file).tobytes()
        yazd = file_bytes[0:4] == b'Yaz0'
        file_bytes = wszst_yaz0.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = sarc.SARC(file_bytes)
            new_sarc.delete_file(file)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + '//' + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = new_sub_sarc.get_bytes()
            new_sarc.add_file(file, new_bytes if not yazd else wszst_yaz0.compress(new_bytes))

        elif isinstance(stuff, list):
            try:
                if file_bytes[0:2] == b'BY' or file_bytes[0:2] == b'YB':
                    dumper = yaml.CDumper
                    yaml_util.add_representers(dumper)
                    base_byml = byml.Byml(file_bytes).parse()
                    str_buf = StringIO()
                    yaml.dump(base_byml, str_buf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                            default_flow_style=None)
                    del base_byml
                    base_text = str_buf.getvalue()
                    del str_buf

                    new_text, success = apply_patches(stuff, base_text)
                    if not success:
                        failures[file] = new_text
                    
                    loader = yaml.CSafeLoader
                    yaml_util.add_constructors(loader)
                    buf = BytesIO()
                    root = yaml.load(new_text, Loader=loader)
                    byml.Writer(root, True).write(buf)
                    del root
                    new_bytes = buf.getvalue() if not yazd else wszst_yaz0.compress(buf.getvalue())
                elif file_bytes[0:4] == b'AAMP':
                    aamp_contents = aamp.Reader(file_bytes).parse()
                    for change in stuff:
                        aamp_contents = _aamp_merge(aamp_contents, change)
                    aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else wszst_yaz0.compress(aamp_bytes)
                else:
                    raise ValueError('Wait, what the heck, we already checked this?!')
            except:
                new_bytes = pack.get_file_data(file).tobytes()
                print(f'Deep merging {file} failed. No changed were made.')

            new_sarc.delete_file(file)
            new_sarc.add_file(file, new_bytes)
    return new_sarc, failures


def get_merged_files() -> List[str]:
    log = util.get_master_modpack_dir() / 'logs' / 'deepmerge.log'
    if not log.exists():
        return []
    else:
        with log.open('r') as lf:
            return lf.readlines()


def threaded_merge(item, verbose: bool) -> (str, dict):
    file, stuff = item
    failures = {}
    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)

    base_file = util.get_game_file(file, file.startswith('aoc'))
    file_ext = os.path.splitext(file)[1]
    if file_ext in util.SARC_EXTS and (util.get_master_modpack_dir() / file).exists():
        base_file = (util.get_master_modpack_dir() / file)
    with base_file.open('rb') as bf:
        file_bytes = bf.read()
    yazd = file_bytes[0:4] == b'Yaz0'
    file_bytes = file_bytes if not yazd else wszst_yaz0.decompress(file_bytes)
    magic = file_bytes[0:4]

    if magic == b'SARC':
        new_sarc, sub_failures = nested_patch(sarc.SARC(file_bytes), stuff)
        del file_bytes
        new_bytes = new_sarc.get_bytes()
        for failure, contents in sub_failures.items():
            print(f'Some patches to {failure} failed to apply.')
            failures[failure] = contents
    else:
        try:
            if magic[0:2] == b'BY' or magic[0:2] == b'YB':
                base_byml = byml.Byml(file_bytes).parse()
                str_buf = StringIO()
                yaml.dump(base_byml, str_buf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                        default_flow_style=None)
                del base_byml
                base_text = str_buf.getvalue()
                del str_buf

                patches = deepcopy(stuff)
                patches.reverse()
                new_text, success = apply_patches(patches, base_text)
                if not success:
                    failures[file] = new_text
                    print(f'One or more patches in {file} failed to apply.')
                else:
                    if verbose:
                        print(f'Successfully patched {file}.')

                buf = BytesIO()
                root = yaml.load(new_text, Loader=loader)
                bw = byml.Writer(root, True)
                del root
                bw.write(buf)
                del bw
                new_bytes = buf.getvalue()
                del buf
            elif magic == b'AAMP':
                aamp_contents = aamp.Reader(file_bytes).parse()
                for change in stuff:
                    aamp_contents = _aamp_merge(aamp_contents, change)
                aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                del aamp_contents
                new_bytes = aamp_bytes if not yazd else wszst_yaz0.compress(aamp_bytes)
            else:
                raise ValueError(f'{file} is not a SARC, AAMP, or BYML file.')
        except:
            new_bytes = file_bytes
            del file_bytes
            print(f'Deep merging file {file} failed. No changes were made.')

    new_bytes = new_bytes if not yazd else wszst_yaz0.compress(new_bytes)
    output_file = (util.get_master_modpack_dir() / file)
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open('wb') as of:
        of.write(new_bytes)
    del new_bytes
    if magic == b'SARC' and verbose:
        print(f'Finished patching files inside {file}')
    elif verbose:
        print(f'Finished patching {file}')
    return util.get_canon_name(file), failures


def deep_merge(verbose: bool = False):
    mods = get_deepmerge_mods()
    if (util.get_master_modpack_dir() / 'logs' / 'rstb.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'rstb.log').unlink()
    if (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').unlink()
    if len(mods) < 2:
        print('No deep merge necessary.')
        return

    print('Loading deep merge data...')
    diffs = consolidate_diff_files(get_deepmerge_diffs())
    failures = {}

    print('Performing deep merge...')
    for file_type in diffs:
        if len(diffs[file_type]) == 0:
            continue
        num_threads = min(multiprocessing.cpu_count(), len(diffs[file_type]))
        p = multiprocessing.Pool(processes=num_threads)
        thread_merger = partial(threaded_merge, verbose=verbose)
        results = p.map(thread_merger, diffs[file_type].items())
        p.close()
        p.join()
        for name, fails in results:
            failures.update(fails)

    print('Updating RSTB...')
    modded_files = install.find_modded_files(util.get_master_modpack_dir())[0]
    sarc_files = [file for file in modded_files if util.is_file_sarc(file) and not fnmatch(
            file, '*Bootup_????.pack')]
    modded_sarc_files = {}
    for file in sarc_files:
        with Path(util.get_master_modpack_dir() / modded_files[file]['path']).open('rb') as sf:
            mod_sarc = sarc.read_file_and_make_sarc(sf)
        if not mod_sarc:
            print(f'Skipped broken pack {file}')
            return {}, [], {}
        modded_sarcs = install.find_modded_sarc_files(mod_sarc, modded_files[file]['path'],
                                    tmp_dir=util.get_master_modpack_dir(),
                                    aoc=('aoc' in file.lower()))[0]
        modded_sarc_files.update(modded_sarcs)
    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with Path(util.get_master_modpack_dir() / 'logs' / 'rstb.log').open('w') as rf:
        rf.write('name,rstb\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in ['.pack', '.bgdata', '.txt', '.bgsvdata', 'data.sarc', '.bat', '.ini', '.png'] \
                    and 'ActorInfo' not in file:
                rf.write('{},{},{}\n'
                            .format(file, modded_files[file]["rstb"], str(modded_files[file]["path"]).replace('\\', '/'))
                            )
    bcml.rstable.generate_master_rstb()

    with (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').open('w') as lf:
        for file_type in diffs:
            for file in diffs[file_type]:
                lf.write(f'{file}\n')
    if len(failures) > 0:
        with (util.get_work_dir() / 'failures.yml').open('w') as ff:
            yaml.safe_dump(failures, ff)
        print(f'In {len(failures)} files, one or more patches failed to apply. For more information, the following log'
              f'file contains the resultant contents of all of the files which had patch failures:\n'
              f'{str(util.get_work_dir() / "failures.yml")}')
