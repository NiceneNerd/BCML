import csv
import glob
import os
import shutil
import sys

import rstb
import sarc
import wszst_yaz0
import xxhash


def main(path, verbose):
    ewd = os.getcwd()
    workdir = os.path.join(os.getenv('LOCALAPPDATA'),'bcml')
    execdir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(workdir)

    hashtable = {}
    print("Loading hash table...")
    with open(os.path.join(execdir, 'data', 'hashtable.csv'),'r') as hashCsv:
        csvLoop = csv.reader(hashCsv)
        for row in csvLoop:
            hashtable[row[0]] = row[1]

    print('Clearing old merges...')
    for dir in glob.iglob(os.path.join(path, 'BotwMod_mod999_BCML', 'content', '*'), recursive=True):
        if not dir.endswith('System'): shutil.rmtree(dir)

    packs = {}
    print('Finding modified packs...')
    for file in glob.iglob(os.path.join(path, 'BotwMod*', 'packs.log')):
        with open(file, 'r') as rlog:
            csvLoop = csv.reader(rlog)
            for row in csvLoop:
                if row[0] == 'name': continue
                filepath = os.path.join(os.path.dirname(file), row[1])
                try:
                    packs[row[0]].append( filepath )
                except KeyError:
                    packs[row[0]] = []
                    packs[row[0]].append( filepath )
                if verbose: print(f'Found pack {row[0]} at {row[1]}')

    for dir in glob.iglob('tmp*'):
        shutil.rmtree(dir, ignore_errors=True)
    for pack in packs:
        if len(packs[pack]) < 2: continue
        print(f'Merging {len(packs[pack])} versions of {pack}...')
        tmpdir = f'tmp_{os.path.basename(pack)}'
        os.mkdir(tmpdir)
        basepack = packs[pack][len(packs[pack]) - 1]
        with open(basepack, 'rb') as bpack:
            if verbose: print(f'Using {packs[pack][0]} as base')
            s : sarc.SARC = sarc.read_file_and_make_sarc(bpack)
            s.extract_to_dir(pack, tmpdir)
        for i in range(0, len(packs[pack])):
            if verbose: print(f'Merging changes from {packs[pack][i]}...')
            with open(packs[pack][i], 'rb') as npack:
                ss : sarc.SARC = sarc.read_file_and_make_sarc(npack)
                for file in ss.list_files():
                    rfile = file.replace('.s', '.')
                    fname, fext = os.path.splitext(file)
                    fdata = ss.get_file_data(file).tobytes()
                    if '.s' in file:
                        fdata = wszst_yaz0.decompress(fdata)
                    if rfile in hashtable:
                        if hashtable[rfile] == xxhash.xxh32(fdata).hexdigest():
                            continue
                        else:
                            with open(os.path.join(tmpdir,file),'wb') as ofile:
                                if '.s' in file:
                                    ofile.write(wszst_yaz0.compress(fdata))
                                else:
                                    ofile.write(fdata)
                            if verbose: print(f'Updated {file} in {pack} with changes from {packs[pack][i]}')
        packpath = basepack[basepack.find('.\\content'):]
        newpath = os.path.join(path, 'BotwMod_mod999_BCML', packpath)
        os.makedirs(os.path.dirname(newpath), exist_ok=True)
        shutil.copy(basepack, newpath)
        os.system('sarc update {} {}{}'.format(tmpdir, newpath, ' >nul 2>&1' if not verbose else ''))
        shutil.rmtree(tmpdir)
    os.chdir(ewd)

if __name__ == "__main__":
    main(sys.argv[1], (sys.argv[2] == 'verb') )
