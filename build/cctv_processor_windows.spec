# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Windows x86_64 build.

Run from project root:
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install pyinstaller -r requirements.txt transformers open-clip-torch ultralytics
    pyinstaller build/cctv_processor_windows.spec
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

# Project root is one level above this spec file
project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

# Collect large AI packages so all submodules and data are included
torch_datas, torch_bins, torch_hiddens = collect_all("torch")
transformers_datas, transformers_bins, transformers_hiddens = collect_all("transformers")
open_clip_datas, open_clip_bins, open_clip_hiddens = collect_all("open_clip")
ultralytics_datas, ultralytics_bins, ultralytics_hiddens = collect_all("ultralytics")
imageio_ffmpeg_datas = collect_data_files("imageio_ffmpeg")

a = Analysis(
    [os.path.join(project_root, "launcher.py")],
    pathex=[project_root],
    binaries=torch_bins + transformers_bins + open_clip_bins + ultralytics_bins,
    datas=[
        (os.path.join(project_root, "static"), "static"),
        (os.path.join(project_root, "app", "templates"), "app/templates"),
    ] + torch_datas + transformers_datas + open_clip_datas + ultralytics_datas + imageio_ffmpeg_datas,
    hiddenimports=[
        # uvicorn internals loaded at runtime
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # FastAPI / Starlette
        "fastapi.routing",
        "starlette.routing",
        "starlette.staticfiles",
        # aiofiles
        "aiofiles.os",
        "aiofiles.threadpool",
        # Qt
        "PyQt6.QtPrintSupport",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        # imageio-ffmpeg
        "imageio_ffmpeg",
        # AI hidden imports
    ] + torch_hiddens + transformers_hiddens + open_clip_hiddens + ultralytics_hiddens,
    excludes=[
        "torch.cuda",
        "torch.distributed",
        "torch.testing",
        "caffe2",
        "matplotlib",
        "scipy",
        "tkinter",
        "IPython",
        "notebook",
        "jupyter",
        "PIL.ImageTk",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CCTV-Video-Processor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no console window on Windows
    disable_windowed_traceback=False,
    icon=os.path.join(project_root, "static", "favicon.ico") if os.path.exists(
        os.path.join(project_root, "static", "favicon.ico")
    ) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CCTV-Video-Processor",
)
