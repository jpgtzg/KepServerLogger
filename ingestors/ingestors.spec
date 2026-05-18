# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Paths relative to the spec file location (ingestors/)
ROOT = os.path.abspath('..')
INGESTORS_ROOT = os.path.abspath('.')
SRC = os.path.join(INGESTORS_ROOT, 'src')

a = Analysis(
    [os.path.join(SRC, 'main.py')],
    pathex=[
        SRC,           # for 'db' module
        INGESTORS_ROOT, # for 'subscribers' package
        ROOT,           # for 'lib' package
    ],
    binaries=[],
    datas=[],
    hiddenimports=[
        'asyncua',
        'asyncua.ua',
        'asyncua.client',
        'asyncua.client.client',
        'asyncua.crypto',
        'psycopg',
        'psycopg.pq',
        'psycopg_binary',
        'psycopg.types',
        'psycopg.types.array',
        'psycopg.types.datetime',
        'psycopg.types.numeric',
        'psycopg.types.string',
        'pandas',
        'pydantic',
        'pydantic_settings',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ingestors',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
