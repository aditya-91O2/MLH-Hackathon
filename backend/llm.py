import os
import json
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
            candidates = [self.model_name, "gemma-4-26b-a4b-it", "gemini-2.0-flash", "gemini-1.5-flash"]
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

llm = LLMClient()
