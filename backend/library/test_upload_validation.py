"""Tests for book cover / media upload validators."""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Book
from .validators import (
    COVER_MAX_BYTES,
    audio_file_validators,
    cover_image_validators,
    pdf_file_validators,
)


def _tiny_png():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new('RGB', (1, 1), color=(255, 0, 0)).save(buf, format='PNG')
    return buf.getvalue()


class UploadValidatorTests(TestCase):
    def test_valid_png_cover_accepted(self):
        upload = SimpleUploadedFile(
            'cover.png',
            _tiny_png(),
            content_type='image/png',
        )
        for validator in cover_image_validators:
            validator(upload)

    def test_disguised_text_as_jpg_rejected(self):
        upload = SimpleUploadedFile(
            'evil.jpg',
            b'not-an-image-at-all',
            content_type='image/jpeg',
        )
        with self.assertRaises(ValidationError):
            for validator in cover_image_validators:
                validator(upload)

    def test_oversized_cover_rejected(self):
        upload = SimpleUploadedFile(
            'huge.png',
            b'x' * (COVER_MAX_BYTES + 1),
            content_type='image/png',
        )
        with self.assertRaises(ValidationError) as ctx:
            for validator in cover_image_validators:
                validator(upload)
        self.assertEqual(ctx.exception.code, 'file_too_large')

    def test_pdf_magic_required(self):
        bad = SimpleUploadedFile('x.pdf', b'notpdf', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            for validator in pdf_file_validators:
                validator(bad)
        good = SimpleUploadedFile(
            'ok.pdf',
            b'%PDF-1.4 ok',
            content_type='application/pdf',
        )
        for validator in pdf_file_validators:
            validator(good)

    def test_audio_rejects_renamed_non_audio(self):
        fake = SimpleUploadedFile(
            'song.mp3',
            b'%PDF-1.4 not-audio',
            content_type='audio/mpeg',
        )
        with self.assertRaises(ValidationError):
            for validator in audio_file_validators:
                validator(fake)

    def test_audio_accepts_real_wav(self):
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b'\x00\x00' * 256)
        upload = SimpleUploadedFile(
            'ok.wav',
            buf.getvalue(),
            content_type='audio/wav',
        )
        for validator in audio_file_validators:
            validator(upload)

    def test_book_full_clean_rejects_bad_cover(self):
        book = Book(
            author_name='V',
            slug='validator-book',
            cover_image=SimpleUploadedFile(
                'fake.jpg',
                b'nope',
                content_type='image/jpeg',
            ),
        )
        with self.assertRaises(ValidationError):
            book.full_clean()
