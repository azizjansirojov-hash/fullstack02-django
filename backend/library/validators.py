"""Upload validators for book covers and media file fields."""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible


@deconstructible
class MaxFileSizeValidator:
    """Reject uploads larger than ``max_bytes``."""

    message = 'File too large (%(size)s). Maximum size is %(max)s.'
    code = 'file_too_large'

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes

    def __call__(self, value):
        size = getattr(value, 'size', None)
        if size is None:
            return
        if size > self.max_bytes:
            raise ValidationError(
                self.message,
                code=self.code,
                params={
                    'size': filesizeformat(size),
                    'max': filesizeformat(self.max_bytes),
                },
            )

    def __eq__(self, other):
        return (
            isinstance(other, MaxFileSizeValidator)
            and self.max_bytes == other.max_bytes
        )


@deconstructible
class ImageContentValidator:
    """Ensure an uploaded image is decodable (not just renamed)."""

    message = 'Upload a valid image file (JPEG, PNG, or WebP).'
    code = 'invalid_image_content'

    def __call__(self, value):
        from PIL import Image, UnidentifiedImageError

        try:
            value.seek(0)
        except Exception:
            pass
        try:
            with Image.open(value) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise ValidationError(self.message, code=self.code) from exc
        finally:
            try:
                value.seek(0)
            except Exception:
                pass

    def __eq__(self, other):
        return isinstance(other, ImageContentValidator)


@deconstructible
class PdfContentValidator:
    """Require PDF magic bytes at the start of the file."""

    message = 'Upload a valid PDF file.'
    code = 'invalid_pdf_content'

    def __call__(self, value):
        try:
            value.seek(0)
            header = value.read(5)
        except Exception as exc:
            raise ValidationError(self.message, code=self.code) from exc
        finally:
            try:
                value.seek(0)
            except Exception:
                pass
        if not header.startswith(b'%PDF-'):
            raise ValidationError(self.message, code=self.code)

    def __eq__(self, other):
        return isinstance(other, PdfContentValidator)


COVER_MAX_BYTES = 5 * 1024 * 1024
PDF_MAX_BYTES = 50 * 1024 * 1024
AUDIO_MAX_BYTES = 100 * 1024 * 1024

cover_image_validators = [
    FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp']),
    MaxFileSizeValidator(COVER_MAX_BYTES),
    ImageContentValidator(),
]

pdf_file_validators = [
    FileExtensionValidator(allowed_extensions=['pdf']),
    MaxFileSizeValidator(PDF_MAX_BYTES),
    PdfContentValidator(),
]

audio_file_validators = [
    FileExtensionValidator(allowed_extensions=['mp3', 'm4a', 'ogg', 'wav']),
    MaxFileSizeValidator(AUDIO_MAX_BYTES),
]
