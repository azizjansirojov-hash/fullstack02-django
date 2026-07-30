"""Byte-range streaming for gated library audio media."""

import mimetypes
import os
import re

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header

# Single-range only: bytes=<start>-<end>, bytes=<start>-, or bytes=-<suffix>
_SINGLE_RANGE_RE = re.compile(r'^\s*bytes=(\d*)-(\d*)\s*$', re.IGNORECASE)


def _file_size(file_obj):
    size = getattr(file_obj, 'size', None)
    if size is not None:
        return int(size)
    pos = file_obj.tell()
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(pos)
    return size


def _guess_content_type(filename, explicit=None):
    if explicit:
        return explicit
    if filename:
        guessed, _encoding = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    return 'application/octet-stream'


def _close_file(file_obj):
    if hasattr(file_obj, 'close'):
        try:
            file_obj.close()
        except OSError:
            pass


def parse_single_byte_range(range_header, file_size):
    """
    Parse one HTTP Range value.

    Returns:
        (start, end) inclusive for a valid range,
        None to fall back to a full 200 response,
        'unsatisfiable' for 416.
    """
    if not range_header or ',' in range_header:
        return None

    match = _SINGLE_RANGE_RE.match(range_header)
    if not match:
        return None

    start_str, end_str = match.groups()
    if not start_str and not end_str:
        return None

    if not start_str:
        try:
            suffix = int(end_str)
        except ValueError:
            return None
        if suffix <= 0:
            return None
        if suffix >= file_size:
            return (0, file_size - 1)
        return (file_size - suffix, file_size - 1)

    try:
        start = int(start_str)
    except ValueError:
        return None
    if start < 0 or start >= file_size:
        return 'unsatisfiable'

    if not end_str:
        return (start, file_size - 1)

    try:
        end = int(end_str)
    except ValueError:
        return None
    if end < start:
        return 'unsatisfiable'
    if end >= file_size:
        end = file_size - 1
    return (start, end)


def _apply_common_headers(response, *, filename, file_size, as_attachment):
    response['Accept-Ranges'] = 'bytes'
    if content_disposition := content_disposition_header(
        as_attachment,
        os.path.basename(filename) if filename else None,
    ):
        response['Content-Disposition'] = content_disposition


def serve_ranged_file(
    request,
    file_obj,
    *,
    filename='',
    content_type=None,
    as_attachment=False,
):
    """
    Stream a file with optional single-range support (RFC 7233 subset).

    Call only after auth and entitlement checks have passed.
    """
    resolved_type = _guess_content_type(filename, content_type)
    file_size = _file_size(file_obj)
    range_header = request.META.get('HTTP_RANGE', '')
    parsed = parse_single_byte_range(range_header, file_size) if range_header else None

    if parsed == 'unsatisfiable':
        _close_file(file_obj)
        response = HttpResponse(status=416)
        response['Content-Range'] = f'bytes */{file_size}'
        _apply_common_headers(
            response,
            filename=filename,
            file_size=file_size,
            as_attachment=as_attachment,
        )
        return response

    if parsed is None:
        if file_obj.tell() != 0:
            file_obj.seek(0)
        response = FileResponse(
            file_obj,
            as_attachment=as_attachment,
            filename=filename,
            content_type=resolved_type,
        )
        _apply_common_headers(
            response,
            filename=filename,
            file_size=file_size,
            as_attachment=as_attachment,
        )
        return response

    start, end = parsed
    length = end - start + 1
    file_obj.seek(start)

    def stream():
        remaining = length
        while remaining > 0:
            chunk = file_obj.read(min(4096, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

    response = StreamingHttpResponse(stream(), status=206, content_type=resolved_type)
    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    response['Content-Length'] = str(length)
    _apply_common_headers(
        response,
        filename=filename,
        file_size=file_size,
        as_attachment=as_attachment,
    )
    if hasattr(file_obj, 'close'):
        response._resource_closers.append(file_obj.close)
    return response
