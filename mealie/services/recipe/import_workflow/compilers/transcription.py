import asyncio

from mealie.core.dependencies.dependencies import get_temporary_path
from mealie.schema.openai.compiled_source import OpenAICompiledSource
from mealie.services.openai import transcription
from mealie.services.openai.content import truncate_source_content

from .base import SourceCompiler


class TranscriptionCompiler(SourceCompiler):
    """
    Compiles a video into its transcript. The audio provider does the transcribing, but the
    transcript itself is already a faithful record of the source, so no further AI call is made.

    Subtitles are preferred over transcription and need no audio provider at all, so a video is
    always worth trying. If it yields nothing, the workflow falls back to reading the URL as a
    webpage exactly as it would have otherwise.
    """

    progress_key = "recipe.create-progress.downloading-video"
    requires_content = False

    def can_compile(self) -> bool:
        url = self.ctx.input.url
        if not url:
            return False

        return transcription.is_video_url(url)

    @property
    def _audio_provider_enabled(self) -> bool:
        settings = self.ctx.ai.provider_settings
        return bool(settings and settings.audio_provider_enabled)

    async def compile(self) -> OpenAICompiledSource | None:
        url = self.ctx.input.url or ""

        with get_temporary_path() as temp_path:
            video_data = await asyncio.to_thread(
                transcription.download_video, url, temp_path, download_audio=self._audio_provider_enabled
            )

            async def report_transcribing() -> None:
                await self.ctx.report_progress("recipe.create-progress.transcribing-audio-with-ai")

            transcript = await transcription.resolve_transcription(
                video_data, self.ctx.ai, before_transcribe=report_transcribing
            )

        if not transcript:
            # Expected when a video has no subtitles and no audio provider is configured;
            # the workflow falls back to reading the URL as a webpage.
            self.logger.info("Could not extract a transcript, falling back to other compilers")
            return None

        content_parts = [f"# {video_data['title']}"] if video_data["title"] else []
        if video_data["description"]:
            content_parts.append(f"## Video description\n\n{video_data['description']}")
        content_parts.append(f"## Video transcript\n\n{transcript}")

        # text pasted alongside the video link is often where the ingredient list actually lives.
        # It goes last so that truncation trims it before the transcript.
        if self.content:
            content_parts.append(f"## Text supplied by the user\n\n{self.content}")

        return OpenAICompiledSource(
            contains_recipe=True,
            content=truncate_source_content("\n\n".join(content_parts)),
            language=None,
            image_url=video_data["thumbnail_url"],
        )
