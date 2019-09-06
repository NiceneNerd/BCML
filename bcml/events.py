"""Provides features for diffing and merging EventInfo.product.sbyml """
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from copy import deepcopy
import yaml
import byml
from byml import yaml_util
import wszst_yaz0
from bcml import util


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
        wszst_yaz0.compress(event_bytes),
        create_bootup=True
    )
    print('Saving event info merge log...')
    event_merge_log.write_text(event_mod_hash)
    merged_events.write_bytes(event_bytes)
