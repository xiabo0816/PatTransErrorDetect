from tqdm import tqdm
global g_pbar

def init(total):
    global g_pbar
    g_pbar = tqdm(total=total)

def update(n):
    global g_pbar
    g_pbar.update(n)