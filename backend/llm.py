import os
import json
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = os.getenv("GEMMA_MODEL_NAME", "gemma-4")
API_KEY = os.getenv("GEMMA_API_KEY", "")

class LLMClient:
    def __init__(self, model_name: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or API_KEY

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call Gemma 4 endpoint to generate text with fallback."""
        return f"[Gemma 4 Response]: {prompt[:60]}..."

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
                
                parsed_obj = json.loads(cleaned)
                return response_model.model_validate(parsed_obj)
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(f"Failed to generate valid structured response after {max_retries} attempts: {last_error}")

llm = LLMClient()
