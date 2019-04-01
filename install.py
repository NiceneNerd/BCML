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

hashnames=[]
hashes=[]
priorities={}

def is_file_in_rstb(file, table) -> bool:
    hash = zlib.crc32(str.encode(file))
    return (hash in table.crc32_map)

def get_canon_name(file) -> str:
    name = file.replace("\\","/").replace('.s','.')
    if 'content/' in name:
        return name.replace('./content/','')
    elif '/aoc' in name:
        return name.replace('./aoc','Aoc')

def is_file_modded(path, name) -> bool:
    fdata = ''
    with open(path, 'rb') as f:
        fdata = f.read()
    fhash = xxhash.xxh32(fdata).hexdigest()
    return not (fhash == hashes[hashnames.index(name)])

def get_mod_id() -> int:
    i = 0
    while os.path.exists(f'../graphicPacks/BotwMod_mod{i:03}'):
        i += 1
    return i

def is_overriden(file, priority) -> bool:
    if not priority:
        priority = 100
    if file in priorities:
        if int(priorities[file]) > int(priority):
            return True
        else:
            return False
    else:
        return False

def main():
    parser = argparse.ArgumentParser(description = 'A tool to install and manage mods for Breath of the Wild in CEMU')
    parser.add_argument('mod', help = 'Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format')
    parser.add_argument('-p', '--priority', help = 'Mod load priority, starting at 100', default = '100', type = int)
    parser.add_argument('-s', '--shrink', help = 'Update RSTB entries for files which haven\'t grown', action="store_false")
    parser.add_argument('-d', '--delete', help = 'Delete RSTB entries for file sizes which cannot be calculated', action="store_false")
    args = parser.parse_args()

    try:
        print("Loading RSTB data...")
        table : rstb.ResourceSizeTable = None
        if not os.path.exists('./data/master.srsizetable.bak'):
            shutil.copyfile('./data/master.srsizetable', './data/master.srsizetable.bak')
        with open('./data/master.srsizetable', 'rb') as file:
            buf = wszst_yaz0.decompress(file.read())
            table = rstb.ResourceSizeTable(buf, True)

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
            print("Mod could not be opened. Either it is in an unsupported format or the archive is invalid.")
            sys.exit(1)

        if os.path.exists('./tmp'):
            shutil.rmtree('./tmp')
        os.mkdir('./tmp')
        modzip.extractall('./tmp')
        modzip.close()
        os.chdir('./tmp')

        files=[]
        realfiles=[]
        if os.path.exists('./content'):
            print("Scanning modded content files...")
            for root, directories, filenames in os.walk("./content/"):
                for filename in filenames:
                    pathname = os.path.join(root, filename)
                    fname = get_canon_name(pathname)
                    if fname in hashnames:
                        if not is_file_modded(pathname, fname):
                            print(f'File {fname} unmodified, ignoring...')
                            continue
                    realfiles.append(pathname)
                    files.append(fname)
                    print('Added file ' + fname)

        if os.path.exists('./aoc'):
            print("Scanning modded aoc files...")
            for root, directories, filenames in os.walk("./aoc/"):
                for filename in filenames:
                    pathname = os.path.join(root, filename)
                    fname = get_canon_name(pathname)
                    if fname in hashnames:
                        if not is_file_modded(pathname, fname):
                            print(f'File {fname} unmodified, ignoring...')
                            continue
                    realfiles.append(pathname)
                    files.append(fname)
                    print('Added file ' + fname)

        print("Scanning modded pack files...")
        packfiles = []
        packsizes = []
        for realfile in realfiles:
            if realfile.endswith('pack'):
                with open(realfile, 'rb') as pack:
                    s : sarc.SARC = sarc.read_file_and_make_sarc(pack)
                    if not s:
                        print("Broken pack, skipping")
                        continue
                    for file in s.list_files():
                        rfile = file.replace('.s','.')
                        if is_file_in_rstb(rfile, table):
                            fname, fext = os.path.splitext(file)
                            fdata = s.get_file_data(file).tobytes()
                            if '.s' in file:
                                fdata = wszst_yaz0.decompress(fdata)
                            if rfile in hashnames:
                                if hashes[hashnames.index(rfile)] == xxhash.xxh32(fdata).hexdigest():
                                    print(f'File {rfile} unmodified, ignoring...')
                                else:
                                    fsize = rstb.SizeCalculator().calculate_file_size_with_ext(fdata, True, fext)
                                    packfiles.append(rfile)
                                    packsizes.append(fsize)
                                    print('Added file ' + rfile)

        if len(files) == 0:
            print()
            print('No content or aoc folders found. This mod may be in a non-standard format. To')
            print('correct this, unzip the mod archive and zip it back with the content and/or aoc')
            print('folders in the root of the zip.')
            print()
            sys.exit(1)

        print('Processing modded file sizes...')
        iUp = 0
        iDel = 0
        delAll = args.delete
        redAll = False
        redNone = args.shrink
        changes = []
        dangers = []
        overrides = []
        for file in files:
            realfile = realfiles[files.index(file)]
            if file.endswith('rsizetable'):
                os.remove(realfile)
                continue
            if is_overriden(file, args.priority):
                overrides.append(file + '\n')
                continue
            elif is_file_in_rstb(file, table):
                print(file + " is in RSTB, checking size...")
                newsize = rstb.SizeCalculator().calculate_file_size(file_name = realfile, wiiu = True, force = False)
                oldsize = table.get_size(file)
                if newsize > oldsize:
                    print(f"Mod file larger, updating RSTB: size {oldsize} to {newsize}")
                    table.set_size(file, newsize)
                    changes.append(f'{file},{oldsize},{newsize}')
                    iUp += 1
                elif newsize <= oldsize and newsize != 0:
                    if (not redAll) and (not redNone):
                        answer = ''
                        while answer not in ("y", "n", "a", "none", "yes", "no", "all"):
                            answer = input("New file size not larger, update RSTB? [yes/no/all/none] ").lower()
                            if answer == "y" or answer == "yes":
                                print(f"Updating RSTB: size {oldsize} to {newsize}")
                                table.set_size(file, newsize)
                                changes.append(f'{file},{oldsize},{newsize}')
                                iUp += 1
                            elif answer =="n" or answer == "no":
                                print("Skipping")
                            elif answer == "a" or answer == "all":
                                print(f"Updating RSTB: size {oldsize} to {newsize}")
                                table.set_size(file, newsize)
                                changes.append(f'{file},{oldsize},{newsize}')
                                iUp += 1
                                redAll = True
                            elif answer == "none":
                                print("Skipping")
                                redNone = True
                            else:
                                print("Please choose an answer")
                    elif redNone:
                        print("Skipping")
                    else:
                        print(f"Updating RSTB: size {oldsize} to {newsize}")
                        table.set_size(file, newsize)
                        changes.append(f'{file},{oldsize},{newsize}')
                        iUp += 1
                else:
                    if file.endswith('.bas') or file.endswith('.baslist'):
                        print('File size could not be calculated, but the RSTB entry cannot be safely deleted.')
                        print('You may need to manually adjust the RSTB entry for ' + file)
                        dangers.append(file + '\n')
                        continue
                    if not delAll:
                        answer = ''
                        while answer not in ("y", "n", "a", "yes", "no", "all"):
                            answer = input("File size could not be calculated, do you want to delete from RSTB? [yes/no/all] ").lower()
                            if answer == "y" or answer == "yes":
                                print("Deleting " + file + " from RSTB")
                                table.delete_entry(file)
                                iDel += 1
                            elif answer == "n" or answer == "no":
                                print("Not deleting " + file + " from RSTB")
                                print("WARNING: This may cause game instability!")
                            elif answer == "a" or answer == "all":
                                print("Deleting " + file + " from RSTB")
                                table.delete_entry(file)
                                iDel += 1
                                delAll = True
                            else:
                                print("Please choose an answer: yes/no/all")
                    else:
                        print("Deleting " + file + " from RSTB")
                        table.delete_entry(file)
                        iDel += 1
        for file in packfiles:
            if is_overriden(file, args.priority):
                overrides.append(file + '\n')
                continue
            print(file + " is in RSTB, checking size...")
            newsize = packsizes[packfiles.index(file)]
            oldsize = table.get_size(file)
            if newsize > oldsize:
                print(f"File has grown, updating RSTB: size {oldsize} to {newsize}")
                table.set_size(file, newsize)
                changes.append(f'{file},{oldsize},{newsize}')
                iUp += 1
            elif newsize < oldsize and newsize != 0:
                if (not redAll) and (not redNone):
                    answer = ''
                    while answer not in ("y", "n", "a", "none", "yes", "no", "all"):
                        answer = input("New file size smaller, update RSTB? [yes/no/all/none] ").lower()
                        if answer == "y" or answer == "yes":
                            print(f"Updating RSTB: size {oldsize} to {newsize}")
                            table.set_size(file, newsize)
                            changes.append(f'{file},{oldsize},{newsize}')
                            iUp += 1
                        elif answer =="n" or answer == "no":
                            print("Skipping")
                        elif answer == "a" or answer == "all":
                            print(f"Updating RSTB: size {oldsize} to {newsize}")
                            table.set_size(file, newsize)
                            changes.append(f'{file},{oldsize},{newsize}')
                            iUp += 1
                            redAll = True
                        elif answer == "none":
                            print("Skipping")
                            redNone = True
                        else:
                            print("Please choose an answer")
                elif redNone:
                    print("Skipping")
                else:
                    print(f"Updating RSTB: size {oldsize} to {newsize}")
                    table.set_size(file, newsize)
                    changes.append(f'{file},{oldsize},{newsize}')
                    iUp += 1
            elif oldsize == newsize:
                print("Size unchanged, skipping")
            else:
                if file.endswith('.bas') or file.endswith('.baslist'):
                    print('File size could not be calculated, but the RSTB entry cannot be safely deleted.')
                    print('You will need to manually adjust the RSTB entry for ' + file)
                    dangers.append(file + '\n')
                    continue
                if not delAll:
                    answer = ''
                    while answer not in ("y", "n", "a", "yes", "no", "all"):
                        answer = input("File size could not be calculated, do you want to delete from RSTB? [Y/n/a] ").lower()
                        if answer == "y" or answer == "yes":
                            print("Deleting " + file + " from RSTB")
                            table.delete_entry(file)
                            changes.append(f'{file},{oldsize},del')
                            iDel += 1
                        elif answer == "n" or answer == "no":
                            print("Not deleting " + file + " from RSTB")
                            print("WARNING: This may cause game instability!")
                        elif answer == "a" or answer == "all":
                            print("Deleting " + file + " from RSTB")
                            table.delete_entry(file)
                            changes.append(f'{file},{oldsize},del')
                            iDel += 1
                            delAll = True
                        else:
                            print("Please choose an answer: y/n/a")
                else:
                    print("Deleting " + file + " from RSTB")
                    table.delete_entry(file)
                    changes.append(f'{file},{oldsize},del')
                    iDel += 1

        os.chdir('../')
        util.write_rstb(table, './data/master.srsizetable', True)
        print()
        print("Updated " + str(iUp) + " file(s) in RSTB")
        print("Deleted " + str(iDel) + " file(s) from RSTB")

        modid = get_mod_id()
        moddir = f'../graphicPacks/BotwMod_mod{modid:03}'
        shutil.move('./tmp', moddir)
        with open(moddir + '/rstb.log','w') as log:
            log.write('name,oldsize,newsize\n')
            for change in changes:
                log.write(change + '\n')
        if len(dangers) > 0:
            print()
            print("RSTB entry for {} item(s) could not be updated or deleted".format(str(len(dangers))))
            print("A list of these has been created in the mod folder in dangers.txt")
            with open(moddir + '/dangers.txt','w') as dlog:
                dlog.writelines(dangers)
        if len(overrides) > 0:
            print()
            print("RSTB entry for {} item(s) have been overriden by higher priority mods.".format(str(len(overrides))))
            print("A list of these has been created in the mod folder in overrides.txt")
            with open(moddir + '/overrides.txt','w') as olog:
                olog.writelines(overrides)
        with open(moddir + '/rules.txt', 'a') as rules:
            p = args.priority if args.priority > 100 else args.priority + modid
            rules.write(f'\nfsPriorty = {p}')

        if not os.path.exists('../graphicPacks/!!!BreathOfTheWild_RSTB'):
            os.makedirs('../!!!BreathOfTheWild_RSTB/content/System/Resource/')
            rules = open('../!!!BreathOfTheWild_RSTB/rules.txt','a')
            rules.write('[Definition]\n'
                        'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                        'name = Master RSTB Fix\n'
                        'path = "The Legend of Zelda: Breath of the Wild/Mods/RSTB"\n'
                        'description = Auto-generated pack which merges RSTB changes for other mods\n'
                        'version = 3\n')
            rules.close()
        shutil.copy('./data/master.srsizetable', '../graphicPacks/!!!BreathOfTheWild_RSTB/content/System/Resource/ResourceSizeTable.product.srsizetable')
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
    main()
