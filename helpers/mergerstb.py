import csv
import glob
import os
import shutil
import sys
import zlib

import rstb
from rstb import util

def main(path, verbose):
    print('Loading clean RSTB data...')
    table : rstb.ResourceSizeTable = None
    if not os.path.exists('./data/master.srsizetable'):
        shutil.copyfile('./data/clean.srsizetable', './data/master.srsizetable')
    table = rstb.util.read_rstb('./data/master.srsizetable', True)

    rstbchanges = {}
    print('Processing RSTB modifications..')
    for file in glob.iglob(os.path.join(path, 'BotwMod*/rstb.log'), recursive=False):
        shrink = False
        leave = False
        if os.path.exists( os.path.join( os.path.dirname(file), '.leave' ) ): leave = True
        if os.path.exists( os.path.join( os.path.dirname(file), '.shrink' ) ): shrink = True
        with open(file, 'r') as log:
            logLoop = csv.reader(log)
            for row in logLoop:
                rstbchanges[row[0]] = {
                    'size' : row[1],
                    'leave' : leave,
                    'shrink': shrink
                }
    for change in rstbchanges:
        if zlib.crc32(str.encode(change)) in table.crc32_map:
            newsize = 0
            try:
                newsize = int(rstbchanges[change]['size'])
            except ValueError:
                if not rstbchanges[change]['leave'] :
                    if change.endswith('.bas') or change.endswith('.baslist'):
                        print(f'WARNING: Cannot calculate or safely remove RSTB size for {change}'
                            'This may need to be corrected manually, or the game could become unstable')
                        continue
                    else:
                        table.delete_entry(change)
                        if verbose == 'verb': print(f'Deleted RSTB entry for {change}')
                        continue
                else:
                    if verbose == 'verb': print(f'Skip deleting RSTB entry for {change}')
                    continue
            oldsize = table.get_size(change)
            if newsize <= oldsize:
                if rstbchanges[change]['shrink']:
                    table.set_size(change, newsize)
                    if verbose == 'verb': print(f'Updated RSTB entry for {change} from {oldsize} to {newsize}')
                    continue
                else:
                    if verbose == 'verb': print(f'Skip updating RSTB entry for {change}')
                    continue
            elif newsize > oldsize:
                table.set_size(change, newsize)
                if verbose == 'verb': print(f'Updated RSTB entry for {change} from {oldsize} to {newsize}')

    print('Writing new RSTB...')
    util.write_rstb(table, './data/master.srsizetable', True)
    mmdir = os.path.join(path, 'BotwMod_mod999_RSTB')
    if not os.path.exists(mmdir):
        os.makedirs(f'{mmdir}/content/System/Resource/')
    shutil.copy('./data/master.srsizetable', f'{mmdir}/content/System/Resource/ResourceSizeTable.product.srsizetable')

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
