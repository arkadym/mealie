from pathlib import Path

from mealie.services.openai import transcription


class TestSelectSubtitleLangs:
    def test_video_language_beats_the_preferred_list(self):
        """A Russian video should be read in Russian, not a machine translation of it."""
        info = {"language": "ru", "subtitles": {"en": [{}], "ru": [{}]}, "automatic_captions": {}}
        assert transcription.select_subtitle_langs(info)[0] == "ru"

    def test_preferred_list_orders_the_remainder(self):
        info = {"language": "ru", "subtitles": {"it": [{}], "en": [{}], "ru": [{}]}, "automatic_captions": {}}
        assert transcription.select_subtitle_langs(info) == ["ru", "en", "it"]

    def test_language_outside_the_preferred_list_is_still_selected(self):
        info = {"language": "ja", "subtitles": {}, "automatic_captions": {"ja": [{}]}}
        assert transcription.select_subtitle_langs(info) == ["ja"]

    def test_falls_back_to_any_available_track(self):
        info = {"subtitles": {"pl": [{}]}, "automatic_captions": {}}
        assert transcription.select_subtitle_langs(info) == ["pl"]

    def test_exact_track_beats_regional_variant(self):
        info = {"language": "en", "subtitles": {"en-GB": [{}], "en": [{}]}, "automatic_captions": {}}
        assert transcription.select_subtitle_langs(info)[0] == "en"

    def test_no_tracks_returns_empty(self):
        assert transcription.select_subtitle_langs({"subtitles": {}, "automatic_captions": {}}) == []

    def test_missing_keys_are_tolerated(self):
        assert transcription.select_subtitle_langs({}) == []


class TestFindSubtitleFile:
    def test_prefers_the_requested_language(self, tmp_path: Path):
        (tmp_path / "mealie.en.vtt").write_text("en")
        (tmp_path / "mealie.ru.vtt").write_text("ru")
        found = transcription.find_subtitle_file(tmp_path, ["ru", "en"])
        assert found is not None
        assert found.name == "mealie.ru.vtt"

    def test_falls_back_to_any_file(self, tmp_path: Path):
        (tmp_path / "mealie.pl.vtt").write_text("pl")
        assert transcription.find_subtitle_file(tmp_path, ["ja"]) is not None

    def test_returns_none_when_nothing_was_written(self, tmp_path: Path):
        assert transcription.find_subtitle_file(tmp_path, ["en"]) is None


class TestParseSubtitleContent:
    def test_strips_headers_timestamps_and_tags(self):
        vtt = "\n".join(
            [
                "WEBVTT",
                "Kind: captions",
                "Language: ru",
                "",
                "1",
                "00:00:01.000 --> 00:00:03.000",
                "<c>Hello</c> there",
            ]
        )
        assert transcription.parse_subtitle_content(vtt) == "Hello there"

    def test_collapses_rolling_caption_repeats(self):
        """Rolling captions repeat each line as the text scrolls; unhandled it triples the tokens."""
        vtt = "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:01.000 --> 00:00:03.000",
                "Line one",
                "",
                "00:00:03.000 --> 00:00:05.000",
                "Line one",
                "Line two",
                "",
                "00:00:05.000 --> 00:00:07.000",
                "Line two",
                "Line three",
            ]
        )
        assert transcription.parse_subtitle_content(vtt) == "Line one Line two Line three"

    def test_keeps_a_repeat_that_is_not_adjacent(self):
        vtt = "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:01.000 --> 00:00:03.000",
                "Stir well",
                "Add salt",
                "Stir well",
            ]
        )
        assert transcription.parse_subtitle_content(vtt) == "Stir well Add salt Stir well"

    def test_empty_input(self):
        assert transcription.parse_subtitle_content("") == ""


class TestResolveTranscriptionPreconditions:
    def test_no_audio_and_no_subtitles_is_not_an_error(self):
        """
        With no audio provider configured and no subtitles available there is nothing to
        transcribe, and the workflow should fall through to reading the URL as a webpage.
        """
        import asyncio
        from unittest.mock import MagicMock

        video_data = {
            "audio": None,
            "subtitle": None,
            "title": "",
            "description": "",
            "thumbnail_url": None,
            "transcription": "",
        }
        assert asyncio.run(transcription.resolve_transcription(video_data, MagicMock())) == ""

    def test_known_transcription_wins(self):
        import asyncio
        from unittest.mock import MagicMock

        video_data = {
            "audio": None,
            "subtitle": None,
            "title": "",
            "description": "",
            "thumbnail_url": None,
            "transcription": "already known",
        }
        assert asyncio.run(transcription.resolve_transcription(video_data, MagicMock())) == "already known"
