import os
import tempfile
from pathlib import Path
from typing import Generator

from pdf2image import convert_from_path
from PIL import Image


class PDFProcessor:
    """
    Renders each page of a PDF as a PIL Image.
    ColPali works directly on page images — no OCR, no text extraction.
    This is the key insight: we treat every page as a visual object.
    """

    def __init__(self, dpi: int = 150):
        # 150 DPI is the sweet spot: good enough for ColPali to read
        # tables and charts without blowing up memory on large docs
        self.dpi = dpi

    def pdf_to_images(self, pdf_bytes: bytes) -> list[Image.Image]:
        """
        Convert a PDF (as raw bytes) into a list of PIL Images, one per page.
        Uses a temp file because pdf2image needs a file path.
        """
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            images = convert_from_path(
                tmp_path,
                dpi=self.dpi,
                fmt="RGB",
                thread_count=2,
            )
            return images
        finally:
            os.unlink(tmp_path)

    def pdf_to_images_generator(
        self, pdf_bytes: bytes
    ) -> Generator[tuple[int, Image.Image], None, None]:
        """
        Generator variant — yields (page_number, image) pairs one at a time.
        Useful for large documents where you don't want all pages in memory.
        """
        images = self.pdf_to_images(pdf_bytes)
        for page_num, image in enumerate(images, start=1):
            yield page_num, image

    def resize_for_model(
        self, image: Image.Image, max_size: int = 1024
    ) -> Image.Image:
        """
        ColPali has a max input resolution. Resize while keeping aspect ratio.
        """
        w, h = image.size
        if max(w, h) <= max_size:
            return image
        scale = max_size / max(w, h)
        return image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    def image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        import io
        buf = io.BytesIO()
        image.save(buf, format=format)
        return buf.getvalue()


pdf_processor = PDFProcessor()