# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import argparse
import configparser
import glob
import os
import shutil
import pathlib

from bcml import mergepacks, mergerstb, mergetext

def main(args):
    workdir = os.path.join(os.getenv('LOCALAPPDATA'),'bcml')

    i = 0
    mods = {}

    try:
        target = args.target
    except:
        target = None
    try:
        priority = args.priority
    except:
        priority = None

    if not target:
        print('Mods currently installed:')
    for rulef in glob.iglob(os.path.join(args.directory, 'BotwMod*/rules.txt')):
        rules = configparser.ConfigParser()
        rules.read(rulef)
        mods[i] = {
            'name' : rules['Definition']['name'],
            'priority' : rules['Definition']['fsPriority'],
            'path' : os.path.dirname(rulef)
        }
        if mods[i]['name'] == 'BCML': continue
        if mods[i]['priority'] == target:
            target = i + 1
        if not target:
            print(f'{i + 1}. {mods[i]["name"]} — Priority: {mods[i]["priority"]}')
        i += 1

    target = '9999' if not target else target
    while int(target) - 1 not in mods:
        print()
        target = input('Enter the number of the mod you would like to modify: ')
    modtarget = mods[int(target) - 1]
    remerge = os.path.exists(os.path.join(modtarget['path'], 'packs.log'))
    retext = os.path.exists(os.path.join(modtarget['path'], 'content', 'Pack', 'Bootup_USen.pack'))

    if not priority:
        priority = -1
    while priority < 0:
        try:
            priority = int(input(f'Enter the new priority for {modtarget["name"]}: '))
        except ValueError as e:
            priority = int(input(f'That was not a number. Enter the new priority for {modtarget["name"]}: '))

    moddir = os.path.join(args.directory, f'BotwMod_mod{priority:03}')

    while os.path.exists(moddir):
        print(f'A mod with priority {priority} already exists.')
        priority = int(input(f'Enter a new priority for {modtarget["name"]}: '))
        moddir = os.path.join(args.directory, f'BotwMod_mod{priority:03}')

    try:
        shutil.move(modtarget['path'], moddir)

        rules = configparser.ConfigParser()
        rules.read(os.path.join(moddir,'rules.txt'))
        rules['Definition']['fsPriority'] = str(priority)
        with open(os.path.join(moddir,'rules.txt'), 'w') as rulef:
            rules.write(rulef)

        print('Updating RSTB configuration...')
        mergerstb.main(args.directory, "verb" if args.verbose else "quiet")
        print()
        if remerge: 
            print('Updating merged packs...')
            mergepacks.main(args.directory, args.verbose)
        if retext: 
            print('Updating merged text modifications...')
            mergetext.main(pathlib.Path(args.directory))
        print()
        print('Mod configuration updated successfully')
    except Exception as e:
        print(f'There was an error changing the priority of {modtarget["name"]}')
        print('Check the error log for details at:')
        elog_path = os.path.join(workdir, 'error.log')
        print(f'  {elog_path}')
        with open(elog_path,'w') as elog:
            elog.write(e.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Refreshes RSTB and merged packs for BCML-managed mods')
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '../graphicPacks', type = str)
    parser.add_argument('-t', '--target', help = 'Specify the priority of the mod to target for re-ordering', type = int)
    parser.add_argument('-p', '--priority', help = 'Specify new load priority for mod', type = int)
    parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
    args = parser.parse_args()
    main(args)