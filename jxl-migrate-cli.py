#!/usr/bin/env python

version = 'v0.2'

'''
jxl-migrate - Convert images to JPEG XL (JXL) format
Copyright (C) 2021-present Kyle Alexander Buan

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import os, sys
import subprocess
import time
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from subprocess import check_output

fsbefore = 0
fsafter = 0

arguments = {}

def is_webp_lossless(p):
    res = check_output(args=[
        'webpinfo',
        p
    ], text=True)

    return 'Format: Lossless' in res

def convert(p, lossy=False, remove=False, losslessjpeg=False):
    res = '.'.join(p.split('.')[0:-1]) + '.jxl'
    proc = subprocess.run(args=[
        'cjxl',
        p,
        res,
        '-d',
        '1' if lossy else '0',
        '-j',
        '1' if losslessjpeg else '0'
    ] + arguments['cjxl_extra_args'], capture_output=True)

    if proc.returncode != 0 or not os.path.exists(res):
        return None
    else:
        os.utime(res, (time.time(), os.path.getmtime(p)))
        if remove:
            os.remove(p)
        return res

def decode(p, remove=False):
    res = '.'.join(p.split('.')[0:-1]) + '.png'

    proc = subprocess.run(args=[
        'dwebp',
        p,
        '-o',
        res
    ], capture_output=True)

    if proc.returncode != 0 or not os.path.exists(res):
        return None
    else:
        os.utime(res, (time.time(), os.path.getmtime(p)))
        return res
def handle_file(filename, root):
    global fsbefore
    global fsafter
    global arguments

    extension = filename.split('.')[-1].lower()

    fullpath = os.path.join(root, filename)
    filesize = os.path.getsize(fullpath)
    lossy = False
    losslessjpeg = False
    decoded_png_filename = None
    if extension not in ['jpg', 'jpeg', 'gif', 'png', 'apng', 'webp']:
        if extension != 'jxl':
            print('Not supported: ' + filename)
        return

    if extension in ['jpg', 'jpeg']:
        lossy = arguments['lossyjpg']
        losslessjpeg = not arguments['lossyjpg']
    elif extension in ['gif']:
        lossy = arguments['lossygif']
    elif extension in ['webp']:
        decoded_png_filename = decode(fullpath)
        if decoded_png_filename is None:
            return
        if arguments['lossywebp']:
            lossy = True
        else:
            lossy = not is_webp_lossless(fullpath)
        fullpath = decoded_png_filename
    filename_without_extension = '.'.join(filename.split('.')[:-1])
    jxl_filename = os.path.join(root, filename_without_extension) + '.jxl'
    if os.path.exists(jxl_filename):
        print(jxl_filename + ' already exists, skipping ' + filename)
        return
    message = "Converting " + fullpath + " to "
    if lossy:
        message += "a lossy"
    else:
        message += "a lossless"
    message += " JXL"
    print(message)
    converted_filename = convert(fullpath, lossy, arguments['delete'], losslessjpeg)
    if converted_filename is None:
        print('Conversion FAILED: ', fullpath)
    else:
        fsbefore += filesize
        fsafter += os.path.getsize(converted_filename)

    if decoded_png_filename is not None:
        os.remove(decoded_png_filename)
def try_handle_file(filename, root):
    try:
        handle_file(filename, root)
    except Exception as inst:
        print('Error processing ' + os.path.join(root, filename) + ': ', repr(inst))

def run():
    global arguments
    global version

    print('jxl-migrate-cli - Convert images in a directory to JPEG XL (JXL) format\n')
    print(version)

    if len(sys.argv) <= 1:
        print('Program usage:')
        print(sys.argv[0] + ' [directory] [--delete] [--lossyjpg] [--lossywebp] [--lossygif]\n')
        print('directory: the folder to process')
        print('--delete: delete original source files if conversion succeeded (default FALSE)')
        print('--lossyjpg: convert JPEG files lossily (-d 1) (default FALSE)')
        print('--lossywebp: convert lossless WebP lossily (-d 1) (default FALSE)')
        print('--lossygif: convert GIF lossily (-d 1) (default FALSE)')
        print('--jobs: number of jobs (cjxl processes) to use (defaults to CPU core count), e.g. --jobs=8')
        print('--cjxl-extra-args: Additional parameters to pass to jxl, e.g. --cjxl-extra-args="-e 8" to set cjxl '
              'effort to 8')
        exit()

    arguments = {
        'delete': False,
        'lossyjpg': False,
        'lossywebp': False,
        'lossygif': False,
        'source': None,
        'cjxl_extra_args': [],
        'jobs': cpu_count(),
    }

    skip_next_argument = False
    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith('--'):
            if arg == '--delete':
                arguments['delete'] = True
            elif arg == '--lossyjpg':
                arguments['lossyjpg'] = True
            elif arg == '--lossywebp':
                arguments['lossywebp'] = True
            elif arg == '--lossygif':
                arguments['lossygif'] = True
            elif arg.startswith('--jobs='):
                try:
                    arguments['jobs'] = int(arg.split('=')[1])
                except ValueError:
                    print('Invalid value for --jobs. Must be an integer.')
                    exit()
                if arguments['jobs'] < 1:
                    print('Invalid value for --jobs. Must be greater than 0.')
                    exit()
            elif arg.startswith('--cjxl-extra-args='):
                arguments['cjxl_extra_args'] = arg.split('=')[1].split(' ')
            else:
                print('Unrecognized flag: ' + arg)
                exit()
        else:
            arguments['source'] = arg

    if arguments['source'] is None:
        print('Missing directory to process.')
        exit()

    pool = ThreadPool(arguments['jobs'])
    for root, subdirs, files in os.walk(arguments['source']):
        for filename in files:
            pool.apply_async(try_handle_file, (filename, root))
    pool.close()
    pool.join()

    if fsbefore == 0:
        print('No files were converted')
        exit()
    print('Before conversion: ' + str(fsbefore / 1024) + 'KB')
    print('After conversion: ' + str(fsafter / 1024) + 'KB')
    print('Reduction: ' + str((1 - fsafter / fsbefore) * 100) + '%')

if __name__ == '__main__':
    run()
