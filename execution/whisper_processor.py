"""
Whisper Processor - Audio transcription pipeline.

Downloads voice notes from Meta, converts to WAV if needed,
and transcribes via OpenAI Whisper API.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"


class TranscriptionError(Exception):
    """Raised when transcription fails."""


class WhisperProcessor:
    """Handles voice-note download → conversion → transcription."""

    def __init__(self) -> None:
        self._whatsapp_base = settings.WHATSAPP_API_URL.rstrip("/")
        self._openai_key = settings.OPENAI_API_KEY
        self._client: httpx.AsyncClient | None = None

    # ── lifecycle ───────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── download audio ──────────────────────────────────────────────
    async def download_audio(self, media_url: str, access_token: str) -> Path:
        """Download .ogg audio from Meta CDN to a temp file.

        Args:
            media_url: The direct media URL obtained from the webhook metadata.
            access_token: WhatsApp access token for auth.

        Returns:
            Path to the downloaded .ogg file.
        """
        client = await self._get_client()

        resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()

        suffix = ".ogg"
        # Try to detect format from content-type
        ct = resp.headers.get("content-type", "")
        if "mp4" in ct:
            suffix = ".mp4"
        elif "mpeg" in ct:
            suffix = ".mp3"
        elif "wav" in ct:
            suffix = ".wav"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="wa_audio_")
        tmp.write(resp.content)
        tmp.close()

        logger.info("whisper.audio_downloaded", path=tmp.name, size=len(resp.content))
        return Path(tmp.name)

    # ── format conversion ───────────────────────────────────────────
    async def convert_to_wav(self, audio_path: Path) -> Path:
        """Convert audio to 16 kHz mono WAV (optimal for Whisper).

        If already .wav, returns as-is. Otherwise uses pydub/ffmpeg.
        """
        if audio_path.suffix.lower() == ".wav":
            logger.debug("whisper.already_wav", path=str(audio_path))
            return audio_path

        try:
            from pydub import AudioSegment
        except ImportError:
            logger.error("whisper.pydub_not_installed – cannot convert audio")
            raise TranscriptionError("pydub is not installed; cannot convert audio formats")

        try:
            logger.info("whisper.converting", from_=audio_path.suffix, path=str(audio_path))
            audio = AudioSegment.from_file(str(audio_path))
            # Normalise: mono, 16 kHz
            audio = audio.set_channels(1).set_frame_rate(16000)

            wav_path = audio_path.with_suffix(".wav")
            audio.export(str(wav_path), format="wav")
            logger.info("whisper.converted", path=str(wav_path), duration_ms=len(audio))
            return wav_path
        except Exception as exc:
            logger.error("whisper.conversion_failed", error=str(exc))
            raise TranscriptionError(f"Audio conversion failed: {exc}") from exc

    # ── transcription ───────────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> str:
        """Send audio to OpenAI Whisper API and return transcribed text.

        Args:
            audio_path: Path to the audio file (WAV preferred).
            language: ISO 639-1 code (e.g. "en", "es"). None for auto-detect.

        Returns:
            Transcribed text string.
        """
        if not self._openai_key:
            raise TranscriptionError("OPENAI_API_KEY is not configured")

        client = await self._get_client()

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data: dict[str, str] = {
                "model": "whisper-1",
                "response_format": "text",
            }
            if language:
                data["language"] = language

            resp = await client.post(
                OPENAI_TRANSCRIPTION_URL,
                headers={"Authorization": f"Bearer {self._openai_key}"},
                files=files,
                data=data,
            )

        if resp.status_code == 429:
            logger.warning("whisper.rate_limited")
            resp.raise_for_status()  # will be retried by tenacity

        if resp.status_code >= 400:
            logger.error("whisper.api_error", status=resp.status_code, body=resp.text[:500])
            raise TranscriptionError(f"Whisper API error {resp.status_code}: {resp.text[:200]}")

        text = resp.text.strip()
        logger.info("whisper.transcribed", chars=len(text), path=str(audio_path))
        return text

    # ── full pipeline ───────────────────────────────────────────────
    async def process_voice_note(
        self,
        media_id: str,
        access_token: str | None = None,
        media_url: str | None = None,
        language: str | None = None,
    ) -> str:
        """Full pipeline: download → convert → transcribe → return text.

        Provide either media_url (direct from webhook metadata) or media_id
        (will be resolved via Meta API).

        Args:
            media_id: WhatsApp media ID from the webhook event.
            access_token: WhatsApp access token (falls back to settings).
            media_url: Direct download URL if already resolved.
            language: Optional language hint for Whisper.

        Returns:
            Transcribed text.

        Raises:
            TranscriptionError: on any pipeline failure.
        """
        token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        audio_path: Path | None = None
        wav_path: Path | None = None

        try:
            # Step 1: Resolve media URL if not provided
            if not media_url:
                media_url, _ = await self._resolve_media_url(media_id, token)

            # Step 2: Download
            audio_path = await self.download_audio(media_url, token)

            # Step 3: Convert
            wav_path = await self.convert_to_wav(audio_path)

            # Step 4: Transcribe
            text = await self.transcribe(wav_path, language=language)

            logger.info("whisper.pipeline_complete", media_id=media_id, text_len=len(text))
            return text

        except Exception as exc:
            logger.error("whisper.pipeline_failed", media_id=media_id, error=str(exc))
            raise
        finally:
            # Cleanup temp files
            for p in (audio_path, wav_path):
                if p and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    # ── helpers ─────────────────────────────────────────────────────
    async def _resolve_media_url(self, media_id: str, token: str) -> tuple[str, str]:
        """Resolve a media_id to a download URL via Meta API.

        Returns (url, mime_type).
        """
        client = await self._get_client()
        resp = await client.get(
            f"{self._whatsapp_base}/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["url"], data.get("mime_type", "audio/ogg")
