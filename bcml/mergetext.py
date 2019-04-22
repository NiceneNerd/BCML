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

    hashtable = {}
    print("Loading hash table...\n")
    with open(execdir / 'data' / 'msyt' / 'msbthash.csv','r') as hashCsv:
        csvLoop = csv.reader(hashCsv)
        for row in csvLoop:
            hashtable[row[0]] = row[1]

    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)

    merged_boot_path = path / 'BotwMod_mod999_BCML' / 'content' / 'Pack' / f'Bootup_{lang}.pack'
    if merged_boot_path.exists():
        print('Removing old text merges...')
        merged_boot_path.unlink()

    print('Loading reference texts...')
    refMsg = zipfile.ZipFile(Path(execdir / 'data' / 'msyt' / 'Msg_USen.product.zip').resolve())
    ref_dir = tmpdir / 'ref'
    refMsg.extractall(ref_dir)

    textmods = []
    print('Detecting mods with text changes...')
    modded_boots = list(path.rglob(f'BotwMod_mod*/**/Bootup_{lang}.pack'))
    if len(modded_boots) < 2:
        print('No text mods need merging, skipping')
        return
    for i, file in enumerate(sorted(modded_boots)):
        textmods.append([])
        with open(file, 'rb') as f_pack:
            s_bootup = sarc.read_file_and_make_sarc(f_pack)
        data_msg = wszst_yaz0.decompress(s_bootup.get_file_data(f'Message/Msg_{lang}.product.ssarc'))
        s_msg = sarc.SARC(data_msg)
        tmp_path = tmpdir / f'{i}'
        for msbt in s_msg.list_files():
            m_data = s_msg.get_file_data(msbt)
            m_hash = xxhash.xxh32(m_data).hexdigest()
            if m_hash != hashtable[msbt]:
                msbt_path = tmp_path / msbt
                msbt_path.parent.mkdir(parents=True, exist_ok=True)
                with msbt_path.open(mode='wb') as f_msbt:
                    f_msbt.write(m_data)
                textmods[i].append(msbt.replace('msbt', 'msyt'))

    print()
    print('Generating MSYT files...')
    CREATE_NO_WINDOW = 0x08000000
    m_args = [str(msyt_ex), 'export', '-d', str(tmpdir)]
    subprocess.run(m_args, stdout = subprocess.PIPE, stderr = subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    for msbt_file in tmpdir.rglob('**/*.msbt'):
        Path(msbt_file).unlink()

    merged_dir = tmpdir / 'merged'
    print('Merging modified text files...')
    for msyt in ref_dir.rglob('**/*.msyt'):
        rel_path = str(msyt.relative_to(ref_dir)).replace('\\','/')
        should_bother = False
        for textmod in textmods:
            if rel_path in textmod:
                should_bother = True
                merge_count = 0
        if not should_bother:
            merged_path = merged_dir / rel_path
            merged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(msyt, merged_dir / rel_path)
            continue

        with open(msyt,'r', encoding='utf-8') as f_ref:
            ref_text = yaml.safe_load(f_ref)
            merged_lines = copy.deepcopy(ref_text)

        for i, textmod in enumerate(textmods):
            if rel_path in textmod:
                with open(tmpdir / f'{i}' / rel_path, 'r', encoding='utf-8') as f_mod:
                    mod_text = yaml.safe_load(f_mod)
                    if mod_text['entries'] == ref_text['entries']: continue
                    for entry in mod_text['entries']:
                        if are_entries_diff(entry, ref_text, mod_text):
                            diff_found = True
                            merged_lines['entries'][entry] = copy.deepcopy(mod_text['entries'][entry])
                if diff_found:
                    merge_count += 1
        merged_path = merged_dir / rel_path
        merged_path.parent.mkdir(parents=True, exist_ok=True)
        with open(merged_path, 'w', encoding='utf-8') as f_merged:
            yaml.dump(merged_lines, f_merged)
        if merge_count > 0:
            print(f'Merging {merge_count} versions of {rel_path}...')
    
    print()
    print('Generating new MSBTs...')
    CREATE_NO_WINDOW = 0x08000000
    m_args = [str(msyt_ex), 'create', '-d', str(merged_dir), '-p', 'wiiu', '-o', str(merged_dir)]
    subprocess.run(m_args, stdout = subprocess.PIPE, stderr = subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    for merged_msyt in merged_dir.rglob('**/*.msyt'):
        merged_msyt.unlink()

    new_boot_path = tmpdir / f'Bootup_{lang}.pack'
    with open(new_boot_path, 'wb') as new_boot:
        print(f'Creating new Msg_{lang}.product.ssarc...')
        s_msg = sarc.SARCWriter(True)
        for new_msbt in merged_dir.rglob('**/*.msbt'):
            with open(new_msbt, 'rb') as f_new:
                s_msg.add_file(str(new_msbt.relative_to(merged_dir)).replace('\\','/'), f_new.read())
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
