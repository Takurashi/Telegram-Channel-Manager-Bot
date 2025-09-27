from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from config.settings import DATABASE_URL, DEFAULT_AI_MODEL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    channels = relationship("Channel", back_populates="owner")


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True)
    channel_id = Column(String, unique=True)
    channel_name = Column(String)
    topic = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    post_interval = Column(Integer, default=7200)
    moderation_mode = Column(Boolean, default=False)
    ai_model = Column(String, default=DEFAULT_AI_MODEL)
    ai_prompt = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="channels")
    rss_sources = relationship("RSSSource", back_populates="channel")
    posts = relationship("Post", back_populates="channel")
    settings = Column(JSON, default={})


class RSSSource(Base):
    __tablename__ = "rss_sources"
    id = Column(Integer, primary_key=True)
    url = Column(String)
    name = Column(String)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime)
    last_guid = Column(String)
    error_count = Column(Integer, default=0)
    channel = relationship("Channel", back_populates="rss_sources")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    source_url = Column(String)
    original_title = Column(String)
    original_content = Column(Text)
    processed_content = Column(Text)
    media_urls = Column(JSON, default=[])
    status = Column(String, default="pending")
    scheduled_time = Column(DateTime)
    published_time = Column(DateTime)
    message_id = Column(Integer)
    channel = relationship("Channel", back_populates="posts")


Base.metadata.create_all(engine)
