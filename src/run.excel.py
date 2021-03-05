# -*- coding: UTF-8 -*-

import os
import re
import regex
import argparse
import time
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
import configparser
# https://docs.python.org/zh-cn/3.9/library/configparser.html
import re
import html
import globals
# from nltk.stem import PorterStemmer
# g_stemmer = PorterStemmer()
# from tqdm import tqdm
import globals
import copy
import csv
import xlrd

"""
全局变量
"""
# 文件编码
FILE_ENCODE = 'UTF-8'
# 输出文件编码
OUT_FILE_ENCODE = 'GBK'
# 最小字串长度
MIN_CHUNK_LEN = 2
# 最大HTML转义次数
MAX_HTMLENTITIES_TIMES = 5
# 每个标签内的每个种类的最大错误数
MAX_ERROR_TIMES_PERTAG_PERTYPE = 10
# 每类问题内最多的实例数
MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV = 100
# 最小参考文献长度
MIN_MULTICHUNK_LEN = 30
# 每个标签内文章的最大长度
MAX_LENGTH_PERTAG = 10240
# 全角字符匹配失败的时候，是否回退到半角字符进行匹配
IS_FULLWIDTH_FALLBACK = True
# XML原文文件名形式
FILE_NAME_PATTERN = '(.+\.xlsx$)|(.+\.xls$)'

"""
初始化
"""
global ANCHORS
global INDEX
global INDEXFILE
global INDEXFILECOUNT
ANCHORS = []
INDEX   = []
INDEXFILE = []
INDEXFILECOUNT = 0

def get_args_parser():
    parser = argparse.ArgumentParser(description='专利机翻检测工具 - excel')
    parser.add_argument('-i', '--input_folder', type=str,
                        default='input.list', help='输入文件夹名')
    parser.add_argument('-o', '--output_folder', type=str,
                        default='output_folder', help='输出文件夹名称前缀')
    parser.add_argument('-c', '--config', type=str,
                        default='config.ini', help='配置文件')
    parser.add_argument('-j', '--jobs', type=int, default=-1, help='进程数，一般默认即可')
    return parser.parse_args()


def readconfig(path):
    global MAX_ERROR_TIMES_PERTAG_PERTYPE
    global MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV
    global MAX_LENGTH_PERTAG

    CONFIG = configparser.ConfigParser()
    CONFIG.read(path, encoding=FILE_ENCODE)

    ENDICT = {}
    # ENDICT['words']   = readlist(CONFIG['DEFAULT']['words'])
    # ENDICT['pattern'] = re.compile(r'([A-Z]{4,})')
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
        t['escapes'] = []
        for item in CONFIG[field]:
            if item.startswith('__pattern__'):
                t['patterns'].append(re.compile(CONFIG[field][item]))
            if item.startswith('__escape__'):
                t['escapes'].append(re.compile(CONFIG[field][item]))
        PATTERNS.append(t)

    if 'MAX_ERROR_TIMES_PERTAG_PERTYPE' in CONFIG['DEFAULT']:
        MAX_ERROR_TIMES_PERTAG_PERTYPE = int(CONFIG['DEFAULT']['MAX_ERROR_TIMES_PERTAG_PERTYPE'])

    if 'MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV' in CONFIG['DEFAULT']:
        MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV = int(CONFIG['DEFAULT']['MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV'])

    if 'MAX_LENGTH_PERTAG' in CONFIG['DEFAULT']:
        MAX_LENGTH_PERTAG = int(CONFIG['DEFAULT']['MAX_LENGTH_PERTAG'])

    if 'FILE_NAME_PATTERN' in CONFIG['DEFAULT']:
        FILE_NAME_PATTERN = CONFIG['DEFAULT']['FILE_NAME_PATTERN']

    return CONFIG['DEFAULT'], ENDICT, PATTERNS


def reference(line):
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

def _do_detect_escapes(escapes, items):
    result = []
    for item in items:
        t = [escape for escape in escapes if not escape.search(item) is None]
        if len(t) == 0:
            result.append(item)
        # else:
        #     print(item)
    return result

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

        result = _do_detect_escapes(section['escapes'], result)

        if len(result) > MAX_ERROR_TIMES_PERTAG_PERTYPE:
            result = result[:MAX_ERROR_TIMES_PERTAG_PERTYPE]
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
        input_file, SECTIONS, tag, ENDICT = args['input_file'], args['sections'], args['tag'], args['endict']
        # print(input_file)
        book = xlrd.open_workbook(input_file)
        _origin_para_eles = []
        _trans_para_eles = []
        for sheet in book.sheets():
            for row in range(1, sheet.nrows):
                # print(sheet.cell_value(row, 1), sheet.cell_value(row, 2))
                origin_cell = sheet.cell(row, 1)
                trans_cell = sheet.cell(row, 2)
                if (origin_cell.ctype == 1 and trans_cell.ctype == 1):
                    _origin_para_eles.append(origin_cell.value)
                    _trans_para_eles.append(trans_cell.value)
                if (origin_cell.ctype == 2 and trans_cell.ctype == 2):
                    _origin_para_eles.append(str(origin_cell.value))
                    _trans_para_eles.append(str(trans_cell.value))
                # _origin_para_eles.append(origin_cell.value)
                # _trans_para_eles.append(trans_cell.value)

        Paragraphs = []
        ParagraphsIndex = []
        ParagraphsIndexCount = 0
        max_eles_len = len(_trans_para_eles)
        if len(_origin_para_eles) > len(_trans_para_eles):
            max_eles_len = len(_origin_para_eles)

        # print(len(_origin_para_eles))
        # print(len(_trans_para_eles))
        # print(max_eles_len)

        for i in range(max_eles_len):
            c_origin = _origin_para_eles[i]
            c_trans = _trans_para_eles[i]
            # print(c_origin, c_trans)
            # print(type(c_origin), type(c_trans))
            _do_detect_result = _do_detect(SECTIONS, c_origin)
    
            if _do_detect_result is None:
                continue
            if len(_do_detect_result) == 0:
                continue

            _do_compare_result = _do_compare(_do_detect_result, c_trans)
            # print(_do_detect_result)
            # print(_do_compare_result)
            # print(c_origin, c_trans)
            if _do_compare_result is None:
                continue
            if len(_do_compare_result) == 0:
                continue

            Paragraphs.extend([_dict_merge(item, {'idx': ParagraphsIndexCount}) for item in _do_compare_result])
            # print('Paragraphs',Paragraphs)
            ParagraphsIndex.append({'c_origin': c_origin[:MAX_LENGTH_PERTAG], 'c_trans': c_trans[:MAX_LENGTH_PERTAG]})
            ParagraphsIndexCount += 1

        return (Paragraphs, ParagraphsIndex, input_file, input_file)
    except:
        globals.print_tb()
        # error_type, error_value, error_trace = sys.exc_info()
        # print(error_type)
        # print(error_value)
        # print(traceback.print_tb(error_trace))
        return ([], [], [], [])


# def readlist(path):
#     if (path == ''):
#         return []
#     lines = [line.strip() for line in open(path, 'r', encoding=FILE_ENCODE).readlines()]
#     return lines

def read_input_folder(path):
    allfile = []
    filename_pattern = re.compile(FILE_NAME_PATTERN)
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if filename_pattern.match(filename):
                allfile.append(os.path.join(dirpath,filename))
    return allfile

def _run_detecter_callback(args):
    global ANCHORS
    global INDEX
    global INDEXFILE
    global INDEXFILECOUNT

    globals.update(1)
    t, tidx, input_ori_file, input_trans_file = args
    if t is None:
        return
    if len(t) == 0:
        return
    ANCHORS.extend([_dict_merge(item, {'index':{"id":INDEXFILECOUNT, "idx":item['idx']}}) for item in t])
    INDEXFILE.append({'input_ori_file': input_ori_file, 'input_trans_file': input_trans_file})
    INDEX.append(tidx)
    INDEXFILECOUNT += 1


def _del_xml_tag(line):
    return re.sub(r'<(/|\?)?\w+[^>]*>', '', line)


def _del_xml_first_attr(line):
    return re.sub(r'^(<[^>\s]+)\s[^>]+?(>)', r'\1\2', line)

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

def _corvert(ANCHORS, INDEX, INDEXFILE):
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
    results['indexfile']  = INDEXFILE

    results['stat'] = sorted(results['stat'], key=lambda x: x['value'], reverse=True)
    return results

def _save_visual_files(ANCHORS, INDEX, INDEXFILE, output_folder, SECTIONS):
    if not os.path.exists(output_folder):
        os.mkdir(output_folder, 0o755)

    results = _corvert(ANCHORS, INDEX, INDEXFILE)

    json.dump(results['stat'], open(os.path.join(output_folder, 'stats.json'), 'w', encoding='utf-8',
                        errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)
    
    for section in SECTIONS:
        section_details = []
        section_details_counter = {}
        section_index = []
        section_indexfile = []

        for detail in results['detail']:
            if detail['name'] == section['name']:
                section_indexfile_find = [x for x,y in enumerate(section_indexfile) if y == detail['index']['id']]
                if len(section_indexfile_find) == 0:
                    section_indexfile.append(detail['index']['id'])
                    section_indexfile_find = [len(section_indexfile) - 1]
                    section_index.append([])

                if detail["obj"] not in section_details_counter:
                    section_details_counter[detail["obj"]] = 0

                if detail["stat"] == 'poly' and section_details_counter[detail["obj"]] > int(MAX_ERROR_TIMES_PERTAG_PERTYPE):
                    continue
                
                if detail["stat"] == 'single' and section_details_counter[detail["obj"]] > 50 * int(MAX_ERROR_TIMES_PERTAG_PERTYPE):
                    continue
                
                section_index_find = [x for x,y in enumerate(section_index[section_indexfile_find[0]]) if y == detail['index']['idx']]
                if len(section_index_find) == 0:
                    section_index[section_indexfile_find[0]].append(detail['index']['idx'])
                    section_index_find = [len(section_index[section_indexfile_find[0]]) - 1]

                # print(detail)
                # print(section_indexfile_find,section_index_find)

                section_details.append({
                    "name": detail["name"],
                    "mode": detail["mode"],
                    "stat": detail["stat"],
                    "obj": detail["obj"],
                    "index": {
                        "id": section_indexfile_find[0],
                        "idx": section_index_find[0]
                    }
                })
                section_details_counter[detail["obj"]] += 1

        json.dump(section_details, open(os.path.join(output_folder, section['name']+'.details.json'), 'w', encoding='utf-8',
                        errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)
        json.dump([[INDEX[section_indexfile[index]][item] for item in section_index[index]] for index,_ in enumerate(section_index)], open(os.path.join(output_folder, section['name']+'.idx.json'), 'w', encoding='utf-8',
                        errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)
        json.dump([INDEXFILE[item] for item in section_indexfile], open(os.path.join(output_folder, section['name']+'.id.json'), 'w', encoding='utf-8',
                        errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

    return results['stat']


def _save_csv_files(ANCHORS, INDEX, INDEXFILE, output_folder, SECTIONS):
    if not os.path.exists(output_folder):
        os.mkdir(output_folder, 0o755)

    results = _corvert(ANCHORS, INDEX, INDEXFILE)

    for section in SECTIONS:
        section_details_content = {}
        for detail in results['detail']:
            myname = str(detail['index']['id']) + '_' + str(detail['index']['idx']) + detail["obj"] 
            if detail['name'] != section['name']:
                continue
            if myname not in section_details_content:
                section_details_content[myname] = {}
                section_details_content[myname]['name'] = detail["name"]
                section_details_content[myname]['obj']  = detail["obj"]
                section_details_content[myname]['count'] = 0
                section_details_content[myname]['input_ori_file']   = INDEXFILE[detail['index']['id']]['input_ori_file']
                section_details_content[myname]['input_trans_file'] = INDEXFILE[detail['index']['id']]['input_trans_file']
                section_details_content[myname]['c_origin'] = regex.sub("[\n\r\t,]+", "", INDEX[detail['index']['id']][detail['index']['idx']]['c_origin'])[:MAX_LENGTH_PERTAG]
                section_details_content[myname]['c_trans']  = regex.sub("[\n\r\t,]+", "", INDEX[detail['index']['id']][detail['index']['idx']]['c_trans'])[:MAX_LENGTH_PERTAG]

            section_details_content[myname]['count'] += 1

        # section_details = []
        section_details_counter = 0
        fout = open(os.path.join(output_folder, section['name']+'.csv'), 'w', encoding=OUT_FILE_ENCODE, errors="ignore", newline='')
        writer = csv.writer(fout)
        writer.writerow(["类型", "内容", "频次", "原文路径", "译文路径", "原文", "译文"]) #这里要以list形式写入，writer会在新建的csv文件中，一行一行写入
        for key in section_details_content:
            t = section_details_content[key]
            writer.writerow([t["name"], t["obj"], t["count"], t["input_ori_file"], t["input_trans_file"], t["c_origin"], t["c_trans"]]) #这里要以list形式写入，writer会在新建的csv文件中，一行一行写入
            if section_details_counter > int(MAX_ERROR_TIMES_PERTAG_PERTYPE_CSV):
                continue
            section_details_counter += 1
        fout.close()
        # fout = pd.DataFrame(section_details)
        # fout.to_csv(os.path.join(output_folder, section['name']+'.csv'), index = 0, encoding='utf_8_sig')
    return results['stat']


def _save_anchor_files(ANCHORS, output_folder):
    if not os.path.exists(output_folder):
        os.mkdir(output_folder, 0o755)

    # results = _corvert(ANCHORS, INDEX, INDEXFILE)

    results = {}
    for anchor in ANCHORS:
        if anchor['name'] not in results:
            results[anchor['name']] = set()
        results[anchor['name']].add(anchor['obj'])
    
    for key in results.keys():
        fout = open(os.path.join(output_folder, key+'.txt'), 'w', encoding='utf-8', errors="ignore", newline='')
        fout.writelines([item+'\n' for item in results[key]])
        # writer = csv.writer(fout)
        # writer.writerow(["类型", "内容", "原文路径", "译文路径", "原文", "译文"]) #这里要以list形式写入，writer会在新建的csv文件中，一行一行写入
        # writer.writerow([detail["name"],detail["obj"],INDEXFILE[detail['index']['id']]['input_ori_file'],INDEXFILE[detail['index']['id']]['input_trans_file'], regex.sub("[\n\r\t,]+", "", INDEX[detail['index']['id']][detail['index']['idx']]['c_origin'])[:MAX_LENGTH_PERTAG], regex.sub("[\n\r\t,]+", "", INDEX[detail['index']['id']][detail['index']['idx']]['c_trans'])[:MAX_LENGTH_PERTAG]])
        fout.close()
        
        
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

    FILELIST = read_input_folder(args.input_folder)
    # print(FILELIST)
    # fl = os.listdir(args.input_folder)

    if args.jobs != -1:
        PROCESSES = args.jobs
    print('Creating PatTransErrorDetect pool with %d processes\n' % PROCESSES)
    e1 = time.time()
    pool = Pool(PROCESSES)

    globals.init(len(FILELIST))
    # 这种方式回调函数无法使用pbar变量
    # with tqdm(total=len(FILELIST)) as pbar:
    error_files = []
    for i in range(len(FILELIST)):
        input_file = FILELIST[i]
        basename, extension = os.path.splitext(os.path.basename(input_file))
        # if extension.lower() != '.xlsx' or extension.lower() != '.xls':
        #     print('\nFile not exists: ' + input_file)
        #     continue

        if not os.path.exists(input_file):
            print('\nFile not exists: ' + input_file)
            error_files.append('File not exists: ' + input_file)
            continue

        param = {'input_file': input_file, 'sections': SECTIONS, 'tag': DEFAULT['TAG'], 'endict': ENDICT}
        # print(param)
        pool.apply_async(_run_detecter, args=(param, ), callback=_run_detecter_callback).get()
    pool.close()
    pool.join()
        
    e2 = time.time()
    # print(float(e2 - e1))
    print('\nTotal',len(ANCHORS),'anchors...')

    with open(args.output_folder+'_errors.txt', 'w', encoding='utf-8', errors="ignore") as fout:
        fout.writelines(error_files)

    print('Saving visual files...')
    stat = _save_visual_files(ANCHORS, INDEX, INDEXFILE, args.output_folder+'_visual', SECTIONS)
    t = {}
    for item in SECTIONS:
        t[item['name']] = 0
    for item in stat:
        t[item['name']] = item['value']

    json.dump([(item['name'], item['stat'], t[item['name']]) for item in SECTIONS], open(os.path.join(args.output_folder+'_visual', 'sections.json'), 'w', encoding='utf-8',
                        errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)
    
    print('Saving csv files...')
    _save_csv_files(ANCHORS, INDEX, INDEXFILE, args.output_folder+'_csv', SECTIONS)

    print('Saving anchor files...')
    _save_anchor_files(ANCHORS, args.output_folder+'_anchors')
    # json.dump(, open(args.output_file+'.anchors.json', 'w', encoding='utf-8',
    #                         errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

    # json.dump(ANCHORS, open(args.output_file+'.ori.json', 'w', encoding='utf-8',
    #                         errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

    # STAT = sorted(STAT.items(), key=lambda x: x[1], reverse=True)
    # json.dump(dict(STAT), open(args.output_file+'.stat.json', 'w', encoding='utf-8',
    #                            errors="ignore"), sort_keys=False, indent=4, ensure_ascii=False)

