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
# https://docs.python.org/zh-cn/3.9/library/configparser.html
import re
import html
from nltk.stem import PorterStemmer
g_stemmer = PorterStemmer()

"""
全局变量
"""
# 文件编码
FILE_ENCODE = 'UTF-8'

# 最小字串长度
MIN_CHUNK_LEN = 2
# 最大HTML转义次数
MAX_HTMLENTITIES_TIMES = 5
# 最小参考文献长度
MIN_REFERENCE_LEN = 30
# 全角字符匹配失败的时候，是否回退到半角字符进行匹配
IS_FULLWIDTH_FALLBACK = True

"""
初始化
"""
#


def get_args_parser():
    parser = argparse.ArgumentParser(description='Data preprocess tool.')
    parser.add_argument('-i', '--input_list', type=str,
                        default='input.list', help='input_list')
    parser.add_argument('-o', '--output_file', type=str,
                        default='output_file', help='output_file')
    parser.add_argument('-c', '--config', type=str,
                        default='config.ini', help='config.ini')
    # parser.add_argument('-j', '--jobs', type=int, default=-1, help='njobs')
    return parser.parse_args()


def readconfig(path):
    config = configparser.ConfigParser()
    config.read('config.ini', encoding=FILE_ENCODE)
    return config


def reference(line):
    MAX_HTMLENTITIES_TIMES = 5
    for i in range(MAX_HTMLENTITIES_TIMES):
        line = html.unescape(line)
    return line


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
        if inside_code > 65248:
            inside_code -= 65248
        rstring += chr(inside_code)
    return rstring


def _do_compare_mark(targets, text):
    results = []
    for target in targets:
        t = text.find(target[0])
        if t == -1:
            t = text.find(strQ2B(target[0]))
        if t == -1:
            results.append(target)
        # print(t, target, text)
        # input()
        # print()

    return results


def _do_compare_chunk(targets, text):
    results = []
    q2btext = strQ2B(text)
    for target in targets:
        if len(target[0]) > MIN_CHUNK_LEN:
            t = text.find(target[0])
            if t == -1:
                t = q2btext.find(strQ2B(target[0]))
            if t == -1:
                t = text.lower().find(target[0].lower())
            if t == -1:
                t = q2btext.replace(' ', '').lower().find(strQ2B(target[0]).lower())
            if t == -1:
                results.append(target)
            # print(t, target, text)
            # input()
            # print()

    return results


def _do_compare_reference(targets, text):
    results = []
    q2btext = strQ2B(text)
    for target in targets:
        if len(target[0]) > MIN_CHUNK_LEN:
            t = text.find(target[0])
            if t == -1:
                t = q2btext.find(strQ2B(target[0]))
            if t == -1:
                results.append(target)
            # print(t, target, text)
            # input()
            # print()

    return results

def _do_detect(patterns, text):
    results = []
    for pattern in patterns:
        # text = u"毛刺　Ａ　１ 127210853300_E2_C2_P2.bmp"
        if pattern[0].startswith('__multichunk__'):
            result = []
            end = 0
            # 由于.search只能识别出第一个，所以需要这个while循环：
            while end < len(text):
                s = pattern[1].search(text[end:])
                if s is None:
                    break
                if len(s.group()) > MIN_REFERENCE_LEN:
                    result.append(s.group())
                end += s.span()[1]
        else:
            result = pattern[1].findall(text)
        results.extend([(item, pattern[0]) for item in result])
        
    return results

def _do_detect_names(endict, text):
    results = []
    for word in endict['pattern'].findall(text):
        result = []
        if re.sub(r'[AGCT]', '', word) == '':
            continue
        if word.lower() not in endict['words'] and g_stemmer.stem(word) not in endict['words']:
            result.append(word)
        results.append(result)
    return results

def _run_detecter(args):
    try:
        output_file, input_ori_file, input_trans_file, MARKS, CHUNKS, REFERENCE, tag, ENDICT = args['output_file'], args[
            'input_ori_file'], args['input_trans_file'], args['MARKS'], args['CHUNKS'], args['REFERENCE'], args['tag'], args['endict']
        # try:
        # file coding: UTF-8 with BOM
        # etree.ElementTree.register_namespace('', 'http://your/uri')
        root_origin = etree.parse(BytesIO(
            open(input_ori_file,   'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
        root_trans = etree.parse(BytesIO(
            open(input_trans_file, 'rb').read()), etree.XMLParser(ns_clean=True)).getroot()
        _origin_para_eles = root_origin.xpath(
            tag, namespaces=root_origin.nsmap)
        _trans_para_eles = root_trans.xpath(tag, namespaces=root_trans.nsmap)
        # print(_trans_para_eles[0].text)

        Paragraphs = []
        max_len = len(_trans_para_eles)
        if len(_origin_para_eles) > len(_trans_para_eles):
            max_len = len(_origin_para_eles)

        for i in range(max_len):
            c_origin = ''
            c_trans = ''
            if i < len(_origin_para_eles):
                c_origin = _del_xml_first_attr(etree.tostring(
                    _origin_para_eles[i], encoding='unicode').strip())
                # c_origin = _origin_para_eles[i].text.strip()
            if i < len(_trans_para_eles):
                # c_origin = _origin_para_eles[i].text.strip()
                c_trans = _del_xml_first_attr(etree.tostring(
                    _trans_para_eles[i], encoding='unicode').strip())
            # print(c_origin, c_trans)
            dtmarks = _do_detect(MARKS, c_origin)
            dtchunks = _do_detect(CHUNKS, c_origin)
            dtreferences = _do_detect(REFERENCE, c_origin)
            # dtnames = _do_detect_names(ENDICT, c_origin)
            # print(dtmarks, dtchunks, dtreferences)
            # print(c_origin)
            if dtmarks is not None and len(dtmarks) > 0:
                marks = _do_compare_mark(dtmarks, c_trans)
                if len(marks) > 0:
                    Paragraphs.append(
                        (input_ori_file, input_trans_file, marks, c_origin, c_trans))

            if dtchunks is not None and len(dtchunks) > 0:
                chunks = _do_compare_chunk(dtchunks, c_trans)
                if len(chunks) > 0:
                    Paragraphs.append(
                        (input_ori_file, input_trans_file, chunks, c_origin, c_trans))

            if dtreferences is not None and len(dtreferences) > 0:
                references = _do_compare_reference(dtreferences, c_trans)
                if len(references) > 0:
                    Paragraphs.append(
                        (input_ori_file, input_trans_file, references, c_origin, c_trans))

            # if dtnames is not None and len(dtnames) > 0:
            #     names = _do_compare_chunk(dtnames, c_trans)
            #     if len(names) > 0:
            #         Paragraphs.append(
            #             (input_ori_file, input_trans_file, names, c_origin, c_trans))
            # print(dttrans)
            # input()
        return Paragraphs
        # return (output_file, json.dumps(Paragraphs, ensure_ascii=False) + "\n")
    except:
        error_type, error_value, error_trace = sys.exc_info()
        print(sys.exc_info())


def readlist(path):
    if (path == ''):
        return []
    lines = [line.strip() for line in open(
        path, 'r', encoding=FILE_ENCODE).readlines()]
    return lines


def _callback_writefile(args):
    pbar.update(1)
    print(args)
    output_file, lines = args
    with open(output_file, 'a+', encoding='utf-8', errors="ignore") as f:
        f.writelines(lines)


def _del_xml_tag(line):
    return re.sub(r'<(/|\?)?\w+[^>]*>', '', line)


def _del_xml_first_attr(line):
    return re.sub(r'^(<[^>\s]+)\s[^>]+?(>)', r'\1\2', line)


def _plot_stat(stat):
    """
    对识别出的每个字符串画出频率柱状图
    """
    import matplotlib.pyplot as plt
    import numpy as np
    x = stat.keys()
    y = stat.values()
    plt.figure()
    plt.plot(x, y)
    plt.show()

def _write_html(Paragraphs):
    FOUT = open(args.output_file+'.html', 'w',
                encoding='utf-8', errors="ignore")
    FOUT.writelines('<style>td{table-layout: fixed; overflow: hidden; word-break: break-all;}textarea{width: 100%; height: 250px;}td:nth-child(1),td:nth-child(2),td:nth-child(3){width: 10%; }td:nth-child(4),td:nth-child(5){width: 34%; }</style>')
    FOUT.writelines('<table>')

    for Paragraph in Paragraphs:
        if Paragraph is not None:
            for c in Paragraph[2]:
                if c not in STAT:
                    STAT[c] = 1
                STAT[c] += 1
            # print(Paragraph)
            # input()
            FOUT.writelines('<tr>\n')
            FOUT.writelines('<td>'+str(Paragraph[0]) + '</td>\n')
            FOUT.writelines('<td>'+str(Paragraph[1]) + '</td>\n')
            # FOUT.writelines('<td>'+str(Paragraph[2]) + '</td>\n')
            FOUT.writelines('<td><textarea disabled>' +
                            str(Paragraph[2]) + '</textarea></td>\n')

            # c3 = str(Paragraph[3])
            # c4 = str(Paragraph[3])
            # for c in Paragraph[2]:
            #     c3 = c3.replace(c, '<b>'+c+'</b>')
            # for c in Paragraph[2]:
            #     c4 = c4.replace(c, '<b>'+c+'</b>')
            # FOUT.writelines('<td><textarea disabled>'+str(c3) + '</textarea></td>\n')
            # FOUT.writelines('<td><textarea disabled>'+str(c4) + '</textarea></td>\n')

            FOUT.writelines('<td><textarea disabled>' +
                            str(Paragraph[3]) + '</textarea></td>\n')
            FOUT.writelines('<td><textarea disabled>' +
                            str(Paragraph[4]) + '</textarea></td>\n')
            # FOUT.writelines('<td>'+html.escape(str(Paragraph[3])) + '</td>\n')
            # FOUT.writelines('<td>'+html.escape(str(Paragraph[4])) + '</td>\n')
            FOUT.writelines('</tr>\n')
            count += 1
    FOUT.writelines('</table>')
    FOUT.close()
if __name__ == '__main__':
    PROCESSES = multiprocessing.cpu_count()

    args = get_args_parser()
    print(args)

    CONFIG = readconfig(args.config)
    print(CONFIG.sections())

    ENDICT = {}
    ENDICT['words']   = readlist(CONFIG['DICTIONARY']['words'])
    ENDICT['pattern'] = re.compile(CONFIG['DICTIONARY']['pattern'])
    print('ENDICT length: ', len(ENDICT))

    MARKS = []
    for field in CONFIG['MARKS']:
        MARKS.append((field, re.compile(CONFIG['MARKS'][field])))
    print(MARKS)

    CHUNKS = []
    for field in CONFIG['CHUNKS']:
        CHUNKS.append((field, re.compile(CONFIG['CHUNKS'][field])))
    print(CHUNKS)

    REFERENCE = []
    for field in CONFIG['REFERENCE']:
        REFERENCE.append((field, re.compile(CONFIG['REFERENCE'][field])))
    print(REFERENCE)

    fl = readlist(args.input_list)
    # print(fl)
    # fl = os.listdir(args.input_folder)

    # if args.jobs != -1:
    #     PROCESSES = args.jobs

    # pbar = tqdm(total=len(fl))

    count = 0
    STAT = {}
    Paragraphs = []
    # 这种方式回调函数无法使用pbar变量
    with tqdm(total=len(fl)) as pbar:
        for i in range(len(fl)):
            input_ori_file = fl[i]
            basename, extension = os.path.splitext(
                os.path.basename(input_ori_file))
            if extension.lower() != '.xml':
                print(input_ori_file)
                continue

            input_trans_file = os.path.splitext(
                input_ori_file)[0] + '_trans' + extension

            if not os.path.exists(input_ori_file):
                print('\nFile not exists: ' + input_ori_file)
                continue

            if not os.path.exists(input_trans_file):
                print('\nFile not exists: ' + input_trans_file)
                continue

            param = {'input_ori_file': input_ori_file, 'input_trans_file': input_trans_file, 'output_file': args.output_file,
                     'MARKS': MARKS, 'CHUNKS': CHUNKS, 'REFERENCE': REFERENCE, 'tag': CONFIG['COMMON']['TAG'], 'endict':ENDICT}
            # print(root_origin)
            t = _run_detecter(param)
            if len(t) == 0:
                continue
            Paragraphs.append(t)
            pbar.update(1)
    print(Paragraphs)
    json.dump(Paragraphs, open(args.output_file+'.paragraphs.json', 'w', encoding='utf-8',
                            errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)
    print(count)
    STAT = sorted(STAT.items(), key=lambda x: x[1], reverse=True)
    json.dump(dict(STAT), open(args.output_file+'.stat.json', 'w', encoding='utf-8',
                               errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)