"""Owner voice command and Kannada STT endpoints."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.database import get_db
from app.routers.serializers import serialize_approval
from app.schemas import VoiceCommandRequest, VoiceCommandResponse
from app.services.workflow import process_owner_voice_command_workflow

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/command", response_model=VoiceCommandResponse)
def run_voice_command(payload: VoiceCommandRequest, db: Session = Depends(get_db)):
    res = process_owner_voice_command_workflow(db, command_text=payload.command_text)
    created_app = res["created_approval"]
    return VoiceCommandResponse(
        transcript=res["transcript"],
        english_meaning=res["english_meaning"],
        intent=res["intent"],
        summary_en=res["summary_en"],
        summary_kn=res["summary_kn"],
        result_data=res["result_data"],
        created_approval=serialize_approval(db, created_app) if created_app else None,
        mcp_tool_used=res["mcp_tool_used"],
        source_data=res["source_data"],
    )


@router.post("/transcribe")
async def transcribe_voice_note(
    file: UploadFile | None = File(default=None),
    preset_key: str | None = Form(default=None),
    hint_text: str | None = Form(default=None),
):
    adapters = build_adapters()
    audio_bytes = await file.read() if file else None
    filename = (file.filename if file and file.filename else None) or f"{preset_key or 'voice'}.ogg"
    res = adapters.kannada_stt.transcribe(audio_bytes, filename, hint_text=hint_text)
    return {
        "transcript_kn": res.transcript_kn,
        "english_meaning": res.english_meaning,
        "confidence": res.confidence,
        "duration_sec": res.duration_sec,
        "mode": res.mode,
    }
