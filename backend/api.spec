# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django.setup()

import sys
sys.setrecursionlimit(5000)
from PyInstaller.utils.hooks import collect_submodules, collect_all

hidden_imports = []
tmp_ret = []
all_datas = []
all_binaries = []

def force_load(package_name):
    global hidden_imports, all_datas, all_binaries
    d, b, h = collect_all(package_name)
    all_datas += d
    all_binaries += b
    hidden_imports += h

force_load('rapidocr_onnxruntime')

hidden_imports += collect_submodules('api')                      
hidden_imports += collect_submodules('rest_framework')           
hidden_imports += collect_submodules('django_q')                 
hidden_imports += collect_submodules('corsheaders')              
hidden_imports += collect_submodules('social_django')            
hidden_imports += collect_submodules('social_core')              
hidden_imports += collect_submodules('storages')                 
hidden_imports += collect_submodules('rest_framework_simplejwt') 

hidden_imports += [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas + [   
        ('ocr_models', 'ocr_models'), 
    ],
    hiddenimports=hidden_imports, 
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='api',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='api',
)
