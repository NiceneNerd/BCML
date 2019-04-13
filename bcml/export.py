import argparse
import glob
import os
import zipfile

def main(args):
    sdir = os.getcwd()

    files = {}
    for mod in glob.iglob(os.path.join(args.directory, 'BotwMod*')):
        if args.onlymerges and '999' not in mod: continue
        os.chdir(mod)
        for file in glob.iglob('**\\*', recursive=True):
            if file.endswith('.log') or file.endswith('.md') or file == 'rules.txt': continue
            files[file] = os.path.abspath(file)
        os.chdir(sdir)

    exzip = zipfile.ZipFile(args.output, mode='w', compression=zipfile.ZIP_DEFLATED)
    for file in files:
        if args.sdcafiine:
            arcfile = os.path.join(f'{args.title}', 'bcml-mod', file)
        elif args.mlc:
            if file.startswith('aoc'):
                arcfile = os.path.join('usr', 'title', args.title.replace('00050000', '00050000\\'), file.replace('aoc\\0010','aoc\\content\\0010'))
            else:
                arcfile = os.path.join('usr', 'title', args.title.replace('00050000', '00050000\\'), file)
        else:
            arcfile = file
        exzip.write(files[file], arcfile)

    if args.sdcafiine:
        with open('README.md', 'w') as readme:
            readme.writelines([
                '# BCML Export SDCafiine Readme\n\n',
                'To install, just extract the contents of this ZIP file to your SD card at the path:\n',
                '/sdcafiine/\n\n',
                'That\'s really all there is to it!'
            ])
        exzip.write(os.path.abspath('README.md'), 'README.md')
        os.remove('README.md')
    elif args.mlc:
        with open('README.md', 'w') as readme:
            readme.writelines([
                '# BCML Export MLC Readme\n\n',
                'To install, just extract the contents of this ZIP file to the mlc01 folder where you installed Cemu, for example:\n',
                'C:\\Cemu\\mlc01\n\n',
                'That\'s really all there is to it!'
            ])
        exzip.write(os.path.abspath('README.md'), 'README.md')
        os.remove('README.md')
    else:        
        with open('tmprules.txt','w') as rules:
            rules.writelines([
                '[Definition]\n',
                'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n',
                'name = Exported BCML Mod\n',
                'path = The Legend of Zelda: Breath of the Wild/BCML Mods/Exported BCML\n',
                'description = Exported contents of all BCML-managed mods\n',
                'version = 4\n'
                ])
        exzip.write(os.path.abspath('tmprules.txt'), 'rules.txt')
        os.remove('tmprules.txt')

    exzip.close()
    print(f'Export to {args.output} successful')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Exports BCML-managed files as a standalone mod')
    parser.add_argument('output', help = 'Path to the mod ZIP that BCML should create')
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '..\\graphicPacks', type = str)
    parser.add_argument('-o', '--onlymerges', help = 'Only include the merged RSTB and packs, not all installed content', action = 'store_true')
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument('-s', '--sdcafiine', help = 'Export in SDCafiine format instead of graphicPack', action = 'store_true')
    formats.add_argument('-m', '--mlc', help = 'Export in the MLC content format instead of graphicPack', action = 'store_true')
    parser.add_argument('-t', '--title', help = 'The TitleID to use for SDCafiine or mlc export, default 00050000101C9400 (US version)', default = '00050000101C9400', type = str)
    args = parser.parse_args()
    main(args)