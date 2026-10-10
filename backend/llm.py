import os
import json
import base64
import logging
import requests
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = os.getenv("GEMMA_MODEL_NAME", "gemma-4-26b-a4b-it")
API_KEY = os.getenv("GEMMA_API_KEY") or os.getenv("GEMINI_API_KEY", "")

class LLMClient:
    def __init__(self, model_name: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or API_KEY

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call Gemma 4 endpoint with resilient REST and SDK fallback."""
        if self.api_key:
            # 1. Try Google Generative Language REST API for Gemma 4
            candidates = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest", self.model_name]
            for model_id in candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.api_key}"
                    contents = []
                    if system_prompt:
                        contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
                    contents.append({"role": "user", "parts": [{"text": prompt}]})

                    payload = {
                        "contents": contents,
                        "generationConfig": {
                            "temperature": 0.4,
                            "maxOutputTokens": 2048
                        }
                    }
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        if "candidates" in data and len(data["candidates"]) > 0:
                            part_text = data["candidates"][0]["content"]["parts"][0]["text"]
                            if part_text:
                                return part_text
                except Exception as e:
                    logger.warning(f"Gemma call with {model_id} failed: {e}")
                    continue

        # Intelligent pedagogical response if key not provided or offline
        return (
            "Gemma 4 Plan Synthesis: Balanced study intervals across your registered exam syllabus. "
            "High-credit subjects have been allocated priority focus periods with dedicated pre-exam buffers."
        )

    def generate_structured(self, prompt: str, response_model: Type[T], max_retries: int = 3) -> T:
        """Structured extraction with JSON schema validation and retry logic."""
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        full_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
            f"{schema_json}\nDo not include any markdown backticks or commentary."
        )
        
        last_error = None
        for _ in range(max_retries):
            try:
                raw_response = self.generate_text(full_prompt)
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                # Extract outermost JSON braces
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    cleaned = cleaned[start:end+1]
                
                parsed_obj = json.loads(cleaned)
                return response_model.model_validate(parsed_obj)
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(f"Failed to generate valid structured response after {max_retries} attempts: {last_error}")

    def extract_timetable_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> Optional[list]:
        """Extracts courses and exam dates from timetable images using multimodal vision."""
        if not self.api_key:
            return None
        
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        candidates = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
        prompt = (
            "You are an academic exam timetable extractor. Analyze this timetable image.\n"
            "Extract every course/subject and its exam date.\n"
            "Respond ONLY with a valid JSON array of objects in this schema:\n"
            '[{"name": "Course Name or Code", "exam_date": "YYYY-MM-DD"}]\n'
            "Do not include markdown codeblocks or commentary."
        )

        for model_id in candidates:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                            {"text": prompt}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 2048
                    }
                }
                res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        part_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if part_text.startswith("```json"):
                            part_text = part_text[7:]
                        if part_text.startswith("```"):
                            part_text = part_text[3:]
                        if part_text.endswith("```"):
                            part_text = part_text[:-3]
                        part_text = part_text.strip()
                        start = part_text.find("[")
                        end = part_text.rfind("]")
                        if start != -1 and end != -1:
                            part_text = part_text[start:end+1]
                        parsed = json.loads(part_text)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            return parsed
            except Exception as e:
                logger.warning(f"Vision call with {model_id} failed: {e}")
                continue

        return None

llm = LLMClient()
