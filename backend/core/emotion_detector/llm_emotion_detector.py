import logging
from typing import Optional

from core.model_providers import ModelMode, model_provider_manager


class LLMEmotionDetector:
    DEFAULT_EMOTIONS = [
        "admiration",
        "amusement",
        "anger",
        "annoyance",
        "approval",
        "caring",
        "confusion",
        "curiosity",
        "desire",
        "disappointment",
        "disapproval",
        "disgust",
        "embarrassment",
        "excitement",
        "fear",
        "gratitude",
        "grief",
        "joy",
        "love",
        "nervousness",
        "optimism",
        "pride",
        "realization",
        "relief",
        "remorse",
        "sadness",
        "surprise",
        "neutral",
    ]

    def __init__(self, provider: str, model: str, emotions: Optional[list[str]] = None):
        self.emotions = emotions or self.DEFAULT_EMOTIONS
        self.llm = model_provider_manager.get_model_instance(provider, model, mode=ModelMode.GENERATE)

    def _build_prompt(self, text: str) -> str:
        return (
            f"Analyze the following text and identify the primary emotion. "
            f"Respond with only one word from this list of emotions: {', '.join(self.emotions)}.\n\n"
            f'Text: "{text}"'
        )

    def get_emotion(self, text: str) -> Optional[str]:
        prompt = self._build_prompt(text)

        try:
            result = self.llm.invoke(prompt).strip().lower()
            for emotion in self.emotions:
                if emotion in result:
                    return emotion
            logging.warning("Emotion not matched in response: %s", result)
        except Exception as e:
            logging.warning("Emotion analysis failed: %s", e)

        return None
