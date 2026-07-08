# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for macOS (arm64 on macos-14, intel on macos-13).

Run from project root:
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install pyinstaller -r requirements.txt transformers open-clip-torch ultralytics
    pyinstaller build/cctv_processor_macos.spec
    bash build/macos/create_dmg.sh
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

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
        "fastapi.routing",
        "starlette.routing",
        "starlette.staticfiles",
        "aiofiles.os",
        "aiofiles.threadpool",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "imageio_ffmpeg",
        # Florence-2 remote code imports these at model-load time; invisible
        # to static analysis (trust_remote_code), so force them in.
        "einops",
        "einops.layers",
        "einops.layers.torch",
        "timm",
        "timm.layers",
        "timm.models",
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
        # onnx/onnxruntime are YOLO export-only deps — never imported at
        # inference time. Excluding them shrinks the bundle and matches the
        # Windows spec (where onnx.reference also crashes PyInstaller).
        "onnx",
        "onnx.reference",
        "onnxruntime",
        "onnxslim",
        "onnxslim.third_party._sympy",
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
    console=False,
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

app = BUNDLE(
    coll,
    name="CCTV Video Processor.app",
    icon=None,
    bundle_identifier="com.cctv.videoprocessor",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": os.environ.get("APP_VERSION", "dev"),
        "CFBundleVersion": os.environ.get("APP_VERSION", "dev"),
        "LSUIElement": False,
        "NSRequiresAquaSystemAppearance": False,
    },
)
