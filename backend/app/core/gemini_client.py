import io
import base64
import time
import os
from PIL import Image

from app.config import get_settings

settings = get_settings()


class GeminiClient:

    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = "llama-3.3-70b-versatile"

        # Tell pytesseract where Tesseract is installed on Windows
        try:
            import pytesseract
            if os.name == 'nt':  # Windows
                pytesseract.pytesseract.tesseract_cmd = (
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                )
            self._ocr_available = True
            print("OCR available via pytesseract")
        except ImportError:
            self._ocr_available = False
            print("pytesseract not installed — OCR disabled")

        print(f"Groq client initialized: {self.model}")

    def answer_with_pages(
        self,
        question: str,
        page_images: list[Image.Image],
        page_numbers: list[int],
        page_texts: list[str] = None,
    ) -> str:
        context_parts = []

        for i, (img, page_num) in enumerate(zip(page_images, page_numbers)):
            page_text = ""

            # Priority 1: pre-extracted text from pdfplumber
            if page_texts and i < len(page_texts) and page_texts[i].strip():
                page_text = page_texts[i].strip()

            # Priority 2: OCR the image with pytesseract
            if not page_text and self._ocr_available:
                page_text = self._extract_text_from_image(img)

            if page_text.strip():
                context_parts.append(f"[Page {page_num}]\n{page_text}")
            else:
                context_parts.append(
                    f"[Page {page_num}]\n"
                    "(This page appears to be a pure visual element like a chart "
                    "or diagram with no readable text. Describe what you can infer "
                    "from the question context.)"
                )

        context = "\n\n".join(context_parts)

        prompt = f"""You are a document analysis assistant.
You have been given the most relevant pages from a document based on the user's question.
Analyze the content carefully and answer accurately.
Always cite which page number contains the relevant information.

DOCUMENT CONTENT:
{context}

QUESTION: {question}

ANSWER:"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                    temperature=0.1,
                )
                return response.choices[0].message.content.strip()

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < 2:
                        wait = (attempt + 1) * 20
                        print(f"Groq rate limit, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    return "Rate limited. Please wait a moment and try again."
                raise

    def _extract_text_from_image(self, image: Image.Image) -> str:
        """OCR the image using pytesseract."""
        try:
            import pytesseract
            # Enhance image for better OCR
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()
        except Exception as e:
            print(f"OCR failed: {e}")
            return ""

    def _image_to_part(self, image: Image.Image) -> dict:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return {
            "mime_type": "image/png",
            "data": base64.b64encode(buf.getvalue()).decode("utf-8"),
        }


gemini_client = GeminiClient()