"""Florence-2 multi-task frame analysis. Gracefully absent when transformers not installed."""
from __future__ import annotations

import contextlib
import io
import logging
import re
import threading
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Caption sanitiser ─────────────────────────────────────────────────────────
# Florence-2's post_process_generation leaks raw model tokens in transformers 5.x.
# This strips: </s> <s> <pad> <loc_NNN> <TASK_TOKEN> (e.g. <MORE_DETAILED_CAPTION>)
_SPECIAL_TOKEN_RE = re.compile(r'</s>|<s>|<pad>|<loc_\d+>|</?[A-Z_]+>')


def _clean_caption(text: str) -> str:
    """Strip Florence-2 special tokens from a caption string."""
    return _SPECIAL_TOKEN_RE.sub('', text or '').strip()


def _run_in_daemon(fn, timeout: float):
    """Run fn() in a daemon thread; return (result, None) or (None, exc) on timeout/error.

    Uses a daemon thread so join(timeout) truly returns without blocking — unlike
    ThreadPoolExecutor.__exit__ which calls shutdown(wait=True) and blocks until the
    worker finishes even after future.result() already raised TimeoutError.
    """
    result_box: list = [None]
    exc_box: list = [None]

    def target():
        try:
            result_box[0] = fn()
        except Exception as exc:  # noqa: BLE001
            exc_box[0] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None, TimeoutError(f"inference exceeded {timeout}s")
    if exc_box[0] is not None:
        return None, exc_box[0]
    return result_box[0], None


class FrameAnalyzer:
    """Singleton wrapper around Florence-2-base for per-event thumbnail analysis."""

    _instance = None
    _model = None
    _processor = None
    _availability_cache: bool | None = None  # set on first is_available() call; stable for process lifetime

    @classmethod
    def is_available(cls) -> bool:
        """Return True if Florence-2 transformers library is installed AND model weights cached."""
        if cls._availability_cache is not None:
            return cls._availability_cache
        # Fast path: device has <5 GB RAM — AI disabled regardless of weights
        from app.config import AI_FEATURES_ENABLED
        if not AI_FEATURES_ENABLED:
            cls._availability_cache = False
            return False
        try:
            from transformers import AutoModelForCausalLM  # noqa: F401
        except Exception:
            cls._availability_cache = False
            return False
        weights_dir = (
            Path.home() / ".cache" / "huggingface" / "hub" / "models--microsoft--Florence-2-base"
        )
        cls._availability_cache = weights_dir.exists()
        return cls._availability_cache

    @classmethod
    def analyze(cls, image_path: Path) -> dict:
        """Run three Florence-2 tasks on image_path thumbnail.

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

        clip_path = cls._get_clip_embedding(image_path)
        result["clip_embedding_path"] = clip_path
        return result

    @classmethod
    def _run_analysis(cls, image_path: Path) -> dict:
        """Load model (once) and run three tasks. CPU inference: ~1-3 min per task."""
        import torch
        from PIL import Image
        from transformers import AutoModelForCausalLM, AutoProcessor, PretrainedConfig
        from transformers.tokenization_utils_base import PreTrainedTokenizerBase

        if cls._model is None:
            # transformers 5.x removed several class-level defaults that Florence-2's custom
            # processing_florence2.py (trust_remote_code) still depends on.
            #
            # 1. PretrainedConfig.forced_bos_token_id was a class-level None default.
            if not hasattr(PretrainedConfig, "forced_bos_token_id"):
                PretrainedConfig.forced_bos_token_id = None

            # 2. PreTrainedTokenizerBase.additional_special_tokens was a property returning
            #    the list of extra special tokens.
            if "additional_special_tokens" not in PreTrainedTokenizerBase.__dict__:
                PreTrainedTokenizerBase.additional_special_tokens = property(
                    lambda self: list(self.special_tokens_map.get("additional_special_tokens", []))
                )

            # trust_remote_code=True required: the HF Hub model config is incomplete
            # (image_token not registered in tokenizer_config.json). Authorized 2026-06-29.
            # Redirect stdout + suppress FutureWarnings so Florence-2's MISSING-keys
            # weight table and transformers attention-mask warnings don't clutter the terminal.
            with contextlib.redirect_stdout(io.StringIO()), \
                 warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
                cls._processor = AutoProcessor.from_pretrained(
                    "microsoft/Florence-2-base", trust_remote_code=True
                )
                # 3. attn_implementation="eager" bypasses SDPA detection (_supports_sdpa missing
                #    from custom class). torch_dtype → dtype in transformers 5.x.
                cls._model = AutoModelForCausalLM.from_pretrained(
                    "microsoft/Florence-2-base",
                    dtype=torch.float32,
                    device_map="cpu",
                    trust_remote_code=True,
                    attn_implementation="eager",
                )

        # CLIPImageProcessor's do_resize is broken in transformers 5.x — it passes raw
        # dimensions unchanged.  Resize to 768×768 (model's preprocessor_config size)
        # before the processor so the ViT produces a perfect-square token grid (24×24=576).
        # Resize (not pad) avoids black-border garbage in the caption.
        image = Image.open(image_path).convert("RGB").resize((768, 768), Image.BILINEAR)
        processor = cls._processor
        model = cls._model

        def _run_task(task: str):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                warnings.simplefilter("ignore", DeprecationWarning)
                inputs = processor(
                    text=task, images=image, return_tensors="pt", truncation=False
                ).to("cpu")
                # use_cache=False: avoids EncoderDecoderCache format incompatibility in
                # transformers 5.x — the custom Florence-2 model (trust_remote_code) was
                # written for 4.x tuple-style past_key_values.
                # max_new_tokens=100: prevents mid-token truncation (was 64); chosen over
                # 150 to stay within the 90s task timeout at ~1 tok/s worst-case.
                ids = model.generate(**inputs, max_new_tokens=100, num_beams=1, use_cache=False)
                raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
                return processor.post_process_generation(raw, task=task, image_size=image.size)

        # Timeout per task. _run_in_daemon uses a daemon thread so join(timeout) truly
        # returns without blocking (unlike ThreadPoolExecutor.__exit__ which calls
        # shutdown(wait=True) and blocks until the worker finishes even after timeout).
        _TASK_TIMEOUT = 90  # 90 s: real CCTV frames fire EOS ~20-45 s; 90 s gives 2× safety margin

        # Task 1: detailed caption
        caption = ""
        parsed, err = _run_in_daemon(lambda: _run_task("<MORE_DETAILED_CAPTION>"), _TASK_TIMEOUT)
        if err is not None:
            logger.warning("Florence-2 caption error for %s: %s", image_path, err)
        elif parsed is not None:
            caption = _clean_caption(parsed.get("<MORE_DETAILED_CAPTION>", "") or "")

        # Task 2: object detection
        detections: list = []
        od_parsed, err = _run_in_daemon(lambda: _run_task("<OD>"), _TASK_TIMEOUT)
        if err is not None:
            logger.warning("Florence-2 OD error for %s: %s", image_path, err)
        elif od_parsed is not None:
            od_data = od_parsed.get("<OD>", {}) or {}
            labels = od_data.get("labels", []) or []
            bboxes = od_data.get("bboxes", []) or []
            detections = [
                {"label": _clean_caption(lbl), "bbox": list(bb)}
                for lbl, bb in zip(labels, bboxes)
            ]

        # Task 3: region caption on first detected object crop (only if OD found something)
        object_caption = ""
        if detections:
            try:
                bbox = detections[0]["bbox"]
                crop = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
                crop_inputs = processor(
                    text="<MORE_DETAILED_CAPTION>",
                    images=crop,
                    return_tensors="pt",
                    truncation=False,
                ).to("cpu")

                def _region_task():
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        warnings.simplefilter("ignore", DeprecationWarning)
                        ids = model.generate(
                            **crop_inputs, max_new_tokens=100, num_beams=1, use_cache=False
                        )
                        raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
                        return processor.post_process_generation(
                            raw, task="<MORE_DETAILED_CAPTION>", image_size=crop.size
                        )

                rc_parsed, err = _run_in_daemon(_region_task, _TASK_TIMEOUT)
                if err is not None:
                    logger.warning("Florence-2 region_caption error for %s: %s", image_path, err)
                elif rc_parsed is not None:
                    object_caption = _clean_caption(rc_parsed.get("<MORE_DETAILED_CAPTION>", "") or "")
            except Exception as exc:
                logger.warning("Florence-2 region_caption setup error for %s: %s", image_path, exc)

        return {
            "caption": caption,
            "object_caption": object_caption,
            "detections": detections,
            "clip_embedding_path": None,
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
