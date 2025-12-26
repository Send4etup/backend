from typing import List, Dict, Any, Optional
import tiktoken

class TokenCounter:
    def __init__(self, model: str):
        self.model = model
        self.encoder = self._init_encoder(model)

    def _init_encoder(self, model: str):
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")

    def text_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                total += self.text_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        total += self.text_tokens(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        total += self.image_tokens(part.get("image_url"))
        return total

    def image_tokens(self, width: int = 1024, height: int = 1024) -> int:
        """
        Приблизительный подсчет токенов для картинки.
        OpenAI считает картинки через vision tokens.
        Формула ниже повторяет официальную логику аппроксимации.

        1 token ≈ 14x14 пикселей
        """
        if not width or not height:
            width = 1024
            height = 1024

        patches_w = (width + 13) // 14
        patches_h = (height + 13) // 14
        patches = patches_w * patches_h

        base_tokens = 85
        return base_tokens + patches

    def completion_chunk_tokens(self, chunk_text: str) -> int:
        return self.text_tokens(chunk_text)
