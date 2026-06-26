"""Florence-2 multi-task frame analysis. Gracefully absent when transformers not installed."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FrameAnalyzer:
    """Singleton wrapper around Florence-2-base for per-event thumbnail analysis."""

    _instance = None
    _model = None
    _processor = None

    @classmethod
    def is_available(cls) -> bool:
        """Return True if Florence-2 transformers library is installed AND model weights cached."""
        try:
            from transformers import Florence2ForConditionalGeneration  # noqa: F401
        except Exception:
            return False
        weights_dir = (
            Path.home() / ".cache" / "huggingface" / "hub" / "models--microsoft--Florence-2-base"
        )
        return weights_dir.exists()

    @classmethod
    def analyze(cls, image_path: Path) -> dict:
        """
        Run three Florence-2 tasks on image_path thumbnail.

        Returns dict with keys:
          caption (str)             — <MORE_DETAILED_CAPTION> result; "" if unavailable
          object_caption (str)      — <REGION_CAPTION> on first detected object crop; "" if none
          detections (list[dict])   — <OD> output: [{label, bbox}]; [] if none
          clip_embedding_path (str|None) — absolute path to .clip.npy sidecar; None if CLIP absent
        """
        if not cls.is_available():
            return {
                "caption": "",
                "object_caption": "",
                "detections": [],
                "clip_embedding_path": None,
            }

        try:
            result = cls._run_analysis(image_path)
        except Exception as exc:
            logger.warning("Florence-2 analysis failed for %s: %s", image_path, exc)
            result = {
                "caption": "",
                "object_caption": "",
                "detections": [],
                "clip_embedding_path": None,
            }

        # Attach CLIP embedding (lazy import — clip_indexer may not be installed)
        clip_path = cls._get_clip_embedding(image_path)
        result["clip_embedding_path"] = clip_path
        return result

    @classmethod
    def _run_analysis(cls, image_path: Path) -> dict:
        """Load model (once) and run three tasks with per-task 30s timeout."""
        import concurrent.futures
        import torch
        from PIL import Image
        from transformers import AutoProcessor, Florence2ForConditionalGeneration

        if cls._model is None:
            cls._processor = AutoProcessor.from_pretrained(
                "microsoft/Florence-2-base", trust_remote_code=False
            )
            cls._model = Florence2ForConditionalGeneration.from_pretrained(
                "microsoft/Florence-2-base",
                torch_dtype=torch.float32,
                device_map="cpu",
            )

        image = Image.open(image_path).convert("RGB")
        processor = cls._processor
        model = cls._model

        def _run_task(task: str):
            inputs = processor(text=task, images=image, return_tensors="pt").to("cpu")
            ids = model.generate(**inputs, max_new_tokens=1024, num_beams=3)
            raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
            return processor.post_process_generation(raw, task=task, image_size=image.size)

        # Task 1: detailed caption
        caption = ""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_run_task, "<MORE_DETAILED_CAPTION>")
                parsed = future.result(timeout=30)
                caption = parsed.get("<MORE_DETAILED_CAPTION>", "") or ""
        except concurrent.futures.TimeoutError:
            logger.warning("Florence-2 caption timeout for %s", image_path)
        except Exception as exc:
            logger.warning("Florence-2 caption error for %s: %s", image_path, exc)

        # Task 2: object detection
        detections = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_run_task, "<OD>")
                od_result = future.result(timeout=30)
                od_data = od_result.get("<OD>", {}) or {}
                labels = od_data.get("labels", []) or []
                bboxes = od_data.get("bboxes", []) or []
                detections = [
                    {"label": lbl, "bbox": list(bb)}
                    for lbl, bb in zip(labels, bboxes)
                ]
        except concurrent.futures.TimeoutError:
            logger.warning("Florence-2 OD timeout for %s", image_path)
        except Exception as exc:
            logger.warning("Florence-2 OD error for %s: %s", image_path, exc)

        # Task 3: region caption on first detected object crop (if any)
        object_caption = ""
        if detections:
            try:
                bbox = detections[0]["bbox"]
                crop = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
                # Use region caption on the crop
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    inputs = cls._processor(
                        text="<MORE_DETAILED_CAPTION>", images=crop, return_tensors="pt"
                    ).to("cpu")
                    future = ex.submit(
                        lambda: cls._model.generate(**inputs, max_new_tokens=256, num_beams=3)
                    )
                    ids = future.result(timeout=30)
                    raw = cls._processor.batch_decode(ids, skip_special_tokens=False)[0]
                    parsed = cls._processor.post_process_generation(
                        raw, task="<MORE_DETAILED_CAPTION>", image_size=crop.size
                    )
                    object_caption = parsed.get("<MORE_DETAILED_CAPTION>", "") or ""
            except concurrent.futures.TimeoutError:
                logger.warning("Florence-2 region_caption timeout for %s", image_path)
            except Exception as exc:
                logger.warning("Florence-2 region_caption error for %s: %s", image_path, exc)

        return {
            "caption": caption,
            "object_caption": object_caption,
            "detections": detections,
            "clip_embedding_path": None,  # set by caller after this returns
        }

    @classmethod
    def _get_clip_embedding(cls, image_path: Path):
        """Call ClipIndexer.embed() if available; never raise."""
        try:
            from app.core.clip_indexer import ClipIndexer
            return ClipIndexer.embed(image_path)
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("CLIP embedding failed for %s: %s", image_path, exc)
            return None
