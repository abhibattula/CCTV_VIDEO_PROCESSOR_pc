"""CLIP ViT-B/32 semantic embedding writer. Gracefully absent when open-clip-torch not installed."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ClipIndexer:
    """Singleton wrapper around CLIP ViT-B/32 for thumbnail + text embedding."""

    _model = None
    _preprocess = None
    _tokenizer = None
    unavailable_reason: str | None = None  # why is_available() last returned False

    @classmethod
    def is_available(cls) -> bool:
        """Return True if open-clip-torch is installed AND CLIP weights are on disk.

        open_clip 3.x downloads the OpenAI checkpoint from the HF hub (the old
        openaipublic.azureedge.net URL is dead), so weights may live in either:
        - the legacy clip cache: <clip cache root>/ViT-B-32.pt, or
        - the HF hub cache: <hf cache>/hub/models--timm--vit_base_patch32_clip_224.openai
        """
        try:
            import open_clip  # noqa: F401
        except Exception:
            cls.unavailable_reason = (
                "open-clip-torch is not installed (optional AI dependency)."
            )
            return False
        import os
        clip_cache_dir = os.environ.get("CLIP_CACHE_DIR", "").strip()
        xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
        if clip_cache_dir:
            cache_root = Path(clip_cache_dir)
        elif xdg:
            cache_root = Path(xdg) / "clip"
        else:
            cache_root = Path.home() / ".cache" / "clip"
        if (cache_root / "ViT-B-32.pt").exists():
            cls.unavailable_reason = None
            return True

        hf_home = (
            os.environ.get("HF_HOME")
            or os.environ.get("HUGGINGFACE_HUB_CACHE")
            or str(Path.home() / ".cache" / "huggingface")
        )
        hub_dir = Path(hf_home) / "hub" / "models--timm--vit_base_patch32_clip_224.openai"
        if hub_dir.exists():
            cls.unavailable_reason = None
            return True
        cls.unavailable_reason = "CLIP model weights are not downloaded yet."
        return False

    @classmethod
    def embed(cls, image_path: Path) -> Optional[str]:
        """
        Embed image_path using CLIP ViT-B/32 and write .clip.npy sidecar.

        Returns absolute path string to the .npy file, or None if:
          - open-clip-torch not installed
          - image load fails
          - .npy write fails (OSError)

        Never raises to caller.
        """
        if not cls.is_available():
            return None

        try:
            return cls._do_embed(image_path)
        except Exception as exc:
            logger.warning("CLIP embed failed for %s: %s", image_path, exc)
            return None

    @classmethod
    def embed_text(cls, query: str):
        """Embed a text query into the same space as embed()'s image vectors.

        Returns a float32 (512,) L2-normalized numpy array, or None if CLIP is
        unavailable or anything fails. Never raises to the caller — mirrors
        embed(). The tokenizer truncates long queries internally (77-token
        context), so arbitrary-length text is safe.
        """
        if not cls.is_available():
            return None
        try:
            return cls._do_embed_text(query)
        except Exception as exc:
            logger.warning("CLIP text embed failed for %r: %s", query, exc)
            return None

    @classmethod
    def _do_embed_text(cls, query: str):
        import torch

        cls._ensure_model()
        if cls._tokenizer is None:
            import open_clip
            cls._tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
        tokens = cls._tokenizer([query])
        if cls._device() != "cpu":
            tokens = tokens.to(cls._device())
        with torch.no_grad():
            features = cls._model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze(0).cpu().numpy().astype("float32")  # shape (512,)

    @classmethod
    def _device(cls) -> str:
        """AI compute device — "cuda" on CUDA machines, else "cpu" (no-op)."""
        from app.utils import ai_device
        return ai_device.get_ai_device()

    @classmethod
    def _ensure_model(cls) -> None:
        """Lazy-load the shared CLIP model (used by both image and text paths)."""
        if cls._model is None:
            import open_clip
            cls._model, _, cls._preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32-quickgelu", pretrained="openai"
            )
            cls._model.eval()
            if cls._device() != "cpu":
                cls._model.to(cls._device())

    @classmethod
    def _do_embed(cls, image_path: Path) -> Optional[str]:
        import torch
        from PIL import Image
        import numpy as np

        cls._ensure_model()

        image = cls._preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
        if cls._device() != "cpu":
            image = image.to(cls._device())
        with torch.no_grad():
            features = cls._model.encode_image(image)
        features = features / features.norm(dim=-1, keepdim=True)
        embedding = features.squeeze(0).cpu().numpy().astype("float32")  # shape (512,)

        sidecar_path = image_path.parent / (image_path.stem + ".clip.npy")
        try:
            np.save(str(sidecar_path), embedding)
        except OSError as exc:
            logger.warning("CLIP sidecar write failed for %s: %s", sidecar_path, exc)
            return None

        return str(sidecar_path.resolve())
