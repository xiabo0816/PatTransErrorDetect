# -*- coding: UTF-8 -*-

import os
import re
import argparse
import time
from tqdm import tqdm
import multiprocessing
from multiprocessing import Pool, TimeoutError
import time
import os
import random
import math
from lxml import etree
import lxml
from io import StringIO, BytesIO
import json
import sys
import traceback

"""
全局变量
"""
FILE_ENCODE = 'UTF-8'


"""
初始化
"""
#


def get_args_parser():
    parser = argparse.ArgumentParser(description='Data preprocess tool.')
    parser.add_argument('-i', '--input_list', type=str, default='input.list', help='input_list')
    parser.add_argument('-o', '--output_folder', type=str, default='output_folder', help='output_folder')
    parser.add_argument('-j', '--jobs', type=int, default=-1, help='njobs')
    return parser.parse_args()


def strB2Q(ustring):
    rstring = ''
    for uchar in ustring:
        inside_code = ord(uchar)
        if inside_code == 0x09:
            continue
        elif inside_code == 0x0a:
            continue
        elif inside_code < 9:
            inside_code = 12288
        elif inside_code > 9 and inside_code < 32:
            inside_code = 12288
        elif inside_code == 0x28:
            inside_code += 65248
        elif inside_code == 0x29:
            inside_code += 65248
        elif inside_code == 0x5B:
            inside_code += 65248
        elif inside_code == 0x5D:
            inside_code += 65248
        elif inside_code == 0x3A:
            inside_code = 12288
        elif inside_code == 0x3B:
            inside_code = 12288
        elif inside_code == 8212:
            inside_code = 45
        rstring += chr(inside_code)
    return rstring

def _detecter(args):
    try:
        print(args)
        output_file, input_ori_file, input_trans_file = args['output_file'], args['input_ori_file'], args['input_trans_file']
        # try:
        # file coding: UTF-8 with BOM
        root_origin = etree.parse(BytesIO(open(input_ori_file,   'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
        root_trans  = etree.parse(BytesIO(open(input_trans_file, 'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
        Paragraphs = {}
        Paragraphs['origin'] = root_origin.xpath('//base:Paragraphs/text()', namespaces=root_origin.nsmap)
        Paragraphs['trans']  = root_trans.xpath('//base:Paragraphs/text()', namespaces=root_trans.nsmap)
        print(Paragraphs)
        return (output_file, json.dumps(Paragraphs, ensure_ascii=False) + "\n")
    except:
        error_type, error_value, error_trace = sys.exc_info()
        print(sys.exc_info())


def readlist(path):
    if (path == ''):
        return []
    lines = [line.strip() for line in open(path, 'r', encoding=FILE_ENCODE).readlines()]
    return lines

if __name__ == '__main__':
    PROCESSES = multiprocessing.cpu_count()

    args = get_args_parser()
    print(args)

    fl = readlist(args.input_list)
    # print(fl)
    # fl = os.listdir(args.input_folder)

    if args.jobs != -1:
        PROCESSES = args.jobs

    print('Creating PatTransErrorDetect pool with %d processes\n' % PROCESSES)
    e1 = time.time()
    pool = Pool(PROCESSES)

    # 这种方式回调函数无法使用pbar变量
    # with tqdm(total=len(fl)) as pbar:
    pbar = tqdm(total=len(fl))

    def _callback_writefile(args):
        pbar.update(1)
        print(args)
        output_file, lines = args
        with open(output_file, 'a+', encoding='utf-8', errors="ignore") as f:
            f.writelines(lines)

    for i in range(len(fl)):
        input_ori_file = fl[i]
        basename, extension = os.path.splitext(os.path.basename(input_ori_file))
        if extension.lower() != '.xml':
            print(input_ori_file)
            continue
        input_trans_file = os.path.splitext(input_ori_file)[0] + '_trans' + extension
        param = {'input_ori_file':input_ori_file,'input_trans_file':input_trans_file,'output_file':args.output_folder}
        # print(root_origin)
        _detecter(param)
        # pool.apply_async(_detecter, args=(param, ), callback=_callback_writefile, stdin = subprocess.PIPE,)
        # pbar.update(1)

    pool.close()
    pool.join()
    # e2 = time.time()
    # print(float(e2 - e1))
    # print("Closing the XMLParser pool")
