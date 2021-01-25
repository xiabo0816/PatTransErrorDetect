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
# from nltk.stem import PorterStemmer
# g_stemmer = PorterStemmer()

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
MIN_MULTICHUNK_LEN = 30
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
    CONFIG = configparser.ConfigParser()
    CONFIG.read(path, encoding=FILE_ENCODE)

    ENDICT = {}
    ENDICT['words']   = readlist(CONFIG['DEFAULT']['words'])
    ENDICT['pattern'] = re.compile(r'([A-Z]{4,})')
    # print('ENDICT[\'words\'] length: ', len(ENDICT['words']))

    PATTERNS = []
    for field in CONFIG:
        if field == 'DEFAULT':
            continue
        if 'mode' not in CONFIG[field]:
            continue
        t = {}
        t['name'] = field
        t['mode'] = CONFIG[field]['mode']
        t['stat'] = CONFIG[field]['stat']
        t['patterns'] = []
        for item in CONFIG[field]:
            if item.startswith('__pattern__'):
                t['patterns'].append(re.compile(CONFIG[field][item]))
        PATTERNS.append(t)
    return CONFIG['DEFAULT'], ENDICT, PATTERNS


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


def _do_detect_mark(patterns, text):
    result = []
    for pattern in patterns:
        result.extend(pattern.findall(text))
    return result
    
def _do_detect_chunk(patterns, text):
    result = []
    for pattern in patterns:
        result.extend(pattern.findall(text))
    return result
    
def _do_detect_multichunk(patterns, text):
    result = []
    end = 0
    for pattern in patterns:
        # 由于.search只能识别出第一个，所以需要这个while循环：
        while end < len(text):
            s = pattern.search(text[end:])
            if s is None:
                break
            if len(s.group()) > MIN_MULTICHUNK_LEN:
                result.append(s.group().strip())
            end += s.span()[1]
    # print(result)
    # input()
    return result

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

def _do_detect(sections, text):
    results = []
    for section in sections:
        result = []
        if section['mode'] == 'mark':
            result = _do_detect_mark(section['patterns'], text)
        elif section['mode'] == 'chunk':
            result = _do_detect_chunk(section['patterns'], text)
        elif section['mode'] == 'multichunk':
            result = _do_detect_multichunk(section['patterns'], text)
        else:
            continue
        results.extend([{'name':section['name'], 'mode':section['mode'], 'stat':section['stat'], 'obj':item} for item in result if item != ''])
    
    # if len(results) > 0:
    #     print(results)
    #     input()
    return results

def _do_compare_mark(item, text):
    t = text.find(item)
    if t == -1:
        t = text.find(strQ2B(item))
    if t == -1:
        return False

    return True

def _do_compare_chunk(item, text):
    q2btext = strQ2B(text)
    if len(item) > MIN_CHUNK_LEN:
        t = text.find(item)
        if t == -1:
            t = q2btext.find(strQ2B(item))
        if t == -1:
            t = text.lower().find(item.lower())
        if t == -1:
            t = q2btext.replace(' ', '').lower().find(strQ2B(item).lower())
        if t == -1:
            return False
    return True

def _do_compare_multichunk(item, text):
    q2btext = strQ2B(text)
    if len(item) > MIN_CHUNK_LEN:
        t = text.find(item)
        if t == -1:
            t = q2btext.find(strQ2B(item))
        if t == -1:
            return False
    return True

def _do_compare(items, text):
    results = []
    for item in items:
        if item['mode'] == 'mark':
            if _do_compare_mark(item['obj'], text) == False:
                results.append(item)
        elif item['mode'] == 'chunk':
            if _do_compare_chunk(item['obj'], text) == False:
                results.append(item)
        elif item['mode'] == 'multichunk':
            if _do_compare_multichunk(item['obj'], text) == False:
                results.append(item)
        else:
            continue
    # if len(results) > 0:
    #     print(results)
    #     input()
    return results

def _dict_merge(dict1, dict2):
    res = {**dict1, **dict2}
    return res

def _run_detecter(args):
    try:
        output_file, input_ori_file, input_trans_file, SECTIONS, tag, ENDICT = args['output_file'], args[
            'input_ori_file'], args['input_trans_file'], args['sections'], args['tag'], args['endict']
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
        ParagraphsIndex = []
        max_eles_len = len(_trans_para_eles)
        if len(_origin_para_eles) > len(_trans_para_eles):
            max_eles_len = len(_origin_para_eles)

        for i in range(max_eles_len):
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
            _do_detect_result = _do_detect(SECTIONS, c_origin)
            
            if _do_detect_result is None:
                continue
            if len(_do_detect_result) == 0:
                continue

            _do_compare_result = _do_compare(_do_detect_result, c_trans)
            if _do_detect_result is None:
                continue
            if len(_do_compare_result) == 0:
                continue
                
            Paragraphs.extend([_dict_merge(item, {'idx': i}) for item in _do_compare_result])
            ParagraphsIndex.append({'input_ori_file': input_ori_file, 'input_trans_file': input_trans_file, 'c_origin': c_origin, 'c_trans': c_trans})
            # print(len(_do_compare_result), Paragraphs, len(ParagraphsIndex))
            # input()

        return Paragraphs, ParagraphsIndex
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

def _convert_new(tree, name, stat):
    tree[name] = {}
    tree[name]['name'] = name
    tree[name]['stat'] = stat
    if stat == 'single':
        tree[name]['children'] = []
    elif stat == 'poly':
        tree[name]['children'] = {}
    else:
        print('stat error in _convert_new, must be single/poly')
        return False
    return True

def _convert(ANCHORS, INDEX):
    """
    转换数据格式为html需要的格式
    """
    TREE = {}
    for item in ANCHORS:
        if item["name"] not in TREE:
            _convert_new(TREE, item["name"], item["stat"])
        if TREE[item["name"]]['stat'] == 'single':
            TREE[item["name"]]['children'].append(item)
        elif TREE[item["name"]]['stat'] == 'poly':
            if item["obj"] not in TREE[item["name"]]['children']:
                _convert_new(TREE[item["name"]]['children'], item["obj"], 'single')
            TREE[item["name"]]['children'][item["obj"]]['children'].append(item)
        else:
            print('stat error in _convert_new, must be single/poly')

    results = {}
    results['stat']   = _convert_stat(TREE, '')
    results['detail'] = _convert_detail(TREE)
    results['index']  = INDEX
    return results

def _convert_stat(tree, path):
    results = []
    for i in tree:
        item = tree[i]
        t = {}
        t['name'] = item['name']
        t['path']  = path + '/' + item['name']
        t['value'] = 0

        if item['stat'] == 'poly':
            t['children'] = _convert_stat(item['children'], t['path'])
            for c in t['children']:
                t['value'] += c["value"]
        if item['stat'] == 'single':
            t['value'] += len(item["children"])
        results.append(t)
    return results

def _convert_detail(tree):
    results = []
    for i in tree:
        item = tree[i]
        one = []
        if item['stat'] == 'poly':
            one = _convert_detail(item['children'])
        if item['stat'] == 'single':
            one = item["children"]
        results.extend(one)
    return results

if __name__ == '__main__':
    PROCESSES = multiprocessing.cpu_count()

    args = get_args_parser()
    print(args)

    print('Reading configure file...')
    DEFAULT, ENDICT, SECTIONS = readconfig(args.config)
    print(DEFAULT, len(ENDICT), SECTIONS)

    FILELIST = readlist(args.input_list)
    # print(FILELIST)
    # fl = os.listdir(args.input_folder)

    # if args.jobs != -1:
    #     PROCESSES = args.jobs

    # pbar = tqdm(total=len(FILELIST))

    count = 0
    STAT = {}
    ANCHORS = []
    INDEX   = []
    # 这种方式回调函数无法使用pbar变量
    with tqdm(total=len(FILELIST)) as pbar:
        for i in range(len(FILELIST)):
            input_ori_file = FILELIST[i]
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
                     'sections': SECTIONS, 'tag': DEFAULT['TAG'], 'endict':ENDICT}
            # print(root_origin)
            t, tidx = _run_detecter(param)
            if t is None:
                continue
            if len(t) == 0:
                continue
            ANCHORS.extend([_dict_merge(item, {'id': i}) for item in t])
            INDEX.append(tidx)
            pbar.update(1)
    # print(Paragraphs)
    json.dump(_convert(ANCHORS, INDEX), open(args.output_file+'.anchors.json', 'w', encoding='utf-8',
                            errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

    # json.dump(ANCHORS, open(args.output_file+'.ori.json', 'w', encoding='utf-8',
    #                         errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

    # STAT = sorted(STAT.items(), key=lambda x: x[1], reverse=True)
    # json.dump(dict(STAT), open(args.output_file+'.stat.json', 'w', encoding='utf-8',
    #                            errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

