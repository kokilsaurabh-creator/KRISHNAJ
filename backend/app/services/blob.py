"""Vercel Blob storage, via the official `vercel` Python SDK.

Files go to Blob and only the URL is stored in Postgres — never the bytes
themselves.

Uploads are proxied through this API rather than done directly from the
browser with a signed URL. Vercel's client-upload flow issues its tokens
through the @vercel/blob JS SDK's handleUpload, whose token format isn't a
documented thing a Python backend can mint, and its completion callback
can't reach localhost during development. Proxying is fine here because
the browser resizes every image to ~1200px before sending, which lands
far below Vercel's 4.5 MB function request-body cap, and it keeps the
blob write and the database row in one request so neither can be left
behind without the other.
"""

from vercel.blob import AsyncBlobClient
from vercel.blob import BlobNoTokenProvidedError

from app.config import get_settings


class BlobNotConfiguredError(RuntimeError):
    """No Blob credentials available in this environment."""


def _client() -> AsyncBlobClient:
    # On Vercel the SDK picks up OIDC credentials by itself; the static
    # token is the fallback that makes local development work, read via
    # Settings so backend/.env is the only place to put it.
    return AsyncBlobClient(token=get_settings().blob_read_write_token)


async def put_image(*, path: str, data: bytes, content_type: str) -> str:
    """Upload bytes and return the public URL."""
    client = _client()
    try:
        result = await client.put(
            path,
            data,
            access="public",
            content_type=content_type,
            # Two people photographing the same cheque shouldn't collide,
            # and an unguessable URL is what keeps a public blob private
            # in practice.
            add_random_suffix=True,
        )
    except BlobNoTokenProvidedError as exc:
        raise BlobNotConfiguredError(str(exc)) from exc
    finally:
        await client.aclose()
    return result.url


async def delete_blob(url: str) -> None:
    client = _client()
    try:
        await client.delete(url)
    except BlobNoTokenProvidedError as exc:
        raise BlobNotConfiguredError(str(exc)) from exc
    finally:
        await client.aclose()
