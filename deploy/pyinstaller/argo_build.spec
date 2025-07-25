# -*- mode: python ; coding: utf-8 -*-

import os
import sys

spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
project_dir = os.path.abspath(os.path.join(spec_dir, "../.."))
sys.path.insert(0, project_dir)

import platform
import urllib.request
import zipfile
import time
import glob
from PyInstaller.utils.hooks import collect_data_files, collect_all
from PyInstaller.compat import is_linux, is_darwin, is_win
from deploy.pyinstaller.utils import get_data_files

backend_dir = os.path.abspath(os.path.join(project_dir, 'backend'))

block_cipher = None

LINUX = is_linux
MACOS = is_darwin
WIN32 = is_win

EXEC_ARCH = None
EXEC_ICON = None
EXEC_NAME = None

NODE_NAME = None

binaries = []

if LINUX:
    EXEC_ARCH = platform.machine().lower()
    EXEC_ICON = os.path.join(project_dir, 'assets', 'icons', 'argo.png')

if MACOS:
    EXEC_ARCH = platform.machine().lower()
    EXEC_ICON = os.path.join(project_dir, 'assets', 'icons', 'argo.icns')
    NODE_NAME = f"node_darwin_{EXEC_ARCH}.zip"

if WIN32:
    EXEC_ARCH = os.environ[
        'PROCESSOR_ARCHITECTURE'].lower() if 'PROCESSOR_ARCHITECTURE' in os.environ else platform.machine().lower()
    EXEC_ICON = os.path.join(project_dir, 'assets', 'icons', 'argo.ico')
    NODE_NAME = 'node_windows.zip'

APPNAME = 'argo'
DIST_NAME = '%s' % (APPNAME)

venv_dir = [p for p in sys.path if 'site-packages' in p][0]

excludes = [
    'IPython',
]

hidden_imports = ["tiktoken_ext.openai_public", "pydantic.deprecated.decorator", "swagger_ui.handlers.tornado"]

a = Analysis(
    [os.path.join(backend_dir, 'main.py')],
    pathex=[venv_dir, '.'],
    binaries=binaries,
    datas=get_data_files(),
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'hooks', 'runtime_env_hook.py')],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APPNAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=EXEC_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=DIST_NAME,
)

#onefile
#exe = EXE(
#    pyz,
#    a.scripts,
#    a.binaries,
#    a.zipfiles,
#    a.datas,
#    exclude_binaries=False,
#    name=APPNAME,
#    debug=False,
#    bootloader_ignore_signals=False,
#    strip=False,
#    upx=True,
#    console=True,
#    disable_windowed_traceback=False,
#    argv_emulation=False,
#    target_arch=None,
#    codesign_identity=None,
#    entitlements_file=None,
#    icon=EXEC_ICON,
#)