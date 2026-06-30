"""CLIP ViT-B/32 semantic embedding writer. Gracefully absent when open-clip-torch not installed."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ClipIndexer:
    """Singleton wrapper around CLIP ViT-B/32 for thumbnail embedding."""

    _model = None
    _preprocess = None

    @classmethod
    def is_available(cls) -> bool:
        """Return True if open-clip-torch is installed."""
        try:
            import open_clip  # noqa: F401
            return True
        except Exception:
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
    def _do_embed(cls, image_path: Path) -> Optional[str]:
        import open_clip
        import torch
        from PIL import Image
        import numpy as np

        if cls._model is None:
            cls._model, _, cls._preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32-quickgelu", pretrained="openai"
            )
            cls._model.eval()

        image = cls._preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
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
