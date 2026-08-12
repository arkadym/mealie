import functools
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypedDict

import yt_dlp
from yt_dlp.extractor.generic import GenericIE

from mealie.core import exceptions
from mealie.core.root_logger import get_logger

from .openai import OpenAIService

# Preferred subtitle languages, used only to break ties. The video's own language always wins,
# and any available track is better than none, so a recipe in a language not listed here still
# gets a transcript.
SUBTITLE_LANGS = ["en", "fr", "es", "de", "it"]

logger = get_logger()


class TranscribedAudio(TypedDict):
    # None when only subtitles were fetched, i.e. there is no audio provider to transcribe with
    audio: Path | None
    subtitle: Path | None
    title: str
    description: str
    thumbnail_url: str | None
    transcription: str


@functools.cache
def get_yt_dlp_extractors() -> list:
    """Build and cache the yt-dlp extractor list once per process lifetime."""
    return [ie for ie in yt_dlp.extractor.gen_extractors() if ie.working() and not isinstance(ie, GenericIE)]


def is_video_url(url: str) -> bool:
    """Whether yt-dlp recognizes the URL as something it can download."""

    if not url:
        return False

    return any(ie.suitable(url) for ie in get_yt_dlp_extractors())


def _base_lang(lang: str) -> str:
    """'en-orig' and 'en-GB' both reduce to 'en'."""

    return lang.split("-")[0].lower()


def select_subtitle_langs(info: dict) -> list[str]:
    """
    Order the video's available subtitle tracks by how much we want them.

    The video's own language comes first — a Russian video should be read in Russian rather
    than through a machine translation — then the preferred languages, then whatever is left,
    so that a video in an unlisted language is still transcribed.
    """

    available: list[str] = []
    for source in ("subtitles", "automatic_captions"):
        for lang in (info.get(source) or {}).keys():
            if lang not in available:
                available.append(lang)

    if not available:
        return []

    video_lang = _base_lang(info.get("language") or "")
    preference = ([video_lang] if video_lang else []) + SUBTITLE_LANGS

    def sort_key(lang: str) -> tuple[int, int]:
        base = _base_lang(lang)
        rank = preference.index(base) if base in preference else len(preference)
        # Prefer an exact track ('ru') over a regional or translated variant ('ru-RU')
        return rank, 0 if base == lang.lower() else 1

    return sorted(available, key=sort_key)


def find_subtitle_file(temp_path: Path, langs: list[str]) -> Path | None:
    """Find the subtitle file yt-dlp wrote, preferring the earliest language in `langs`."""

    subtitles = list(temp_path.glob("mealie*.vtt"))
    if not subtitles:
        return None

    for lang in langs:
        for path in subtitles:
            # yt-dlp writes 'mealie.<lang>.vtt'
            if path.name.rsplit(".", 2)[-2].lower() == lang.lower():
                return path

    return subtitles[0]


SUBTITLE_HEADERS = ("WEBVTT", "Kind:", "Language:")


def parse_subtitle_content(subtitle_content: str) -> str:
    """
    Turn a VTT subtitle file into plain text.

    Rolling captions repeat each line across consecutive cues as the text scrolls, so identical
    neighbouring lines are collapsed. Left in, they can triple the token count of a transcript
    and read as stuttering to the model.
    """

    lines: list[str] = []
    for raw_line in subtitle_content.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(SUBTITLE_HEADERS) or "-->" in line or line.isdigit():
            continue

        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)

    return " ".join(lines)


def download_video(url: str, temp_path: Path, *, download_audio: bool = True) -> TranscribedAudio:
    """
    Downloads subtitles from a video URL, and its audio unless `download_audio` is False.

    Subtitles alone are enough to produce a transcript, so when there is no audio provider to
    fall back on there is no reason to pay for the audio download.
    """

    output_template = temp_path / "mealie"  # No extension here

    def build_opts(langs: list[str], download: bool) -> dict:
        opts: dict = {
            "format": "bestaudio/best",
            "outtmpl": str(output_template) + ".%(ext)s",
            "quiet": True,
            "writesubtitles": bool(langs),
            "writeautomaticsub": bool(langs),
            "subtitleslangs": langs,
            "skip_download": not download,
            "ignoreerrors": True,
        }

        if download:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "32",
                }
            ]
            opts["postprocessor_args"] = ["-ac", "1"]

        return opts

    try:
        # Probe first: which subtitle tracks exist, and what language is the video in? Only then
        # can we ask for the right one, rather than guessing from a fixed list.
        with yt_dlp.YoutubeDL(build_opts([], False)) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            raise exceptions.VideoDownloadError(
                "Failed to extract video information. The video may be unavailable or the URL is invalid."
            )

        langs = select_subtitle_langs(info)
        if langs:
            logger.debug(f"Subtitle tracks available, in preference order: {langs}")
        else:
            logger.debug("Video has no subtitle tracks")

        metadata = {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "thumbnail_url": info.get("thumbnail") or None,
            "transcription": "",
        }

        if not langs and not download_audio:
            # Nothing left worth fetching
            return {"audio": None, "subtitle": None, **metadata}  # type: ignore[typeddict-item]

        # Ask for the best track only; requesting every language would download dozens of
        # machine translations of the same captions.
        with yt_dlp.YoutubeDL(build_opts(langs[:1], download_audio)) as ydl:
            downloaded = ydl.extract_info(url, download=True)

        if downloaded:
            metadata = {
                "title": downloaded.get("title", metadata["title"]),
                "description": downloaded.get("description", metadata["description"]),
                "thumbnail_url": downloaded.get("thumbnail") or metadata["thumbnail_url"],
                "transcription": "",
            }

        return {
            "audio": output_template.with_suffix(".mp3") if download_audio else None,
            "subtitle": find_subtitle_file(temp_path, langs),
            **metadata,  # type: ignore[typeddict-item]
        }
    except exceptions.VideoDownloadError:
        raise
    except Exception as e:
        raise exceptions.VideoDownloadError(f"Failed to download video: {e}") from e


def read_subtitles(video_data: TranscribedAudio) -> str:
    """Reads the downloaded subtitle file, if there is one. Returns an empty string on failure."""

    subtitle_path = video_data["subtitle"]
    if not subtitle_path:
        return ""

    try:
        with open(subtitle_path, encoding="utf-8") as f:
            subtitle_content = f.read()

        logger.info("Using subtitles from video instead of transcription")
        return parse_subtitle_content(subtitle_content)
    except Exception:
        logger.exception("Failed to read subtitles, falling back to transcription")
        return ""


async def resolve_transcription(
    video_data: TranscribedAudio,
    openai_service: OpenAIService,
    before_transcribe: Callable[[], Awaitable[None]] | None = None,
) -> str:
    """
    Resolves a video's transcript, preferring one that's already known, then its subtitles,
    and falling back to transcribing the audio with AI. `before_transcribe` is awaited only
    if that fallback is needed.

    Returns an empty string when subtitles are unavailable and there is no audio to fall back
    on, leaving the caller to try another way of reading the source.
    """

    if video_data["transcription"]:
        return video_data["transcription"]

    if subtitles := read_subtitles(video_data):
        return subtitles

    if not video_data["audio"]:
        logger.info("Video has no usable subtitles and no audio provider is configured")
        return ""

    if before_transcribe:
        await before_transcribe()

    try:
        transcript = await openai_service.transcribe_audio(video_data["audio"])
    except exceptions.RateLimitError:
        raise
    except Exception as e:
        raise exceptions.OpenAIServiceError(f"Failed to transcribe audio: {e}") from e

    if not transcript:
        raise exceptions.OpenAIServiceError("No transcription returned from OpenAI")

    return transcript
