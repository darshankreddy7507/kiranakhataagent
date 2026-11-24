"""Mock Kannada Speech-to-Text adapter supporting customer voice notes and owner voice commands."""

from typing import Any

from app.adapters.interfaces import SpeechTranscriptionResult


PRESET_VOICE_MAP: dict[str, tuple[str, str, int]] = {
    "suresh_rice_oil": (
        "ಅಣ್ಣ, 5 ಕೆಜಿ ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ ಮತ್ತು 2 ಲೀಟರ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ ಕಳಿಸಿ. ಖಾತೆಗೆ ಹಾಕಿ.",
        "Brother, send 5 kg Sona Masoori rice and 2 litres sunflower oil. Put it on khata.",
        9,
    ),
    "ramesh_credit_500": (
        "Ramesh ge 500 khatege haki.",
        "Add ₹500 to Ramesh's khata ledger.",
        4,
    ),
    "suresh_balance": (
        "Suresh eshtu baki iddane?",
        "How much balance does Suresh owe?",
        3,
    ),
    "sugar_stock": (
        "Sakkare stock eshtu ide?",
        "How much sugar stock is available?",
        3,
    ),
    "ramesh_reminder": (
        "Ramesh ge reminder kalisu.",
        "Draft and queue a payment reminder for Ramesh.",
        4,
    ),
}


class MockKannadaSttAdapter:
    mode = "mock"

    def transcribe(
        self, audio_bytes: bytes | None, filename: str, hint_text: str | None = None
    ) -> SpeechTranscriptionResult:
        if hint_text and hint_text.strip():
            text = hint_text.strip()
            return SpeechTranscriptionResult(
                transcript_kn=text,
                english_meaning=text,
                confidence=0.95,
                duration_sec=max(3, min(18, len(text) // 6)),
                mode=self.mode,
            )

        lower = (filename or "").lower()
        for key, (kn_text, en_text, dur) in PRESET_VOICE_MAP.items():
            if key in lower:
                return SpeechTranscriptionResult(
                    transcript_kn=kn_text,
                    english_meaning=en_text,
                    confidence=0.94,
                    duration_sec=dur,
                    mode=self.mode,
                )

        # Default realistic kirana Kannada customer voice note fallback
        return SpeechTranscriptionResult(
            transcript_kn="ಅಣ್ಣ, 2 ಕೆಜಿ ಸಕ್ಕರೆ ಮತ್ತು 1 ಕೆಜಿ ತೊಗರಿ ಬೇಳೆ ಕೊಡಿ. ಖಾತೆಗೆ ಹಾಕಿ.",
            english_meaning="Brother, give 2 kg sugar and 1 kg toor dal. Put it on khata.",
            confidence=0.92,
            duration_sec=6,
            mode=self.mode,
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "kannada_stt",
            "mode": "mock",
            "configured": True,
            "note": "Mock Kannada STT adapter active with realistic transcription & browser fallback",
        }
