import os
from typing import Protocol

from ..models import ModelResponse


class ModelProvider(Protocol):
    @property
    def cache_identity(self) -> dict: ...

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse: ...
    

class OpenAIProvider:
    """Calls the OpenAI chat API with the same settings for every role."""

    def __init__(self, model: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ImportError("Install the openai package: pip install -r requirements.txt") from error

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY in .env (see .env.example)")

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4")
        self.temperature = float(os.environ.get("OPENAI_TEMPERATURE", "0"))
        self.seed = int(os.environ.get("OPENAI_SEED", "567"))
        self.client = OpenAI()

    @property
    def cache_identity(self) -> dict:
        return {"provider": "openai", "model": self.model,
                "temperature": self.temperature, "seed": self.seed}

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse:

        request = {"model": self.model, "temperature": self.temperature, "seed": self.seed,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}]}

        # JSON mode is not supported by every model (e.g. the original gpt-4), so fall back
        # to plain text and let the agent extract the JSON object.
        from openai import BadRequestError
        try:
            completion = self.client.chat.completions.create(
                response_format={"type": "json_object"}, **request)
        except BadRequestError:
            completion = self.client.chat.completions.create(**request)

        usage = completion.usage
        return ModelResponse(completion.choices[0].message.content or "", completion.model,
                             usage.prompt_tokens if usage else 0,
                             usage.completion_tokens if usage else 0)
