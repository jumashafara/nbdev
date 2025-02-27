"""A parallel ipynb processor (experimental)"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/17_serve.ipynb.

# %% auto 0
__all__ = ['proc_nbs']

# %% ../nbs/api/17_serve.ipynb
import ast,subprocess,threading,sys
from shutil import rmtree,copy2

from fastcore.utils import *
from fastcore.parallel import parallel
from fastcore.script import call_parse
from fastcore.meta import delegates

from .config import get_config
from .doclinks import nbglob_cli,nbglob
from .processors import FilterDefaults
import nbdev.serve_drv

# %% ../nbs/api/17_serve.ipynb
def _is_qpy(path:Path):
    "Is `path` a py script starting with frontmatter?"
    path = Path(path)
    if not path.suffix=='.py': return
    p = ast.parse(path.read_text(encoding='utf-8'))
#     try: p = ast.parse(path.read_text(encoding='utf-8'))
#     except: return
    if not p.body: return
    a = p.body[0]
    if isinstance(a, ast.Expr) and isinstance(a.value, ast.Constant):
        v = a.value.value.strip()
        vl = v.splitlines()
        if vl[0]=='---' and vl[-1]=='---': return '\n'.join(vl[1:-1])

# %% ../nbs/api/17_serve.ipynb
def _proc_file(s, cache, path, mtime=None):
    skips = ('_proc', '_docs', '_site', 'settings.ini')
    if not s.is_file() or any(o[0]=='.' or o in skips for o in s.parts): return
    d = cache/s.relative_to(path)
    if s.suffix=='.py': d = d.with_suffix('')
    if d.exists():
        dtime = d.stat().st_mtime
        if mtime: dtime = max(dtime, mtime)
        if s.stat().st_mtime<=dtime: return

    d.parent.mkdir(parents=True, exist_ok=True)
    if s.suffix=='.ipynb': return s,d,FilterDefaults
    md = _is_qpy(s)
    if md is not None: return s,d,md.strip()
    else: copy2(s,d)

# %% ../nbs/api/17_serve.ipynb
@delegates(nbglob_cli)
def proc_nbs(
    path:str='', # Path to notebooks
    n_workers:int=defaults.cpus,  # Number of workers
    force:bool=False,  # Ignore cache and build all
    file_glob:str='', # Only include files matching glob
    file_re:str='', # Only include files matching glob
    **kwargs):
    "Process notebooks in `path` for docs rendering"
    cfg = get_config()
    cache = cfg.config_path/'_proc'
    path = Path(path or cfg.nbs_path)
    files = nbglob(path, func=Path, file_glob='', file_re='', **kwargs)
    if (path/'_quarto.yml').exists(): files.append(path/'_quarto.yml')
    if (path/'_brand.yml').exists(): files.append(path/'_brand.yml')
    if (path/'_extensions').exists(): files.extend(nbglob(path/'_extensions', func=Path, file_glob='', file_re='', skip_file_re='^[.]'))

    # If settings.ini or filter script newer than cache folder modified, delete cache
    chk_mtime = max(cfg.config_file.stat().st_mtime, Path(__file__).stat().st_mtime)
    cache.mkdir(parents=True, exist_ok=True)
    cache_mtime = cache.stat().st_mtime
    if force or (cache.exists() and cache_mtime<chk_mtime): rmtree(cache)

    files = files.map(_proc_file, mtime=cache_mtime, cache=cache, path=path).filter()
    kw = {} if IN_NOTEBOOK else {'method':'spawn'}
    parallel(nbdev.serve_drv.main, files, n_workers=n_workers, pause=0.01, **kw)
    if cache.exists(): cache.touch()
    return cache
