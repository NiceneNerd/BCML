# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import argparse
import configparser
import csv
import glob
import os
import shutil
import signal
import sys
import traceback
import zipfile
import zlib
from xml.dom import minidom

import rarfile
import rstb
import sarc
import wszst_yaz0
import xxhash
from rstb import util

from bcml import mergepacks, mergerstb

hashtable = {}
args = None

def get_canon_name(file) -> str:
    name = file.replace("\\","/").replace('.s','.')
    if 'content/' in name:
        return name.replace('./content/','')
    elif '/aoc' in name:
        return name.replace('./aoc','Aoc')

def find_modded_files(dir, verbose = False) -> {}:
    modfiles = {}
    for root, directories, filenames in os.walk(dir):
        for filename in filenames:
            pathname = os.path.join(root, filename)
            if filename.endswith('sizetable'):
                os.remove(pathname)
                continue
            cname = get_canon_name(pathname)
            if cname in hashtable:
                if not is_file_modded(pathname, cname):
                    if verbose: print(f'File {cname} unmodified, ignoring...')
                    continue
                else:
                    rstbsize = rstb.SizeCalculator().calculate_file_size(file_name = pathname, wiiu = True, force = False)
                    modfiles[cname] = { 'path': pathname, 'rstb': rstbsize if rstbsize > 0 else 'del' }
                    if verbose: print(f'Added modified file {cname}')
                    continue
            else:
                if verbose: print(f'{cname} not found in hashtable')

    return modfiles

def find_modded_sarc_files(s, verbose = False) -> {}:
    modfiles = {}
    for file in s.list_files():
        rfile = file.replace('.s','.')
        if 'Msg_' in file:
            modfiles[rfile] = { 'path': '', 'rstb': 'del' }
            if verbose: print(f'Added modified file {rfile}')
            continue
        fname, fext = os.path.splitext(file)
        fdata = s.get_file_data(file).tobytes()
        if '.s' in file:
            fdata = wszst_yaz0.decompress(fdata)
        if rfile in hashtable:
            if hashtable[rfile] == xxhash.xxh32(fdata).hexdigest():
                if verbose: print(f'File {rfile} unmodified, ignoring...')
            else:
                rstbsize = rstb.SizeCalculator().calculate_file_size_with_ext(fdata, True, fext)
                modfiles[rfile] = { 'path': '', 'rstb': rstbsize if rstbsize > 0 else 'del' }
                if verbose: print(f'Added modified file {rfile}')
                if rfile.endswith('pack') or rfile.endswith('sarc'):
                    modfiles.update(find_modded_sarc_files(sarc.SARC(fdata)))
    return modfiles


def is_file_modded(path, name) -> bool:
    fdata = ''
    with open(path, 'rb') as f:
        fdata = f.read()
    fhash = xxhash.xxh32(fdata).hexdigest()
    return not (fhash == hashtable[name])

def get_mod_id(moddir, priority) -> int:
    i = priority
    while os.path.exists(os.path.join(moddir,f'BotwMod_mod{i:03}')):
        i += 1
    return i

def main(args):
    ewd = os.getcwd()
    print(f'Attemping to install {args.mod}...')
    print()
    try:
        workdir = os.path.join(os.getenv('LOCALAPPDATA'),'bcml')
        execdir = os.path.dirname(os.path.realpath(__file__))

        print("Loading hash table...")
        with open(os.path.join(execdir, 'data', 'hashtable.csv'),'r') as hashCsv:
            csvLoop = csv.reader(hashCsv)
            for row in csvLoop:
                hashtable[row[0]] = row[1]

        print("Extracting mod files...")
        tmpdir = ''
        try:
            tmpdir = os.path.join(workdir, 'tmp')
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
            if args.mod.endswith('.zip'):
                modzip = zipfile.ZipFile(args.mod, 'r')
                os.mkdir(tmpdir)
                modzip.extractall(tmpdir)
                modzip.close()
            elif args.mod.endswith('.rar'):
                modzip = rarfile.RarFile(args.mod, 'r')
                os.mkdir(tmpdir)
                modzip.extractall(tmpdir)
                modzip.close()
            elif args.mod.endswith('.7z'):
                os.system(f'{os.path.join(execdir, "helpers", "7za.exe")} x -o"{tmpdir}" "{args.mod}" >nul 2>&1')
            else:
                raise Exception
        except:
            print("Mod could not be extracted. Either it is in an unsupported format or the archive is invalid.")
            print('Check error.log for details')
            with open(os.path.join(workdir, 'error.log'),'w') as elog:
                elog.write(traceback.format_exc())

        mdir = tmpdir
        if not os.path.exists(os.path.join(mdir, 'rules.txt')):
            for subdir in glob.iglob(f'{tmpdir}/*', recursive=True):
                if os.path.exists(os.path.join(subdir, 'rules.txt')):
                    mdir = subdir
        try:
            os.chdir(mdir)
        except Exception as e:
            print(f'No rules.txt was found. Is this a mod in Cemu graphics pack format?')
            sys.exit()
            
        modfiles = {}
        if os.path.exists('./content'):
            print("Scanning modded content files...")
            modfiles.update(find_modded_files('./content', args.verbose))

        if os.path.exists('./aoc'):
            print("Scanning modded aoc files...")
            modfiles.update(find_modded_files('./aoc', args.verbose))

        sarcmods = {}
        for file in modfiles.keys():
            if file.endswith('pack') or file.endswith('sarc'):
                print(f'Scanning files in {file}...')
                with open(modfiles[file]['path'], 'rb') as pack:
                    s : sarc.SARC = sarc.read_file_and_make_sarc(pack)
                    if not s:
                        print('Broken pack, skipping...')
                    else:
                        sarcmods.update(find_modded_sarc_files(s, args.verbose))
        modfiles.update(sarcmods)

        if len(modfiles) == 0:
            print()
            print('No modified files were found. That\'s very unusual. Are you sure this is a mod?')
            print()
            sys.exit(0)

        os.chdir(ewd)
        modid = get_mod_id(args.directory, args.priority)
        moddir = os.path.join(args.directory,f'BotwMod_mod{modid:03}')
        print(f'Moving mod from {mdir} to {moddir}')
        shutil.move(mdir, moddir)
        with open(os.path.join(moddir, 'rstb.log'),'w') as rlog:
            rlog.write('name,rstb\n')
            for file in modfiles.keys():
                rlog.write(f'{file},{modfiles[file]["rstb"]}\n')

        if not args.nomerge and len(sarcmods) > 0: 
            with open(os.path.join(moddir,'packs.log'),'w') as plog:
                plog.write('name,path\n')
                for pack in modfiles.keys():
                    if (pack.endswith('pack') or pack.endswith('sarc')) and modfiles[pack]['path'] != '':
                        plog.write('{},{}\n'.format(pack, modfiles[pack]['path'].replace('/','\\')))

        p = args.priority if args.priority > 100 else modid
        rules = configparser.ConfigParser()
        rules.read(os.path.join(moddir,'rules.txt'))
        rulepath = os.path.basename(rules['Definition']['path']).replace('"','')
        rules['Definition']['path'] = f'The Legend of Zelda: Breath of the Wild/BCML Mods/{rulepath}'
        rules['Definition']['fsPriority'] = str(p)
        with open(os.path.join(moddir,'rules.txt'), 'w') as rulef:
            rules.write(rulef)

        setpath = os.path.join(args.directory, '../', 'settings.xml')
        setread = ''
        with open(setpath, 'r') as setfile:
            for line in setfile.readlines():
                setread += line
        settings = minidom.parseString(setread.replace('\n','').replace('\r','').rstrip('\r\n').replace('  ',''))
        gpack = settings.getElementsByTagName('GraphicPack')[0]
        hasbcml = False
        for entry in gpack.getElementsByTagName('Entry'):
            if 'BotwMod_mod999_BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
                hasbcml = True
        if not hasbcml:
            bcmlentry = settings.createElement('Entry')
            entryfile = settings.createElement('filename')
            entryfile.appendChild(settings.createTextNode(f'graphicPacks\\BotwMod_mod999_BCML\\rules.txt'))
            entrypreset = settings.createElement('preset')
            entrypreset.appendChild(settings.createTextNode(''))
            bcmlentry.appendChild(entryfile)
            bcmlentry.appendChild(entrypreset)
            gpack.appendChild(bcmlentry)
        modentry = settings.createElement('Entry')
        entryfile = settings.createElement('filename')
        entryfile.appendChild(settings.createTextNode(f'graphicPacks\\BotwMod_mod{modid:03}\\rules.txt'))
        entrypreset = settings.createElement('preset')
        entrypreset.appendChild(settings.createTextNode(''))
        modentry.appendChild(entryfile)
        modentry.appendChild(entrypreset)
        gpack.appendChild(modentry)
        settings.writexml(open(setpath, 'w'),indent='',addindent='    ',newl='\n')

        if args.leave: open(os.path.join(moddir,'.leave'), 'w').close()
        if args.shrink: open(os.path.join(moddir,'.shrink'), 'w').close()

        mmdir = os.path.join(args.directory,'BotwMod_mod999_BCML')
        if not os.path.exists(mmdir):
            os.makedirs(f'{mmdir}/content/System/Resource/')
            rules = open(f'{mmdir}/rules.txt','a')
            rules.write('[Definition]\n'
                        'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                        'name = BCML\n'
                        'path = The Legend of Zelda: Breath of the Wild/BCML Mods/Master BCML\n'
                        'description = Auto-generated pack which merges RSTB changes and packs for other mods\n'
                        'version = 4\n'
                        'fsPriority = 999')
            rules.close()
        mergerstb.main(args.directory, "verb" if args.verbose else "quiet")
        if not args.nomerge: mergepacks.main(args.directory, args.verbose)

        while os.path.exists(tmpdir):
            try:
                shutil.rmtree(tmpdir)
            except PermissionError as e:
                pass
        print('Mod installed successfully!')
    except SystemExit as e:
        print('Exiting...')
    except:
        print(f'There was an error installing {args.mod}')
        print('Check error.log for details')
        with open(os.path.join(workdir, 'error.log'),'w') as elog:
            elog.write(traceback.format_exc())
        os.chdir(ewd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'A tool to install and manage mods for Breath of the Wild in CEMU')
    parser.add_argument('mod', help = 'Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format')
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '../graphicPacks', type = str)
    parser.add_argument('-p', '--priority', help = 'Mod load priority, default 100', default = '100', type = int)
    parser.add_argument('--nomerge', help = 'Do not automatically merge pack files', action = 'store_true')
    parser.add_argument('-s', '--shrink', help = 'Update RSTB entries for files which haven\'t grown', action="store_true")
    parser.add_argument('-l', '--leave', help = 'Do not remove RSTB entries for file sizes which cannot be calculated', action="store_true")
    parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
    args = parser.parse_args()
    main(args)
