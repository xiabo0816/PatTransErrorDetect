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

FILE_ENCODE = 'UTF-8'

"""
初始化
"""
#
"""
全局变量
"""
#

def get_args_parser():
    parser = argparse.ArgumentParser(description='Data preprocess tool.')
    parser.add_argument('-i', '--input_list', type=str, default='addon2.list', help='input_list')
    parser.add_argument('-o', '--output_file', type=str, default='addon2.txt', help='output_file')
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

def gettb(description):
    technology = ''
    background = ''
    tmp = []
    bool_tech, bool_bg = False, False
    for idx in description.split('\n'):
        idx = idx.replace('所属', '').replace('（', '').replace('）', '').replace('【', '').replace('】','').replace('.', '').replace('I', '').replace('、', '').replace('\n', '').replace('\t', '').replace(' ','').replace('\xa0', '').replace('</b>', '').replace('<b>', '')
        idx = re.sub(r'[\d+一二三四五六七八九十]', "", idx)
        if bool_tech:
            if idx == '背景技术' or idx == '技术背景':
                technology = ''.join(tmp)
                tmp = []
                bool_tech = False
            else:
                tmp.append(idx)
        if bool_bg:
            if idx == '发明内容' or idx == '内容发明' or idx == '申请内容' or idx == '发明创造' or idx == '技术方案' or idx == '附图说明':
                background = ''.join(tmp)
                tmp = []
                bool_bg = False
            else:
                tmp.append(idx)

        if idx == '技术领域' or idx == '领域技术' or idx == '发明领域' or idx == '领域发明':
            bool_tech = True
        if idx == '背景技术' or idx == '技术背景':
            bool_bg = True
    return technology, background
    
def _cleaner(args):
    output_file, input_file = args['output_file'], args['input_file']
    patent = {}
    # try:
    # file coding: UTF-8 with BOM
    root = etree.parse(BytesIO(open(input_file, 'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
    ipcs = root.xpath('//classification-ipcr/text/text()', namespaces=root.nsmap)
    patent['ipc'] = []
    for item in ipcs:
        patent['ipc'].append(item.replace(" ", ""))
    patent['aid'] = strB2Q(''.join(root.xpath('//application-reference//doc-number/text()', namespaces=root.nsmap)))
    patent['title'] = strB2Q(''.join(root.xpath('//cn-bibliographic-data/invention-title/text()', namespaces=root.nsmap)))
    patent['abstract'] = strB2Q(''.join(root.xpath('//abstract/p/text()', namespaces=root.nsmap)))
    patent['claims'] = strB2Q(''.join(root.xpath('//claim/claim-text/text()', namespaces=root.nsmap)))
    description = ''.join(root.xpath('//description//p/text()', namespaces=root.nsmap))
    technology, background = gettb(description)
    if (technology != "" and background != ""):
        patent['description'] = {}
        patent['description']['technology'] = strB2Q(technology)
        patent['description']['background'] = strB2Q(background)
    else:
        patent['description'] = strB2Q(description)[0:512]
    return (output_file, json.dumps(patent, ensure_ascii=False) + "\n")


def cbwritefile(args):
    output_file, lines = args
    with open(output_file, 'a+', encoding='utf-8', errors="ignore") as f:
        f.writelines(lines)


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
    print(fl)
    # fl = os.listdir(args.input_folder)

    if args.jobs != -1:
        PROCESSES = args.jobs

    print('Creating XMLParser pool with %d processes\n' % PROCESSES)
    e1 = time.time()
    pool = Pool(PROCESSES)

    with tqdm(total=len(fl)) as pbar:
        for i in range(len(fl)):
            param = {'input_file':fl[i],'output_file':args.output_file}
            pool.apply_async(_cleaner, args=(param, ), callback=cbwritefile)
            pbar.update(1)

    pool.close()
    pool.join()
    e2 = time.time()
    print(float(e2 - e1))

    print("Closing the XMLParser pool")
