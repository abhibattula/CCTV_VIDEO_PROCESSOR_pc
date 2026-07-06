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
        # Florence-2 remote code imports these at model-load time; they are
        # invisible to PyInstaller's static analysis (loaded via
        # trust_remote_code), so they must be forced in here.
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
        # onnx/onnxruntime are YOLO export-only deps — not needed at inference time.
        # Importing onnx.reference in PyInstaller's isolated subprocess causes a
        # STATUS_ACCESS_VIOLATION (exit code 3221225477) on Windows, crashing the
        # entire Analysis phase. Safe to exclude: the app never calls onnx APIs.
        "onnx",
        "onnx.reference",
        "onnxruntime",
        "onnxslim",
        "onnxslim.third_party._sympy",
    ],
    noarchive=False,
    optimize=0,
)

# PyQt6 ships 2020-era VC++ runtime DLLs (14.26) inside Qt6/bin. In the
# windowed app Qt loads first, so Windows resolves msvcp140.dll to that old
# copy; torch's c10.dll needs the newer runtime and fails DLL init with
# WinError 1114, silently disabling AI. Strip Qt's copies so every module
# uses the single up-to-date runtime PyInstaller places in _internal/.
_vc_runtime_dlls = {
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll",
}
a.binaries = [
    entry for entry in a.binaries
    if not (
        entry[0].replace("/", "\\").lower().startswith("pyqt6\\qt6\\bin\\")
        and entry[0].replace("/", "\\").lower().rsplit("\\", 1)[-1] in _vc_runtime_dlls
    )
]

# Qt6Core/Qt6Gui statically link msvcp140_1.dll and msvcp140_2.dll, which
# only existed as Qt's stripped 14.26 copies. Ship the host's current
# (>=14.40) runtime at the bundle root so clean machines without the VC++
# redistributable still resolve them (the bootloader adds _internal to the
# process-wide DLL search path).
_sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
for _dll in ("msvcp140_1.dll", "msvcp140_2.dll"):
    _src = os.path.join(_sys32, _dll)
    if os.path.exists(_src):
        a.binaries.append((_dll, _src, "BINARY"))

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
