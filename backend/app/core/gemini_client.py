import base64
import io
from PIL import Image
import google.generativeai as genai

from app.config import get_settings

settings = get_settings()


class GeminiClient:
    """
    Wraps Gemini 1.5 Flash for visual question answering.

    Gemini sees the actual page images retrieved by ColPali and answers
    the user's question by reading them — tables, charts, handwriting,
    mixed layouts, all handled natively by the vision model.

    Free tier: 15 requests/minute, 1 million tokens/day.
    """

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def answer_with_pages(
        self,
        question: str,
        page_images: list[Image.Image],
        page_numbers: list[int],
    ) -> str:
        """
        Send the question + retrieved page images to Gemini and get an answer.

        The prompt is carefully structured so Gemini:
        1. Knows which pages it's looking at
        2. Grounds its answer in the visual content
        3. Cites the page number when referencing specific content
        """
        parts = []

        # System context
        parts.append(
            "You are a document analysis assistant. "
            "You have been given specific pages from a document that are "
            "most relevant to the user's question. Analyze the visual content "
            "of these pages — including any tables, charts, diagrams, or text "
            "— and answer the question accurately. "
            "Always cite which page number you found the information on.\n\n"
        )

        # Attach each retrieved page image
        for i, (img, page_num) in enumerate(zip(page_images, page_numbers)):
            parts.append(f"Page {page_num}:\n")
            parts.append(self._image_to_part(img))
            parts.append("\n")

        # The actual question
        parts.append(f"\nQuestion: {question}\n\nAnswer:")

        response = self.model.generate_content(parts)
        return response.text.strip()

    def _image_to_part(self, image: Image.Image) -> dict:
        """Convert a PIL Image to the format Gemini expects."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        return {
            "mime_type": "image/png",
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        }


gemini_client = GeminiClient()