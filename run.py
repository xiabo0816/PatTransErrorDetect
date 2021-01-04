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
# https://lxml.de/apidoc/lxml.htmlhttps://lxml.de/tutorial.html
# https://lxml.de/apidoc/lxml.html

from io import StringIO, BytesIO
import json
import sys
import traceback
import configparser
import re
# https://docs.python.org/zh-cn/3.9/library/configparser.html

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
    parser.add_argument('-c', '--config', type=str, default='config.ini', help='config.ini')
    # parser.add_argument('-j', '--jobs', type=int, default=-1, help='njobs')
    return parser.parse_args()

def readconfig(path):
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config


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

def strQ2B(ustring):
    rstring = ''
    for uchar in ustring:
        inside_code = ord(uchar)
        inside_code -= 65248
        rstring += chr(inside_code)
    return rstring

def _do_detect(patterns, text):
    results = []
    for pattern in patterns:
        # text = u"毛刺　Ａ　１ 127210853300_E2_C2_P2.bmp"
        results.append(pattern.findall(text))
    return results

def _run_detecter(args):
    try:
        print(args)
        output_file, input_ori_file, input_trans_file, patterns = args['output_file'], args['input_ori_file'], args['input_trans_file'], args['patterns']
        # try:
        # file coding: UTF-8 with BOM
        root_origin = etree.parse(BytesIO(open(input_ori_file,   'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
        root_trans  = etree.parse(BytesIO(open(input_trans_file, 'rb').read()), etree.XMLParser(ns_clean=True)).getroot()

        _origin_para_eles = root_origin.xpath('//base:Paragraphs', namespaces=root_origin.nsmap)
        _trans_para_eles  = root_trans.xpath('//base:Paragraphs', namespaces=root_trans.nsmap)
        # print(_trans_para_eles[0].text)

        Paragraphs = []
        max_len = len(_trans_para_eles)
        if len(_origin_para_eles) > len(_trans_para_eles):
            max_len = len(_origin_para_eles)

        for i in range(max_len):
            c_origin = ''
            c_trans  = ''
            if i < len(_origin_para_eles):
                c_origin = _origin_para_eles[i].text.strip()
            if i < len(_trans_para_eles):
                c_trans = _trans_para_eles[i].text.strip()
            # print(c_origin, c_trans)
            dtorigins = _do_detect(patterns, c_origin)
            dttranss  = _do_detect(patterns, c_origin)

            print(dtorigin)
            if dtorigin is not None and  len(dtorigin) > 0:
                print([[strQ2B(item) for item in dtorigin] for dtorigin in dtorigins])
            # print(dttrans)
            input()

        # return (output_file, json.dumps(Paragraphs, ensure_ascii=False) + "\n")
    except:
        error_type, error_value, error_trace = sys.exc_info()
        print(sys.exc_info())


def readlist(path):
    if (path == ''):
        return []
    lines = [line.strip() for line in open(path, 'r', encoding=FILE_ENCODE).readlines()]
    return lines

def _callback_writefile(args):
    pbar.update(1)
    print(args)
    output_file, lines = args
    with open(output_file, 'a+', encoding='utf-8', errors="ignore") as f:
        f.writelines(lines)
        
if __name__ == '__main__':
    PROCESSES = multiprocessing.cpu_count()

    args = get_args_parser()
    print(args)

    CONFIG = readconfig(args.config)
    print(CONFIG.sections())

    PATTERNS = []
    for field in CONFIG['TAGS']:
        PATTERNS.append(re.compile(CONFIG['TAGS'][field]))
    print(PATTERNS)

    fl = readlist(args.input_list)
    # print(fl)
    # fl = os.listdir(args.input_folder)

    # if args.jobs != -1:
    #     PROCESSES = args.jobs

    pbar = tqdm(total=len(fl))
    # 这种方式回调函数无法使用pbar变量
    with tqdm(total=len(fl)) as pbar:
        for i in range(len(fl)):
            input_ori_file = fl[i]
            basename, extension = os.path.splitext(os.path.basename(input_ori_file))
            if extension.lower() != '.xml':
                print(input_ori_file)
                continue

            input_trans_file = os.path.splitext(input_ori_file)[0] + '_trans' + extension

            if not os.path.exists(input_ori_file):
                print('\nFile not exists: ' + input_ori_file)
                continue

            if not os.path.exists(input_trans_file):
                print('\nFile not exists: ' + input_trans_file)
                continue

            param = {'input_ori_file':input_ori_file,'input_trans_file':input_trans_file,'output_file':args.output_folder,'patterns':PATTERNS}
            # print(root_origin)
            _run_detecter(param)
