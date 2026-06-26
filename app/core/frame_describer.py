from pathlib import Path

_PROMPT = "a security camera showing"


class FrameDescriber:
    _model = None
    _processor = None

    @classmethod
    def is_available(cls) -> bool:
        """True if transformers + torch are importable for local CPU inference."""
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    @classmethod
    def describe(cls, image_path: Path) -> str:
        """Return a visual description of the thumbnail, or '' on any failure."""
        # Short-circuit if file doesn't exist — avoids triggering model load.
        if not Path(image_path).exists():
            return ""
        if not cls.is_available():
            return ""
        try:
            from PIL import Image
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration

            if cls._model is None:
                model_id = "Salesforce/blip-image-captioning-base"
                cls._processor = BlipProcessor.from_pretrained(model_id)
                cls._model = BlipForConditionalGeneration.from_pretrained(
                    model_id, torch_dtype=torch.float32
                )
                cls._model.eval()

            img = Image.open(str(image_path)).convert("RGB")
            inputs = cls._processor(img, _PROMPT, return_tensors="pt")
            with torch.no_grad():
                out = cls._model.generate(**inputs, max_new_tokens=60)
            return cls._processor.decode(out[0], skip_special_tokens=True).strip()
        except Exception:
            return ""
