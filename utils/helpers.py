import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio


def sanitize_html(text: str) -> str:
    allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
    pattern = r'<(?!/?({}))([^>]*)>'.format('|'.join(allowed_tags))
    return re.sub(pattern, '', text)


def generate_post_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def calculate_next_post_time(interval: int, last_post: Optional[datetime] = None) -> datetime:
    if last_post:
        return last_post + timedelta(seconds=interval)
    return datetime.utcnow() + timedelta(seconds=interval)


def split_long_message(text: str, max_length: int = 4000) -> List[str]:
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        split_point = text.rfind('\n', 0, max_length)
        if split_point == -1:
            split_point = text.rfind(' ', 0, max_length)
        if split_point == -1:
            split_point = max_length

        parts.append(text[:split_point])
        text = text[split_point:].lstrip()

    return parts


def extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


def format_time_delta(delta: timedelta) -> str:
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")

    return ' '.join(parts) or '0м'


async def retry_async(func, max_attempts: int = 3, delay: int = 1):
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(delay * (attempt + 1))


def clean_rss_content(html_content: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    for script in soup(["script", "style"]):
        script.decompose()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)

    return text[:2000]
