"""Provides features for diffing and merging EventInfo.product.sbyml """
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from copy import deepcopy
from pathlib import Path
from typing import List, Union
import yaml
import byml
from byml import yaml_util
import rstb
import sarc
from bcml import util, rstable, mergers


def get_stock_eventinfo() -> {}:
    """ Gets the contents of the stock `EventInfo.product.sbyml` """
    if not hasattr(get_stock_eventinfo, 'event_info'):
        get_stock_eventinfo.event_info = byml.Byml(
            util.get_nested_file_bytes(
                str(util.get_game_file('Pack/Bootup.pack')) + '//Event/EventInfo.product.sbyml',
                unyaz=True
            )
        ).parse()
    return deepcopy(get_stock_eventinfo.event_info)

def get_modded_events(event_info: dict) -> {}:
    """
    Gets a dict of new or modified event entries in an `EventInfo.product.sbyml` file

    :param eventinfo: The contents of the modded event info file to diff
    :type eventinfo: dict
    :returns: Returns a dict of new or modified event entries
    :rtype: dict
    """
    stock_events = get_stock_eventinfo()
    modded_events = {}
    for event, data in event_info.items():
        if event not in stock_events or\
           stock_events[event] != data:
            modded_events[event] = deepcopy(data)
    return modded_events


def get_events_for_mod(mod: util.BcmlMod) -> {}:
    """
    Gets all of the logged event info changes for a mod

    :return: Returns a dict of new and modded event info entries
    :rtype: dict
    """
    events = {}
    if (mod.path / 'logs' / 'eventinfo.yml').exists():
        loader = yaml.CSafeLoader
        yaml_util.add_constructors(loader)
        events = yaml.load((mod.path / 'logs' / 'eventinfo.yml').open('r'), Loader=loader)
    return events


def merge_events():
    """ Merges all installed event info mods """
    event_mods = [mod for mod in util.get_installed_mods() \
                  if (mod.path / 'logs' / 'eventinfo.yml').exists()]
    merged_events = util.get_master_modpack_dir() / 'logs' / 'eventinfo.byml'
    event_merge_log = util.get_master_modpack_dir() / 'logs' / 'eventinfo.log'
    event_mod_hash = str(hash(tuple(event_mods)))

    if not event_mods:
        print('No event info merging necessary')
        if merged_events.exists():
            merged_events.unlink()
            event_merge_log.unlink()
            try:
                stock_eventinfo = util.get_nested_file_bytes(
                    str(util.get_game_file('Pack/Bootup.pack')) + '//Event/EventInfo.product.sbyml',
                    unyaz=False
                )
                util.inject_file_into_bootup(
                    'Event/EventInfo.product.sbyml',
                    stock_eventinfo
                )
            except FileNotFoundError:
                pass
        return
    if event_merge_log.exists() and event_merge_log.read_text() == event_mod_hash:
        print('No event info merging necessary')
        return

    print('Loading event info mods...')
    modded_events = {}
    for mod in event_mods:
        modded_events.update(get_events_for_mod(mod))
    new_events = get_stock_eventinfo()
    for event, data in modded_events.items():
        new_events[event] = data

    print('Writing new event info...')
    event_bytes = byml.Writer(new_events, be=True).get_bytes()
    util.inject_file_into_bootup(
        'Event/EventInfo.product.sbyml',
        util.compress(event_bytes),
        create_bootup=True
    )
    print('Saving event info merge log...')
    event_merge_log.write_text(event_mod_hash)
    merged_events.write_bytes(event_bytes)

    print('Updating RSTB...')
    rstb_size = rstb.SizeCalculator().calculate_file_size_with_ext(event_bytes, True, '.byml')
    rstable.set_size('Event/EventInfo.product.byml', rstb_size)


class EventInfoMerger(mergers.Merger):
    NAME: str = 'eventinfo'

    def __init__(self):
        super().__init__('event info merge', 'Merges changes to EventInfo.product.byml',
                         'eventinfo.yml', options={})

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//Event/EventInfo.product.sbyml' in modded_files:
            with (mod_dir / 'content' / 'Pack' / 'Bootup.pack').open('rb') as bootup_file:
                bootup_sarc = sarc.read_file_and_make_sarc(bootup_file)
            event_info = byml.Byml(
                util.decompress(
                    bootup_sarc.get_file_data('Event/EventInfo.product.sbyml').tobytes()
                )
            ).parse()
            return get_modded_events(event_info)
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                dumper = yaml.CSafeDumper
                yaml_util.add_representers(dumper)
                yaml.dump(diff_material, log, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                          default_flow_style=None)

    def get_mod_diff(self, mod: util.BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}
            
    def get_all_diffs(self):
        diffs = []
        for mod in [mod for mod in util.get_installed_mods() if self.is_mod_logged(mod)]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    def perform_merge(self):
        merge_events()

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / 'logs' / 'eventinfo.byml'
        if tmp_sarc.exists():
            return (
                'Event/EventInfo.product.sbyml',
                util.compress(tmp_sarc.read_bytes())
            )
        else:
            return
