from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from sqlalchemy.orm import joinedload
from admin.auth import is_admin
from database.models import SessionLocal, Channel, RSSSource, Post, User
import json

admin_router = Router()


def get_stats_text():
    db = SessionLocal()
    total_users = db.query(User).count()
    total_channels = db.query(Channel).count()
    active_channels = db.query(Channel).filter(Channel.is_active == True).count()
    total_sources = db.query(RSSSource).count()
    total_posts = db.query(Post).count()
    pending_posts = db.query(Post).filter(Post.status == "pending").count()
    db.close()

    return (
        f"<b>📊 Статистика системы:</b>\n\n"
        f"<b>👥 Пользователей:</b> {total_users}\n"
        f"<b>📢 Каналов:</b> {total_channels} (активных: {active_channels})\n"
        f"<b>📰 RSS источников:</b> {total_sources}\n"
        f"<b>📝 Постов:</b> {total_posts} (в очереди: {pending_posts})"
    )


@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    text = get_stats_text()

    keyboard = [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_stats")],
        [InlineKeyboardButton(text="📢 Все каналы", callback_data="all_channels")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="all_users")]
    ]

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "refresh_stats")
async def refresh_stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    text = get_stats_text()

    try:
        await callback.message.edit_text(
            text,
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML"
        )
        await callback.answer("Статистика обновлена!")
    except Exception:
        await callback.answer("Данные не изменились.")


@admin_router.callback_query(F.data == "all_channels")
async def show_all_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    db = SessionLocal()
    channels = db.query(Channel).options(joinedload(Channel.owner)).all()
    db.close()

    if not channels:
        await callback.message.edit_text("В системе нет ни одного канала.")
        return

    text = "<b>📢 Все каналы в системе:</b>\n\n"
    for channel in channels[:20]:
        status = "🟢" if channel.is_active else "🔴"
        owner_info = channel.owner.username if channel.owner and channel.owner.username else f"ID: {channel.owner.telegram_id if channel.owner else 'N/A'}"
        text += f"{status} <b>{channel.channel_name}</b> (<code>{channel.channel_id}</code>)\n"
        text += f"   - Владелец: {owner_info}\n"
        text += f"   - Тема: {channel.topic}\n\n"

    await callback.message.edit_text(text, parse_mode="HTML")
