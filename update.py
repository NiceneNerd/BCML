import argparse
from helpers import mergerstb
from helpers import mergepacks

args = None

def main():
    try:
        print('Updating RSTB configuration...')
        mergerstb.main(args.directory, "verb" if args.verbose else "quiet")
        print('Updating merged packs...')
        mergepacks.main(args.directory, args.verbose)
        print('Mod uninstalled successfully')
    except Exception as e:
        print(f'There was an error updating your mod configuration')
        print('Check error.log for details')
        with open('error.log','w') as elog:
            elog.write(e.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Refreshes RSTB and merged packs for BCML-managed mods')
    parser.add_argument('-d', '--directory', help = 'Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory', default = '../graphicPacks', type = str)
    parser.add_argument('-v', '--verbose', help = 'Verbose output covering every file processed', action='store_true')
    args = parser.parse_args()
    main()