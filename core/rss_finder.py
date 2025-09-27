import asyncio
import aiohttp
from bs4 import BeautifulSoup
import feedparser
import g4f
from typing import List, Dict
from urllib.parse import urljoin, urlparse, quote_plus


class RSSFinder:
    def __init__(self):
        self.search_url = "https://duckduckgo.com/html/?q={}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def find_rss_by_topic(self, topic: str) -> List[Dict]:
        search_queries = await self.generate_search_keywords(topic)

        sites = set()
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for query in search_queries:
                try:
                    url = self.search_url.format(quote_plus(query))
                    async with session.get(url, timeout=10) as response:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        for link in soup.select('a.result__a'):
                            href = link.get('href')
                            if href and href.startswith('http'):
                                domain = urlparse(href).netloc
                                if domain:
                                    sites.add(f"https://{domain}")
                except Exception:
                    continue

        if not sites:
            return []

        feeds = await self.discover_rss_feeds(list(sites)[:15])
        validated = await self.validate_feeds(feeds)
        return sorted(validated, key=lambda x: x.get('entry_count', 0), reverse=True)[:5]

    async def generate_search_keywords(self, topic: str) -> List[str]:
        prompt = f"Generate 3 diverse search queries to find RSS feeds for the topic '{topic}'. Return only the queries, one per line."
        try:
            response = await g4f.ChatCompletion.create_async(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            keywords = response.strip().split('\n')
            return [k.strip() for k in keywords if k.strip()]
        except Exception:
            return [f'"{topic}" RSS feed', f'"{topic}" blog RSS']

    async def discover_rss_feeds(self, sites: List[str]) -> List[Dict]:
        feeds = []
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [self.fetch_site_feeds(site, session) for site in sites]
            results = await asyncio.gather(*tasks)
            for site_feeds in results:
                feeds.extend(site_feeds)
        return list({feed['url']: feed for feed in feeds}.values())

    async def fetch_site_feeds(self, site_url: str, session: aiohttp.ClientSession) -> List[Dict]:
        found_feeds = []
        try:
            async with session.get(site_url, timeout=7) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                for link in soup.find_all('link', {'type': ['application/rss+xml', 'application/atom+xml']}):
                    href = link.get('href')
                    if href:
                        feed_url = urljoin(site_url, href)
                        title = link.get('title', soup.title.string if soup.title else site_url)
                        found_feeds.append({'url': feed_url, 'title': title, 'site': site_url})
        except Exception:
            pass
        return found_feeds

    async def validate_feeds(self, feeds: List[Dict]) -> List[Dict]:
        validated = []
        tasks = [self.parse_and_validate(feed) for feed in feeds]
        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                validated.append(result)
        return validated

    async def parse_and_validate(self, feed: Dict) -> Dict | None:
        try:
            parsed = feedparser.parse(feed['url'])
            if parsed and parsed.entries:
                feed['title'] = parsed.feed.get('title', feed['title'])
                feed['entry_count'] = len(parsed.entries)
                return feed
        except Exception:
            return None
        return None
