# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import argparse
import os
import traceback

from bcml import mergepacks, mergerstb

def main(args):
    try:
        print('Updating RSTB configuration...')
        mergerstb.main(args.directory, "verb" if args.verbose else "quiet")
        print()
        print('Updating merged packs...')
        if not args.nomerge: mergepacks.main(args.directory, args.verbose)
        print()
        print('Mod configuration updated successfully')
    except Exception as e:
        workdir = os.path.join(os.getenv('LOCALAPPDATA'), 'bcml')
        print(f'There was an error updating your mod configuration')
        print('Check error.log for details')
        with open(os.path.join(workdir,'error.log'),'w') as elog:
            elog.write(traceback.format_exc())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Refreshes RSTB and merged packs for BCML-managed mods')
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '../graphicPacks', type = str)
    parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
    parser.add_argument('--nomerge', 'Skip updating merged packs', action='store_true')
    args = parser.parse_args()
    main(args)
