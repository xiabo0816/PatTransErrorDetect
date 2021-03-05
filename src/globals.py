import traceback
import sys
from tqdm import tqdm
global g_pbar

def init(total):
    global g_pbar
    g_pbar = tqdm(total=total)

def update(n):
    global g_pbar
    g_pbar.update(n)

def print_tb():
    error_type, error_value, error_trace = sys.exc_info()
    print(error_type)
    print(error_value)
    print(traceback.print_tb(error_trace))