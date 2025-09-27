from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Dict, Callable
import asyncio
from database.crud import *
from database.models import SessionLocal, Post
from core.rss_parser import RSSParser
from core.ai_processor import AIProcessor
from core.publisher import Publisher


class Scheduler:
    def __init__(self, bot):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.publisher = Publisher(bot)
        self.ai_processor = AIProcessor()

    def start(self):
        self.scheduler.add_job(
            self.check_rss_sources,
            IntervalTrigger(seconds=1800),
            id='rss_checker',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.publish_scheduled_posts,
            IntervalTrigger(seconds=60),
            id='post_publisher',
            replace_existing=True
        )

        self.scheduler.start()

    async def check_rss_sources(self):
        db = SessionLocal()
        try:
            sources = get_active_sources(db)

            parser = RSSParser()
            async with parser:
                for source in sources:
                    try:
                        entries = await parser.parse_feed(source.url, source.last_guid)

                        if entries:
                            channel = source.channel

                            for entry in entries[:2]:
                                if not entry.get('media'):
                                    continue

                                processed = await self.ai_processor.process_content(
                                    entry,
                                    {
                                        'ai_model': channel.ai_model,
                                        'ai_prompt': channel.ai_prompt,
                                        'topic': channel.topic
                                    }
                                )

                                last_post = db.query(Post).filter(
                                    Post.channel_id == channel.id
                                ).order_by(Post.scheduled_time.desc()).first()

                                if last_post and last_post.scheduled_time > datetime.utcnow():
                                    next_time = last_post.scheduled_time + timedelta(seconds=channel.post_interval)
                                else:
                                    next_time = datetime.utcnow() + timedelta(minutes=5)

                                create_post(
                                    db, channel.id, source.url,
                                    entry['title'], entry['content'],
                                    processed, entry.get('media', []),
                                    next_time
                                )

                            if entries:
                                update_source_check(db, source.id, entries[0]['guid'])

                    except Exception:
                        update_source_check(db, source.id, error=True)
        finally:
            db.close()

    async def publish_scheduled_posts(self):
        db = SessionLocal()
        try:
            posts = get_pending_posts(db)

            for post in posts:
                channel = post.channel

                if not channel.is_active:
                    continue

                if channel.moderation_mode:
                    update_post_status(db, post.id, "moderation")
                    continue

                message_id = await self.publisher.publish_post(
                    channel.channel_id,
                    post.processed_content,
                    post.media_urls
                )

                if message_id:
                    update_post_status(db, post.id, "published", message_id)
                else:
                    update_post_status(db, post.id, "failed")
        finally:
            db.close()

    def stop(self):
        self.scheduler.shutdown()
