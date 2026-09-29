import json
from pathlib import Path
import tempfile
import unittest

from antigravity_migrator.annotation_generator import (
    AnnotationGenerator,
    ensure_annotation_file,
    extract_title_from_transcript,
    generate_annotation_pbtxt,
)


class TestAnnotationGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_extract_title_with_user_request_tag(self):
        transcript_file = self.root / "transcript.jsonl"
        lines = [
            json.dumps({
                "step_index": 0,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "created_at": "2026-09-29T12:00:00Z",
                "content": "<USER_REQUEST>\n/goal /vibe-coding\n\n### 1. Цель\nСоздать модуль AnnotationGenerator для чатов\n\n### 2. DoD\n...</USER_REQUEST>",
            }),
            json.dumps({
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "created_at": "2026-09-29T12:05:00Z",
                "content": "Done",
            }),
        ]
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

        title, ts = extract_title_from_transcript(transcript_file)
        self.assertIn("Создать модуль AnnotationGenerator для чатов", title)
        self.assertIsNotNone(ts)
        self.assertEqual(ts, 1790683500)  # 2026-09-29 12:05:00 UTC

    def test_extract_title_without_tags_plain_text(self):
        transcript_file = self.root / "transcript.jsonl"
        lines = [
            json.dumps({
                "step_index": 0,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "created_at": "2026-09-29T10:00:00Z",
                "content": "Fix bug in authentication token refresh mechanism",
            })
        ]
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

        title, ts = extract_title_from_transcript(transcript_file)
        self.assertEqual(title, "Fix bug in authentication token refresh mechanism")
        self.assertIsNotNone(ts)

    def test_extract_title_word_limit(self):
        transcript_file = self.root / "transcript.jsonl"
        long_content = "слово " * 30
        lines = [
            json.dumps({
                "step_index": 0,
                "type": "USER_INPUT",
                "created_at": "2026-09-29T10:00:00Z",
                "content": long_content,
            })
        ]
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

        title, _ = extract_title_from_transcript(transcript_file)
        words = title.split()
        self.assertLessEqual(len(words), 10)
        self.assertGreaterEqual(len(words), 8)

    def test_extract_title_strips_slash_commands_and_markdown(self):
        transcript_file = self.root / "transcript.jsonl"
        lines = [
            json.dumps({
                "step_index": 0,
                "type": "USER_INPUT",
                "created_at": "2026-09-29T10:00:00Z",
                "content": "/goal /using-superpowers /vibe-coding\n### 1. Цель:\nНастройка VPN на сервере",
            })
        ]
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

        title, _ = extract_title_from_transcript(transcript_file)
        self.assertEqual(title, "Настройка VPN на сервере")

    def test_extract_title_corrupted_jsonl(self):
        transcript_file = self.root / "transcript.jsonl"
        content = (
            "corrupted line not a json\n"
            "\n"
            + json.dumps({
                "step_index": 0,
                "type": "USER_INPUT",
                "created_at": "2026-09-29T10:00:00Z",
                "content": "Valid query after corrupted lines",
            })
            + "\n{truncated json"
        )
        transcript_file.write_text(content, encoding="utf-8")

        title, ts = extract_title_from_transcript(transcript_file)
        self.assertEqual(title, "Valid query after corrupted lines")
        self.assertIsNotNone(ts)

    def test_extract_title_empty_or_no_user_input(self):
        transcript_file = self.root / "empty_transcript.jsonl"
        transcript_file.write_text("", encoding="utf-8")

        title, ts = extract_title_from_transcript(transcript_file)
        self.assertEqual(title, "Untitled Conversation")

    def test_generate_annotation_pbtxt(self):
        title = 'Тестовый чат: "Проверка" & \\символы\\'
        ts = 1788298094
        pbtxt = generate_annotation_pbtxt(title, ts)

        expected = (
            'title: "Тестовый чат: \\"Проверка\\" & \\\\символы\\\\"\n'
            'last_user_view_time {\n'
            '  seconds: 1788298094\n'
            '  nanos: 0\n'
            '}\n'
        )
        self.assertEqual(pbtxt, expected)

    def test_ensure_annotation_file(self):
        ann_path = self.root / "annotations" / "test-uuid.pbtxt"
        title = "Новый диалог"
        ts = 1788298094

        created = ensure_annotation_file(ann_path, title, ts)
        self.assertTrue(created)
        self.assertTrue(ann_path.exists())

        content = ann_path.read_text(encoding="utf-8")
        self.assertIn('title: "Новый диалог"', content)
        self.assertIn("seconds: 1788298094", content)

        # Без overwrite повторный вызов не должен перезаписывать
        not_overwritten = ensure_annotation_file(ann_path, "Другой заголовок", 12345, overwrite=False)
        self.assertFalse(not_overwritten)
        self.assertIn('title: "Новый диалог"', ann_path.read_text(encoding="utf-8"))

        # С overwrite=True перезаписывает
        overwritten = ensure_annotation_file(ann_path, "Обновленный заголовок", 12345, overwrite=True)
        self.assertTrue(overwritten)
        self.assertIn('title: "Обновленный заголовок"', ann_path.read_text(encoding="utf-8"))

    def test_annotation_generator_class_wrapper(self):
        transcript_file = self.root / "transcript.jsonl"
        transcript_file.write_text(
            json.dumps({
                "step_index": 0,
                "type": "USER_INPUT",
                "created_at": "2026-09-29T10:00:00Z",
                "content": "Class wrapper test query",
            }),
            encoding="utf-8",
        )

        title, ts = AnnotationGenerator.extract_title_from_transcript(transcript_file)
        self.assertEqual(title, "Class wrapper test query")

        pbtxt = AnnotationGenerator.generate_annotation_pbtxt(title, ts)
        self.assertIn('title: "Class wrapper test query"', pbtxt)


if __name__ == "__main__":
    unittest.main()
