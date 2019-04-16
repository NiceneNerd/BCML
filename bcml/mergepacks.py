import configparser
import csv
import glob
import io
import os
import shutil
import subprocess
import sys
from operator import itemgetter

import rstb
import sarc
import wszst_yaz0
import xxhash

hashtable = {}
verbose = False

def is_file_modded(name, data):
    fhash = xxhash.xxh32(data).hexdigest()
    return not (fhash == hashtable[name])

def merge_sarcs(sarc_list):
    sarc_list = sorted(sarc_list, key=itemgetter('priority'))
    new_sarc = sarc.make_writer_from_sarc(sarc_list[-1]['pack'])

    output_spaces = (' ' * (int((sarc_list[-1]['nest_level'] * 4)/len(' '))+1))[:(sarc_list[-1]['nest_level'] * 4)]
    print(f'{output_spaces[4:]}Merging {len(sarc_list)} versions of {sarc_list[-1]["name"]}...')

    modded_files = {}
    modded_sarcs = {}
    can_skip = True
    for msarc in sarc_list:
        pack : sarc.SARC = msarc['pack']
        priority = msarc['priority']
        for file in pack.list_files():
            rfile = file.replace('.s', '.')
            if rfile in hashtable:
                fdata = pack.get_file_data(file)
                if '.s' in file and not file.endswith('.sarc'): fdata = wszst_yaz0.decompress(fdata)
                if is_file_modded(rfile, fdata):
                    ext = os.path.splitext(rfile)[1]
                    if ext.endswith('pack') or ext.endswith('sarc'):
                        modded_sarc = {
                                'pack': sarc.SARC(fdata),
                                'priority': priority,
                                'nest_level': sarc_list[-1]['nest_level'] + 1,
                                'name': rfile
                            }
                        can_skip = False
                        try:
                            modded_sarcs[file].append(modded_sarc)
                        except:
                            modded_sarcs[file] = []
                            modded_sarcs[file].append(modded_sarc)
                    else:
                        modded_files[file] = priority

    for modded_file in modded_files.keys():
        if not modded_files[modded_file] == priority: can_skip = False
    if can_skip:
        print(f'{output_spaces}No merges necessary, skipping')
        return new_sarc

    for modded_file in modded_files.keys():
        new_sarc.delete_file(modded_file)
        p = filter(lambda msarc: msarc['priority'] == modded_files[modded_file], sarc_list).__next__()
        new_data = p['pack'].get_file_data(modded_file)
        new_sarc.add_file(modded_file, new_data)
        print(f'{output_spaces}Updated file {modded_file}')

    merged_sarcs = []
    for mod_sarc_list in modded_sarcs:
        if len(modded_sarcs[mod_sarc_list]) < 2:
            continue
        merged_sarcs.append({
            'file': mod_sarc_list,
            'pack': merge_sarcs(modded_sarcs[mod_sarc_list])
            })

    for merged_sarc in merged_sarcs:
        new_sarc.delete_file(merged_sarc['file'])
        new_stream = io.BytesIO()
        merged_sarc['pack'].write(new_stream)
        new_data = new_stream.getvalue()
        if '.s' in merged_sarc['file'] and not merged_sarc['file'].endswith('.sarc'):
            new_data = wszst_yaz0.compress(new_data)
        new_sarc.add_file(merged_sarc['file'], new_data)

    if sarc_list[-1]['nest_level'] > 1:
        print(f'{output_spaces[4:]}Updated nested pack {sarc_list[-1]["name"]}')
    return new_sarc

def main(path, verbose = False):
    execdir = os.path.dirname(os.path.realpath(__file__))

    print("Loading hash table...")
    with open(os.path.join(execdir, 'data', 'hashtable.csv'),'r') as hashCsv:
        csvLoop = csv.reader(hashCsv)
        for row in csvLoop:
            hashtable[row[0]] = row[1]

    print('Clearing old merges...')
    for dir in glob.iglob(os.path.join(path, 'BotwMod_mod999_BCML', 'aoc', '*'), recursive=True):
        shutil.rmtree(dir)
    for dir in glob.iglob(os.path.join(path, 'BotwMod_mod999_BCML', 'content', '*'), recursive=True):
        if not dir.endswith('System'): shutil.rmtree(dir)

    packs = {}
    print('Finding modified packs...')
    for file in glob.iglob(os.path.join(path, 'BotwMod*', 'packs.log')):
        rules = configparser.ConfigParser()
        rules.read(os.path.join(os.path.dirname(file), 'rules.txt'))
        priority = int(rules['Definition']['fsPriority'])
        with open(file, 'r') as rlog:
            csvLoop = csv.reader(rlog)
            for row in csvLoop:
                if row[0] == 'name': continue
                if 'Bootup_' in row[0] and not 'Bootup_Graphics' in row[0]: continue
                filepath = os.path.join(os.path.dirname(file), row[1])
                try:
                    packs[row[0]].append({
                        'path': filepath,
                        'priority': priority
                        })
                except KeyError:
                    packs[row[0]] = []
                    packs[row[0]].append({
                        'path': filepath,
                        'priority': priority
                        })
                if verbose: print(f'Found pack {row[0]} at {row[1]}')

    for pack in packs:
        iVersions = len(packs[pack])
        if iVersions < 2: continue
        sarc_list = []
        for mpack in packs[pack]:
            with open(mpack['path'], 'rb') as opened_pack:
                sarc_list.append({
                    'pack': sarc.read_file_and_make_sarc(opened_pack),
                    'priority': mpack['priority'],
                    'nest_level': 1,
                    'name': pack
                })
        new_pack = merge_sarcs(sarc_list)
        packpath = packs[pack][0]['path'][packs[pack][0]['path'].find('.\\content'):]
        newpath = os.path.join(path, 'BotwMod_mod999_BCML', packpath)
        os.makedirs(os.path.dirname(newpath), exist_ok=True)
        new_stream = io.BytesIO()
        new_pack.write(new_stream)
        new_data = new_stream.getvalue()
        p_ext = os.path.splitext(packs[pack][0]['path'])[1]
        if p_ext.startswith('.s') and not p_ext == '.sarc': new_data = wszst_yaz0.compress(new_data)
        with open(newpath, 'wb') as new_file:
            new_file.write(new_data)

if __name__ == "__main__":
    verbose = (sys.argv[2] == 'verb')
    main(sys.argv[1])
