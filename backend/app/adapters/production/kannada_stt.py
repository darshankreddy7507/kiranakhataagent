"""Production Kannada Speech-to-Text adapter scaffold."""

from typing import Any
import httpx

from app.adapters.interfaces import SpeechTranscriptionResult


class ProductionKannadaSttAdapter:
    mode = "production"

    def __init__(self, api_key: str, endpoint: str) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    def transcribe(
        self, audio_bytes: bytes | None, filename: str, hint_text: str | None = None
    ) -> SpeechTranscriptionResult:
        if not self.api_key or not self.endpoint:
            raise RuntimeError("KANNADA_STT_API_KEY and KANNADA_STT_ENDPOINT must be set")
        if not audio_bytes:
            raise ValueError("audio_bytes required in production STT mode")

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (filename, audio_bytes)},
                data={"language": "kn-IN"},
            )
            resp.raise_for_status()
            data = resp.json()
        return SpeechTranscriptionResult(
            transcript_kn=data.get("transcript", ""),
            english_meaning=data.get("translation", data.get("transcript", "")),
            confidence=float(data.get("confidence", 0.9)),
            duration_sec=int(data.get("duration_sec", 5)),
            mode=self.mode,
        )

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.api_key and self.endpoint)
        return {
            "adapter": "kannada_stt",
            "mode": "production",
            "configured": configured,
            "note": "Kannada STT endpoint configured" if configured else "Missing KANNADA_STT_API_KEY or KANNADA_STT_ENDPOINT",
        }
