from sqlalchemy.orm import Session
from database.models import User, Channel, RSSSource, Post, SessionLocal
from datetime import datetime, timedelta
from typing import List, Optional


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user(db: Session, telegram_id: int, username: str = None):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def create_channel(db: Session, user_id: int, channel_id: str, channel_name: str, topic: str):
    channel = Channel(
        channel_id=channel_id,
        channel_name=channel_name,
        topic=topic,
        owner_id=user_id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def get_user_channels(db: Session, user_id: int):
    return db.query(Channel).filter(Channel.owner_id == user_id).all()


def add_rss_source(db: Session, channel_id: int, url: str, name: str):
    source = RSSSource(
        url=url,
        name=name,
        channel_id=channel_id
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def get_active_sources(db: Session):
    return db.query(RSSSource).filter(RSSSource.is_active == True).all()


def create_post(db: Session, channel_id: int, source_url: str, title: str, content: str, processed: str, media: list,
                scheduled: datetime):
    post = Post(
        channel_id=channel_id,
        source_url=source_url,
        original_title=title,
        original_content=content,
        processed_content=processed,
        media_urls=media,
        scheduled_time=scheduled
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_pending_posts(db: Session):
    now = datetime.utcnow()
    return db.query(Post).filter(
        Post.status == "pending",
        Post.scheduled_time <= now
    ).all()


def get_channel_queue(db: Session, channel_id: int):
    return db.query(Post).filter(
        Post.channel_id == channel_id,
        Post.status == "pending"
    ).order_by(Post.scheduled_time).all()


def update_post_status(db: Session, post_id: int, status: str, message_id: int = None):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.status = status
        if message_id:
            post.message_id = message_id
        if status == "published":
            post.published_time = datetime.utcnow()
        db.commit()
    return post


def update_source_check(db: Session, source_id: int, last_guid: str = None, error: bool = False):
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()
    if source:
        source.last_checked = datetime.utcnow()
        if last_guid:
            source.last_guid = last_guid
        if error:
            source.error_count += 1
        else:
            source.error_count = 0
        db.commit()
    return source


def toggle_channel_active(db: Session, channel_id: int):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if channel:
        channel.is_active = not channel.is_active
        db.commit()
    return channel


def update_channel_settings(db: Session, channel_id: int, **kwargs):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if channel:
        for key, value in kwargs.items():
            if hasattr(channel, key):
                setattr(channel, key, value)
        db.commit()
    return channel


def delete_rss_source(db: Session, source_id: int):
    source = db.query(RSSSource).filter(RSSSource.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
        return True
    return False


def delete_channel(db: Session, channel_id: int):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if channel:
        db.query(Post).filter(Post.channel_id == channel_id).delete()
        db.query(RSSSource).filter(RSSSource.channel_id == channel_id).delete()
        db.delete(channel)
        db.commit()
        return True
    return False


def get_moderation_posts(db: Session, channel_id: int):
    return db.query(Post).filter(
        Post.channel_id == channel_id,
        Post.status == "moderation"
    ).all()
