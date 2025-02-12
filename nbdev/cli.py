"""CLI commands"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/13_cli.ipynb.

# %% ../nbs/api/13_cli.ipynb 2
from __future__ import annotations
import warnings
import time

from .config import *
from .process import *
from .processors import *
from .doclinks import *
from .test import *
from .clean import *
from .quarto import nbdev_readme, refresh_quarto_yml, fs_watchdog
from .export import nb_export
from .frontmatter import FrontmatterProc

from fastcore.xtras import run
from execnb.nbio import *
from fastcore.meta import *
from fastcore.utils import *
from fastcore.script import *
from fastcore.style import S
from fastcore.shutil import rmtree,move

from urllib.error import HTTPError
from contextlib import redirect_stdout
import os, tarfile, sys

# %% auto 0
__all__ = ['mapping', 'nbdev_filter', 'extract_tgz', 'nbdev_new', 'nbdev_update_license', 'nb_export_cli', 'watch_export',
           'chelp']

# %% ../nbs/api/13_cli.ipynb
@call_parse
def nbdev_filter(
    nb_txt:str=None,  # Notebook text (uses stdin if not provided)
    fname:str=None,  # Notebook to read (uses `nb_txt` if not provided)
    printit:bool_arg=True, # Print to stdout?
):
    "A notebook filter for Quarto"
    os.environ["IN_TEST"] = "1"
    try: filt = globals()[get_config().get('exporter', 'FilterDefaults')]()
    except FileNotFoundError: filt = FilterDefaults()
    if fname:        nb_txt = Path(fname).read_text()
    elif not nb_txt: nb_txt = sys.stdin.read()
    nb = dict2nb(loads(nb_txt))
    if printit:
        with open(os.devnull, 'w', encoding="utf-8") as dn:
            with redirect_stdout(dn): filt(nb)
    else: filt(nb)
    res = nb2str(nb)
    del os.environ["IN_TEST"]
    if printit: print(res, flush=True)
    else: return res

# %% ../nbs/api/13_cli.ipynb
def extract_tgz(url, dest='.'):
    from fastcore.net import urlopen
    with urlopen(url) as u: tarfile.open(mode='r:gz', fileobj=u).extractall(dest)

# %% ../nbs/api/13_cli.ipynb
def _render_nb(fn, cfg):
    "Render templated values like `{{lib_name}}` in notebook at `fn` from `cfg`"
    txt = fn.read_text()
    txt = txt.replace('from your_lib.core', f'from {cfg.lib_path}.core') # for compatibility with old templates
    for k,v in cfg.d.items(): txt = txt.replace('{{'+k+'}}', v)
    fn.write_text(txt)

# %% ../nbs/api/13_cli.ipynb
def _update_repo_meta(cfg):
    "Enable gh pages and update the homepage and description in your GitHub repo."
    token=os.getenv('GITHUB_TOKEN')
    if token:
        from ghapi.core import GhApi
        api = GhApi(owner=cfg.user, repo=cfg.repo, token=token)
        try: api.repos.update(homepage=f'{cfg.doc_host}{cfg.doc_baseurl}', description=cfg.description)
        except HTTPError:print(f"Could not update the description & URL on the repo: {cfg.user}/{cfg.repo} using $GITHUB_TOKEN.\n"
                  "Use a token with the correction permissions or perform these steps manually.")

# %% ../nbs/api/13_cli.ipynb
@call_parse
@delegates(nbdev_create_config)
def nbdev_new(**kwargs):
    "Create an nbdev project."
    from ghapi.core import GhApi
    nbdev_create_config.__wrapped__(**kwargs)
    cfg = get_config()
    _update_repo_meta(cfg)
    path = Path()

    _ORG_OR_USR,_REPOSITORY = 'answerdotai','nbdev-template'
    _TEMPLATE = f'{_ORG_OR_USR}/{_REPOSITORY}'
    template = kwargs.get('template', _TEMPLATE)
    try: org_or_usr, repo = template.split('/')
    except ValueError: org_or_usr, repo = _ORG_OR_USR, _REPOSITORY

    tag = kwargs.get('tag', None)
    if tag is None:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            tag = GhApi(gh_host='https://api.github.com', authenticate=False).repos.get_latest_release(org_or_usr, repo).tag_name

    url = f"https://github.com/{org_or_usr}/{repo}/archive/{tag}.tar.gz"
    extract_tgz(url)
    tmpl_path = path/f'{repo}-{tag}'

    cfg.nbs_path.mkdir(exist_ok=True)
    nbexists = bool(first(cfg.nbs_path.glob('*.ipynb')))
    _nbs_path_sufs = ('.ipynb','.css')
    for o in tmpl_path.ls():
        p = cfg.nbs_path if o.suffix in _nbs_path_sufs else path
        if o.name == '_quarto.yml': continue
        if o.name == 'index.ipynb': _render_nb(o, cfg)
        if o.name == '00_core.ipynb' and not nbexists: move(o, p)
        elif not (path/o.name).exists(): move(o, p)
    rmtree(tmpl_path)

    refresh_quarto_yml()
    nbdev_export.__wrapped__()
    nbdev_readme.__wrapped__()

# %% ../nbs/api/13_cli.ipynb
mapping = {
  'mit': 'mit',
  'apache2': 'apache-2.0',
  'gpl2': 'gpl-2.0',
  'gpl3': 'gpl-3.0',
  'bsd3': 'bsd-3-clause'
}

# %% ../nbs/api/13_cli.ipynb
@call_parse
def nbdev_update_license(
    to: str=None, # update license to
):
    "Allows you to update the license of your project."
    from ghapi.core import GhApi
    warnings.filterwarnings("ignore")
    avail_lic = GhApi().licenses.get_all_commonly_used().map(lambda x: x['key'])

    cfg = get_config()
    curr_lic = cfg['license']

    mapped = mapping.get(to, None)

    if mapped not in avail_lic: raise ValueError(f"{to} is not an available license")
    body = GhApi().licenses.get(mapped)['body']

    body = body.replace('[year], [fullname]', cfg['copyright'])
    body = body.replace('[year] [fullname]', cfg['copyright'])

    content = open("settings.ini", "r").read()
    content = re.sub(r"^(license\s*=\s*).*?$", r"\1 " + to, content, flags=re.MULTILINE)

    config = open("settings.ini", "w")
    config.write(content)

    lic = open('LICENSE', 'w')
    lic.write(body)
    print(f"License updated from {curr_lic} to {to}")

# %% ../nbs/api/13_cli.ipynb
@call_parse
@delegates(nb_export, but=['procs', 'mod_maker'])
def nb_export_cli(nbname, 
                  debug:store_true=False, # Debug flag 
                  **kwargs): 
    "Export a single nbdev notebook to a python script."
    return nb_export(nbname=nbname, debug=debug, **kwargs)

# %% ../nbs/api/13_cli.ipynb
@call_parse
def watch_export(nbs:str=None, # Nb directory to watch for changes
                 lib:str=None, # Export directory to write py files to
                 force:bool=False # Ignore nbdev config if in nbdev project
                ):
    '''Use `nb_export` on ipynb files in `nbs` directory on changes using nbdev config if available'''
    cfg = get_config() if is_nbdev() else None
    nbs = nbs or (cfg.nbs_path if cfg else '.')
    lib = lib or (cfg.lib_path if cfg else '.')
    if cfg and (nbs != cfg.nbs_path or lib != cfg.lib_path) and not force:
        raise ValueError("In nbdev project. Use --force to override config.")
    def _export(e,lib=lib):
        p = e.src_path
        if (not '.ipynb_checkpoints' in p and p.endswith('.ipynb') and not Path(p).name.startswith('.~')):
            if e.event_type == 'modified': run(f'nb_export --lib_path {lib} "{p}"')
    with fs_watchdog(_export, nbs):
        while True: time.sleep(1)

# %% ../nbs/api/13_cli.ipynb
@call_parse
def chelp():
    "Show help for all console scripts"
    from fastcore.xtras import console_help
    console_help('nbdev')
