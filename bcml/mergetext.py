import copy
import csv
import glob
import os
import shutil
import io
import re
import sys
import traceback
import unicodedata
import zipfile
from pathlib import Path

import sarc
import wszst_yaz0
import xxhash
import yaml

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
    hashtable = {}

    print("Loading hash table...\n")
    with open(execdir / 'data' / 'msyt' / 'msbthash.csv','r') as hashCsv:
        csvLoop = csv.reader(hashCsv)
        for row in csvLoop:
            hashtable[row[0]] = row[1]

    #if tmpdir.exists():
    #    shutil.rmtree(tmpdir, ignore_errors=True)

    print('Loading reference texts...')
    refMsg = zipfile.ZipFile(Path(execdir / 'data' / 'msyt' / 'Msg_USen.product.zip').resolve())
    ref_dir = tmpdir / 'ref'
    refMsg.extractall(ref_dir)

    textmods = []
    print('Detecting mods with text changes...')
    for i, file in enumerate(sorted(path.rglob(f'BotwMod_mod*/**/Bootup_{lang}.pack'))):
        textmods.append([])
        with open(file, 'rb') as f_pack:
            s_bootup = sarc.read_file_and_make_sarc(f_pack)
        data_msg = wszst_yaz0.decompress(s_bootup.get_file_data(f'Message/Msg_{lang}.product.ssarc'))
        s_msg = sarc.SARC(data_msg)
        tmp_path = workdir / 'tmp' / f'{i}'
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
    for msbt_file in sorted(tmpdir.rglob('**/*.msbt')):
        #os.system(f'msyt export "{msbt_file}"')
        Path(msbt_file).unlink()

    merged_dir = tmpdir / 'merged'
    print('Comparing modified text files...')
    for msyt in ref_dir.rglob('**/*.msyt'):
        rel_path = str(msyt.relative_to(ref_dir)).replace('\\','/')
        with open(msyt,'r', encoding='utf-8') as f_ref:
            ref_text = yaml.load(f_ref)
            merged_lines = copy.deepcopy(ref_text)

        for i, textmod in enumerate(textmods):
            if rel_path in textmod:
                with open(tmpdir / f'{i}' / rel_path, 'r', encoding='utf-8') as f_mod:
                    mod_text = yaml.load(f_mod)
                    if mod_text['entries'] == ref_text['entries']: continue
                    for entry in mod_text['entries']:
                        if are_entries_diff(entry, ref_text, mod_text):
                            merged_lines['entries'][entry] = copy.deepcopy(mod_text['entries'][entry])
                            print(f'Updated {entry} text in {rel_path}')
        merged_path = merged_dir / rel_path
        merged_path.parent.mkdir(parents=True, exist_ok=True)
        with open(merged_path, 'w', encoding='utf-8') as f_merged:
            yaml.dump(merged_lines, f_merged)

if __name__ == "__main__":
    workdir = Path(os.getenv('LOCALAPPDATA')) / 'bcml'
    execdir = Path(__file__).parent.absolute()
    tmpdir = workdir / 'tmp'
    
    main(Path(sys.argv[1]))