import argparse
import csv
import os
import shutil
import signal
import sys
import traceback
import zipfile
import zlib

import rarfile
import rstb
import sarc
import wszst_yaz0
import xxhash
from rstb import util
from helpers import mergerstb

hashnames=[]
hashes=[]
priorities={}
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
            if cname in hashnames:
                if not is_file_modded(pathname, cname):
                    if verbose: print(f'File {cname} unmodified, ignoring...')
                    continue
                else:
                    rstbsize = rstb.SizeCalculator().calculate_file_size(file_name = pathname, wiiu = True, force = False)
                    modfiles[cname] = { 'path': pathname, 'rstb': rstbsize if rstbsize > 0 else 'del' }
                    if verbose: print(f'Added modified file {cname}')
    return modfiles

def find_modded_sarc_files(s, verbose = False) -> {}:
    modfiles = {}
    for file in s.list_files():
        if file in hashnames:
            rfile = file.replace('.s','.')
            fname, fext = os.path.splitext(file)
            fdata = s.get_file_data(file).tobytes()
            if '.s' in file:
                fdata = wszst_yaz0.decompress(fdata)
            if rfile in hashnames:
                if hashes[hashnames.index(rfile)] == xxhash.xxh32(fdata).hexdigest():
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
    return not (fhash == hashes[hashnames.index(name)])

def get_mod_id(moddir) -> int:
    i = args.priority
    while os.path.exists(os.path.join(moddir,f'BotwMod_mod{i:03}')):
        i += 1
    return i

def main():
    try:

        print("Loading hash table...")
        with open('./data/hashtable.csv','r') as hashCsv:
            csvLoop = csv.reader(hashCsv)
            for row in csvLoop:
                hashnames.append(row[0])
                hashes.append(row[1])

        if os.path.exists('./data/priorities.csv'):
            with open('./data/priorities.csv', 'r') as pCsv:
                csvLoop = csv.reader(pCsv)
                for row in csvLoop:
                    priorities[row[0]] = row[1]

        print("Extracting mod files...")
        modzip = ''
        try:
            if args.mod.endswith('.zip'):
                modzip = zipfile.ZipFile(args.mod, 'r')
            elif args.mod.endswith('.rar'):
                modzip = rarfile.RarFile(args.mod, 'r')
            else:
                raise Exception
        except:
            print("Mod could not be extracted. Either it is in an unsupported format or the archive is invalid.")
            sys.exit(1)

        if os.path.exists('./tmp'):
            shutil.rmtree('./tmp')
        os.mkdir('./tmp')
        modzip.extractall('./tmp')
        modzip.close()
        os.chdir('./tmp')

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
            print('No content or aoc folders found. This mod may be in a non-standard format. To')
            print('correct this, unzip the mod archive and zip it back with the content and/or aoc')
            print('folders in the root of the zip.')
            print()
            sys.exit(1)

        os.chdir('../')
        modid = get_mod_id(args.directory)
        moddir = os.path.join(args.directory,f'BotwMod_mod{modid:03}')
        print(f'Moving mod to {moddir}')
        shutil.move('./tmp', moddir)
        with open(moddir + '/rstb.log','w') as log:
            log.write('name,rstb\n')
            for file in modfiles.keys():
                log.write(f'{file},{modfiles[file]["rstb"]}\n')

        with open(moddir + '/rules.txt', 'a') as rules:
            p = args.priority if args.priority > 100 else modid
            rules.write(f'\nfsPriority = {p}')

        mmdir = os.path.join(args.directory,'!!!BreathOfTheWild_RSTB')
        if not os.path.exists(mmdir):
            os.makedirs(f'{mmdir}/content/System/Resource/')
            rules = open(f'{mmdir}/rules.txt','a')
            rules.write('[Definition]\n'
                        'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                        'name = Master RSTB Fix\n'
                        'path = "The Legend of Zelda: Breath of the Wild/Mods/RSTB"\n'
                        'description = Auto-generated pack which merges RSTB changes for other mods\n'
                        'version = 3\n'
                        'fsPriority = 999')
            rules.close()
        mergerstb.main(args.directory, "shr" if args.shrink else "noshr", "del" if args.remove else "nodel", "verb" if args.verbose else "quiet")
    except SystemExit as e:
        os.chdir('../')
        shutil.rmtree('./tmp')
        sys.exit(e)
    except:
        print(traceback.format_exc())
    finally:
        if os.path.exists("./tmp"):
            shutil.rmtree('./tmp')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'A tool to install and manage mods for Breath of the Wild in CEMU')
    parser.add_argument('mod', help = 'Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format')
    parser.add_argument('-s', '--shrink', help = 'Update RSTB entries for files which haven\'t grown', action="store_true")
    parser.add_argument('-r', '--remove', help = 'Remove RSTB entries for file sizes which cannot be calculated', action="store_false")
    parser.add_argument('-p', '--priority', help = 'Mod load priority, default 100', default = '100', type = int)
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '../graphicPacks', type = str)
    parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
    args = parser.parse_args()
    main()
