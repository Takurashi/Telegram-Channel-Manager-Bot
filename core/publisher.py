import io
import logging
from typing import List, Optional

import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile
from PIL import Image

_MAX_IMG_SIZE = 8000000
_PLACEHOLDER_IMG = "https://source.unsplash.com/1280x720/?news,technology"


class Publisher:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._http: Optional[aiohttp.ClientSession] = None

    async def publish_post(self, channel_id: str, content: str, media_urls: List[str] | None = None) -> Optional[int]:
        try:
            if media_urls:
                return await self._publish_with_media(channel_id, content, media_urls)
            msg = await self.bot.send_message(channel_id, content, parse_mode="HTML")
            return msg.message_id
        except Exception as e:
            logging.getLogger(__name__).exception("Publish failed: %s", e)
            return None

    async def edit_post(self, channel_id: str, message_id: int, html: str) -> bool:
        try:
            await self.bot.edit_message_text(chat_id=channel_id, message_id=message_id, text=html, parse_mode="HTML")
            return True
        except Exception:
            return False

    async def delete_post(self, channel_id: str, message_id: int) -> bool:
        try:
            await self.bot.delete_message(channel_id, message_id)
            return True
        except Exception:
            return False

    async def _publish_with_media(self, channel_id: str, content: str, media_urls: List[str]) -> Optional[int]:
        for url in media_urls:
            img_bytes = await self._download_image(url)
            if not img_bytes:
                logging.warning("Image download failed: %s", url)
                continue
            photo = BufferedInputFile(img_bytes, filename="image.jpg")
            try:
                msg = await self.bot.send_photo(channel_id, photo=photo, caption=content[:1024], parse_mode="HTML")
                return msg.message_id
            except Exception as e:
                logging.warning("Send photo failed (%s): %s", url, e)
        return await self._fallback_with_placeholder(channel_id, content)

    async def _fallback_with_placeholder(self, channel_id: str, content: str) -> Optional[int]:
        img_bytes = await self._download_image(_PLACEHOLDER_IMG)
        if img_bytes:
            photo = BufferedInputFile(img_bytes, filename="placeholder.jpg")
            try:
                msg = await self.bot.send_photo(channel_id, photo=photo, caption=content[:1024], parse_mode="HTML")
                return msg.message_id
            except Exception:
                pass
        try:
            msg = await self.bot.send_message(channel_id, content, parse_mode="HTML")
            return msg.message_id
        except Exception:
            return None

    async def _download_image(self, url: str) -> Optional[bytes]:
        if self._http is None:
            self._http = aiohttp.ClientSession()
        try:
            async with self._http.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                data = await r.read()
                if len(data) > _MAX_IMG_SIZE:
                    return None
                return self._optimize_image(data)
        except Exception as e:
            logging.debug("Download error %s: %s", url, e)
            return None

    @staticmethod
    def _optimize_image(data: bytes) -> bytes:
        try:
            img = Image.open(io.BytesIO(data))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85, optimize=True)
            return out.getvalue()
        except Exception:
            return data

    async def __aexit__(self, *exc):
        if self._http:
            await self._http.close()
