from pathlib import Path

class FrameDescriber:
    _model = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            import moondream  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def describe(cls, image_path: Path) -> str:
        if not cls.is_available():
            return ""
        try:
            from PIL import Image
            if cls._model is None:
                import moondream as md
                cls._model = md.vl()
            img = Image.open(str(image_path))
            result = cls._model.query(img, "Briefly describe what is happening in this security camera frame. Focus on people, vehicles, and any notable actions.")
            return result.answer if hasattr(result, "answer") else str(result)
        except Exception:
            return ""
