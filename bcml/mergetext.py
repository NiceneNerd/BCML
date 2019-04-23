import copy
import csv
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import traceback
import unicodedata
import zipfile
from pathlib import Path

import rstb
import sarc
import wszst_yaz0
import xxhash
import yaml
from rstb import util

def are_entries_diff(entry, ref_list, mod_list) -> bool:
    mod_entry = unicodedata.normalize('NFC', mod_list['entries'][entry].__str__())
    mod_entry = re.sub('[^0-9a-zA-Z]+', '', mod_entry)
    try:
        ref_entry = unicodedata.normalize('NFC', ref_list['entries'][entry].__str__())
        ref_entry = re.sub('[^0-9a-zA-Z]+', '', ref_entry)
    except KeyError as e:
        return True
    if not ref_entry == mod_entry:
        return True
    return False

def main(path : Path, lang = 'USen'):
    workdir = Path(os.getenv('LOCALAPPDATA')) / 'bcml'
    execdir = Path(os.path.dirname(os.path.realpath(__file__)))
    tmpdir = workdir / 'tmp_text'
    msyt_ex = execdir / 'helpers' / 'msyt.exe'

    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)

    merged_boot_path = path / 'BotwMod_mod999_BCML' / 'content' / 'Pack' / f'Bootup_{lang}.pack'
    if merged_boot_path.exists():
        print('Removing old text merges...')
        merged_boot_path.unlink()

    print('Generating clean texts...')
    refMsg = zipfile.ZipFile(Path(execdir / 'data' / 'msyt' / 'Msg_USen.product.zip').resolve())
    merge_dir = tmpdir / 'merged'
    refMsg.extractall(merge_dir)

    print('Detecting mods with text changes...')
    textmods = []
    for mod in sorted(path.rglob('**/texts.yml')):
        with open(mod, 'r', encoding='utf-8') as mod_text:
            textmods.append(yaml.safe_load(mod_text))

    print('Merging modified text files...')
    for msyt in merge_dir.rglob('**/*.msyt'):
        rel_path = str(msyt.relative_to(merge_dir)).replace('\\','/')
        should_bother = False
        for textmod in textmods:
            if rel_path in textmod:
                should_bother = True
                merge_count = 0
        if not should_bother:
            continue

        with open(msyt,'r', encoding='utf-8') as f_ref:
            merged_text = yaml.safe_load(f_ref)

        for textmod in textmods:
            diff_found = False
            if rel_path in textmod:
                if textmod[rel_path]['entries'] == merged_text['entries']: continue
                for entry in textmod[rel_path]['entries']:
                    diff_found = True
                    merged_text['entries'][entry] = copy.deepcopy(textmod[rel_path]['entries'][entry])
            if diff_found:
                merge_count += 1
        
        with open(msyt, 'w', encoding='utf-8') as f_ref:
            yaml.dump(merged_text, f_ref)
        if merge_count > 0:
            print(f'Adding {merge_count} version(s) of {rel_path}...')
    
    print()
    print('Generating new MSBTs...')
    CREATE_NO_WINDOW = 0x08000000
    m_args = [str(msyt_ex), 'create', '-d', str(merge_dir), '-p', 'wiiu', '-o', str(merge_dir)]
    subprocess.run(m_args, stdout = subprocess.PIPE, stderr = subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    for merged_msyt in merge_dir.rglob('**/*.msyt'):
        merged_msyt.unlink()

    new_boot_path = tmpdir / f'Bootup_{lang}.pack'
    with open(new_boot_path, 'wb') as new_boot:
        print(f'Creating new Msg_{lang}.product.ssarc...')
        s_msg = sarc.SARCWriter(True)
        for new_msbt in merge_dir.rglob('**/*.msbt'):
            with open(new_msbt, 'rb') as f_new:
                s_msg.add_file(str(new_msbt.relative_to(merge_dir)).replace('\\','/'), f_new.read())
        new_msg_stream = io.BytesIO()
        s_msg.write(new_msg_stream)
        new_msg_bytes = wszst_yaz0.compress(new_msg_stream.getvalue())
        print(f'Creating new Bootup_{lang}.pack...')
        s_boot = sarc.SARCWriter(True)
        s_boot.add_file(f'Message/Msg_{lang}.product.ssarc', new_msg_bytes)
        s_boot.write(new_boot)
    merged_boot_path.parent.mkdir(parents = True, exist_ok=True)
    shutil.copy(new_boot_path, merged_boot_path)

    print('Correcting RSTB if necessary...')
    rstb_path = path / 'BotwMod_mod999_BCML' / 'content' / 'System' / 'Resource' / 'ResourceSizeTable.product.srsizetable'
    table = rstb.util.read_rstb(str(rstb_path), True)
    if table.is_in_table(f'Message/Msg_{lang}.product.sarc'):
        table.delete_entry(f'Message/Msg_{lang}.product.sarc')
        rstb.util.write_rstb(table, str(rstb_path), True)

    print()
    print('All text mods merged successfully!')

    while tmpdir.exists():
        shutil.rmtree(tmpdir)

if __name__ == "__main__":    
    main(Path(sys.argv[1]))
