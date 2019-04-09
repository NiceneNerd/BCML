import argparse
import os

from bcml import install, uninstall, update, export

owd = os.path.abspath(os.getcwd())
idir = os.path.dirname(os.path.abspath(__file__))
os.chdir(idir)

cemudir = ''
if not os.path.exists('.cdir'):
    while not os.path.exists(os.path.join(cemudir, 'Cemu.exe')):
        cemudir = input('For first time use, please specify the folder where Cemu is installed:\n> ')
    with open('.cdir', 'w') as cdir:
        cdir.write(os.path.abspath(cemudir))
else:
    with open('.cdir', 'r') as cdir:
        cemudir = cdir.readline()

parser : argparse.ArgumentParser = argparse.ArgumentParser(prog='bcml')
parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, if different from saved', default = os.path.join(cemudir, 'graphicPacks'), type = str)
parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
subparsers = parser.add_subparsers(dest='command', help='Command for BCML to perform')
subparsers.required = True

p_install = subparsers.add_parser('install')
p_install.add_argument('mod', help = 'Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format')
p_install.add_argument('-p', '--priority', help = 'Mod load priority, default 100', default = '100', type = int)
p_install.add_argument('--nomerge', help = 'Do not automatically merge pack files', action = 'store_true')
p_install.add_argument('-s', '--shrink', help = 'Update RSTB entries for files which haven\'t grown', action="store_true")
p_install.add_argument('-l', '--leave', help = 'Do not remove RSTB entries for file sizes which cannot be calculated', action="store_true")

p_uninstall = subparsers.add_parser('uninstall', description = 'Uninstaller for BCML-managed mods')

p_update = subparsers.add_parser('update', description = 'Refreshes RSTB and merged packs for BCML-managed mods')

p_export = subparsers.add_parser('export')
p_export.add_argument('output', help = 'Path to the mod ZIP that BCML should create')
p_export.add_argument('-o', '--onlymerges', help = 'Only include the merged RSTB and packs, not all installed content', action = 'store_true')
formats = p_export.add_mutually_exclusive_group()
formats.add_argument('-s', '--sdcafiine', help = 'Export in SDCafiine format instead of graphicPack', action = 'store_true')
formats.add_argument('-m', '--mlc', help = 'Export in the MLC content format instead of graphicPack', action = 'store_true')
p_export.add_argument('-t', '--title', help = 'The TitleID to use for SDCafiine or mlc export, default 00050000101C9400 (US version)', default = '00050000101C9400', type = str)

args = parser.parse_args()

print('##############################################')
print('##    Breath of the Wild Cemu Mod Loader    ##')
print('##------------------------------------------##')
print('##     (c) 2019 Nicene Nerd - GPLv3+        ##')
print('## 7za.exe (c) 2019 Ignor Pavolv - LGPLv3+  ##')
print('##############################################')
print()

try:
    if args.command == 'install':
        os.chdir(owd)
        args.mod = os.path.abspath(args.mod)
        os.chdir(idir)
        install.main(args)
        os._exit(0)
    elif args.command == 'uninstall':
        uninstall.main(args)
        os._exit(0)
    elif args.command == 'export':
        os.chdir(owd)
        args.output = os.path.abspath(args.output)
        os.chdir(idir)
        export.main(args)
        os._exit(0)
    elif args.command == 'update':
        update.main(args)
        os._exit(0)
    else:
        print('Invalid command')
finally:
    os.chdir(owd)