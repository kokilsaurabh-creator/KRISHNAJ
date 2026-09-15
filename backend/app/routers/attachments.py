"""Attachments: images stored in Vercel Blob, referenced by URL from the
attachments table.

The size and type limits here are the real ones. The browser resizes and
re-encodes before uploading, but that's a courtesy to the user's data
plan, not a control — anything can POST to this endpoint, so the type is
decided by sniffing the bytes rather than trusting the multipart
Content-Type, and the size is capped while reading rather than after.
"""

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import Attachment, Payment, UserRole
from app.schemas.attachment import AttachmentOut
from app.services import blob

router = APIRouter(prefix="/attachments", tags=["attachments"], dependencies=[Depends(get_current_user)])

# Deliberately below Vercel's 4.5 MB function request-body limit, so an
# oversized upload gets this clear error instead of being cut off by the
# platform. A 1200px JPEG from the browser is ~200-400 KB.
MAX_BYTES = 4 * 1024 * 1024

_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# entity_type -> model, so an attachment can never point at a row that
# isn't there. Part 2 adds products here.
_ENTITY_MODELS = {"payment": Payment}

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sniff_mime(data: bytes) -> str | None:
    """Image type from the file's own magic bytes."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_filename(name: str, mime: str) -> str:
    stem = _UNSAFE_FILENAME.sub("-", (name or "image").rsplit("/", 1)[-1].rsplit(".", 1)[0])[:60]
    return f"{stem or 'image'}.{_EXTENSIONS[mime]}"


@router.get("", response_model=list[AttachmentOut])
async def list_attachments(
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[Attachment]:
    result = await session.execute(
        select(Attachment)
        .where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id)
        .order_by(Attachment.id)
    )
    return list(result.scalars().all())


@router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def create_attachment(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> Attachment:
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot attach to '{entity_type}'")

    if await session.get(model, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {entity_type} with id {entity_id}")

    # One byte past the limit is enough to know it's too big, and stops a
    # huge upload being read into memory in full.
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image is larger than {MAX_BYTES // (1024 * 1024)} MB",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    mime = _sniff_mime(data)
    if mime is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only JPEG, PNG and WebP images can be attached",
        )

    filename = _safe_filename(file.filename or "", mime)

    try:
        url = await blob.put_image(
            path=f"{entity_type}/{entity_id}/{filename}",
            data=data,
            content_type=mime,
        )
    except blob.BlobNotConfiguredError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "File storage isn't configured on this environment",
        )

    attachment = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        url=url,
        filename=filename,
        mime_type=mime,
        size_bytes=len(data),
    )
    session.add(attachment)
    try:
        await session.commit()
    except Exception:
        # The blob is already stored; without this it would linger with
        # nothing in the database pointing at it.
        await session.rollback()
        await blob.delete_blob(url)
        raise
    await session.refresh(attachment)
    return attachment


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def delete_attachment(attachment_id: int, session: AsyncSession = Depends(get_session)) -> None:
    attachment = await session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")

    url = attachment.url
    await session.delete(attachment)
    await session.commit()

    # After the row is gone: a blob with no row is invisible and costs
    # storage, but a row pointing at a deleted blob is a broken image in
    # the UI. If this fails the blob is orphaned rather than the record
    # being wrong, which is the better failure of the two.
    try:
        await blob.delete_blob(url)
    except blob.BlobNotConfiguredError:
        pass
