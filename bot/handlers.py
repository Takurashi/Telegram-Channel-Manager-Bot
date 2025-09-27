from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards import Keyboards
from database.crud import *
from database import crud
from database.models import SessionLocal, Channel, RSSSource, Post
from core.publisher import Publisher
from core.ai_processor import AIProcessor
from config.settings import ADMIN_IDS
from datetime import datetime, timedelta
import random

router = Router()
keyboards = Keyboards()


class ChannelStates(StatesGroup):
    waiting_channel_id = State()
    waiting_channel_topic = State()
    waiting_rss_url = State()
    waiting_rss_search = State()
    waiting_post_content = State()
    waiting_ai_prompt = State()
    editing_post = State()
    waiting_manual_rss = State()


@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    db = SessionLocal()
    user = get_or_create_user(db, message.from_user.id, message.from_user.username)

    if message.from_user.id in ADMIN_IDS and not user.is_admin:
        user.is_admin = True
        db.commit()

    db.close()

    await message.answer(
        "👋 Добро пожаловать в Channel Manager Bot!\n\n"
        "Я помогу автоматизировать ведение ваших телеграм-каналов.",
        reply_markup=keyboards.main_admin_menu()
    )


@router.callback_query(F.data == "back_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=keyboards.main_admin_menu()
    )


@router.message(Command("my_channels"))
@router.callback_query(F.data == "my_channels")
async def show_channels(event: Message | CallbackQuery):
    db = SessionLocal()
    user = get_or_create_user(db, event.from_user.id, event.from_user.username)
    channels = get_user_channels(db, user.id)
    db.close()

    text = "У вас пока нет каналов. Хотите добавить первый?" if not channels else "📊 Ваши каналы:"

    keyboard = []
    if channels:
        for channel in channels:
            status = "🟢" if channel.is_active else "🔴"
            keyboard.append([InlineKeyboardButton(
                text=f"{status} {channel.channel_name}",
                callback_data=f"channel_{channel.id}"
            )])

    keyboard.append([InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")])
    if isinstance(event, CallbackQuery):
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if isinstance(event, Message):
        await event.answer(text, reply_markup=reply_markup)
    else:
        await event.message.edit_text(text, reply_markup=reply_markup)


@router.message(Command("add_channel"))
@router.callback_query(F.data == "add_channel")
async def add_channel_start(event: Message | CallbackQuery, state: FSMContext):
    text = (
        "<b>Шаг 1: Добавление канала</b>\n\n"
        "1. Добавьте этого бота в администраторы вашего канала с правом на публикацию постов.\n"
        "2. Пришлите сюда <code>@username</code>, ссылку <code>https://t.me/channel</code> или просто перешлите любое сообщение из него."
    )
    if isinstance(event, Message):
        await event.answer(text)
    else:
        await event.message.edit_text(text)
    await state.set_state(ChannelStates.waiting_channel_id)


@router.message(StateFilter(ChannelStates.waiting_channel_id))
async def process_channel_id(message: Message, state: FSMContext, bot: Bot):
    channel_id = None
    channel_name = None
    channel_input = None

    if message.forward_from_chat:
        channel_id = str(message.forward_from_chat.id)
        channel_name = message.forward_from_chat.title
    elif message.text:
        if message.text.startswith("@"):
            channel_input = message.text
        elif message.text.startswith("https://t.me/"):
            channel_input = f"@{message.text.split('/')[-1]}"

        if channel_input:
            try:
                chat = await bot.get_chat(channel_input)
                channel_id = str(chat.id)
                channel_name = chat.title
            except Exception:
                await message.answer(
                    "Не удалось найти канал. Убедитесь, что бот добавлен в него с правами администратора, и попробуйте снова.")
                return
        else:
            await message.answer(
                "Неверный формат. Пожалуйста, перешлите сообщение из канала или отправьте его @username / ссылку.")
            return
    else:
        await message.answer(
            "Неверный формат. Пожалуйста, перешлите сообщение из канала или отправьте его @username / ссылку.")
        return

    if channel_id:
        db = SessionLocal()
        existing_channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
        db.close()
        if existing_channel:
            await message.answer(
                f"Канал '{channel_name}' уже добавлен в систему. Вы можете управлять им через меню /my_channels.")
            await state.clear()
            return

        await state.update_data(channel_id=channel_id, channel_name=channel_name)
        await message.answer(
            "Отлично! Теперь введите основную тему канала (например: 'Новости IT', 'Криптовалюты', 'Маркетинг'):")
        await state.set_state(ChannelStates.waiting_channel_topic)


@router.message(StateFilter(ChannelStates.waiting_channel_topic))
async def process_channel_topic(message: Message, state: FSMContext):
    data = await state.get_data()
    db = SessionLocal()
    user = get_or_create_user(db, message.from_user.id, message.from_user.username)

    channel = create_channel(
        db, user.id, data['channel_id'],
        data['channel_name'], message.text
    )
    db.close()

    await state.clear()

    await message.answer(
        f"✅ Канал '{data['channel_name']}' успешно добавлен!\n\n"
        "Теперь необходимо добавить источники новостей (RSS-ленты).",
        reply_markup=keyboards.channel_menu(channel.id)
    )


@router.callback_query(F.data.startswith("channel_"))
async def channel_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    channel_id = int(callback.data.split("_")[1])

    db = SessionLocal()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    db.close()

    if not channel:
        await callback.answer("Канал не найден!", show_alert=True)
        return

    status = "активен 🟢" if channel.is_active else "на паузе 🔴"
    mode = "с модерацией" if channel.moderation_mode else "автоматический"

    text = (
        f"<b>Управление каналом: {channel.channel_name}</b>\n\n"
        f"<b>Тема:</b> {channel.topic}\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Режим AI:</b> {mode} (модель: <code>{channel.ai_model}</code>)\n"
        f"<b>Интервал постов:</b> ~{channel.post_interval // 60} мин."
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboards.channel_menu(channel_id)
    )


@router.callback_query(F.data.startswith("rss_"))
async def rss_sources_menu(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    sources = db.query(RSSSource).filter(RSSSource.channel_id == channel_id).all()
    db.close()

    text = "📰 У вас пока нет RSS-источников." if not sources else "📰 Ваши RSS-источники:"
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.rss_sources_menu(channel_id, sources)
    )


@router.callback_query(F.data.startswith("add_rss_"))
async def add_rss_manual_start(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[2])
    await state.update_data(channel_id=channel_id)
    await callback.message.edit_text(
        "📡 Введите URL RSS-ленты напрямую.\n\n"
        "Примеры популярных RSS:\n"
        "• <code>https://habr.com/ru/rss/all/all/</code> - Хабр\n"
        "• <code>https://vc.ru/rss</code> - VC.ru\n"
        "• <code>https://www.vedomosti.ru/rss/news</code> - Ведомости\n"
        "• <code>https://lenta.ru/rss</code> - Лента.ру"
    )
    await state.set_state(ChannelStates.waiting_manual_rss)


@router.message(StateFilter(ChannelStates.waiting_manual_rss))
async def process_manual_rss(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['channel_id']

    url_input = message.text.strip()
    if not url_input.startswith(('http://', 'https://')):
        formatted_url = f"https://{url_input}"
    else:
        formatted_url = url_input

    import feedparser
    feed = feedparser.parse(formatted_url)

    if feed.entries:
        db = SessionLocal()
        title = feed.feed.get('title', formatted_url[:50])
        add_rss_source(db, channel_id, formatted_url, title)
        sources = db.query(RSSSource).filter_by(channel_id=channel_id).all()
        db.close()

        await message.answer(
            f"✅ RSS источник '{title}' успешно добавлен!",
            reply_markup=keyboards.rss_sources_menu(channel_id, sources)
        )
    else:
        await message.answer(
            "❌ Не удалось прочитать RSS по указанному URL. Проверьте правильность ссылки."
        )

    await state.clear()


@router.callback_query(F.data.startswith("create_"))
async def create_post_start(callback: CallbackQuery, bot: Bot):
    channel_id = int(callback.data.split("_")[1])

    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    sources = db.query(RSSSource).filter_by(channel_id=channel_id, is_active=True).all()

    if not channel:
        await callback.answer("Канал не найден!", show_alert=True)
        db.close()
        return

    if not sources:
        await callback.answer("Сначала добавьте RSS источники!", show_alert=True)
        db.close()
        return

    msg = await callback.message.edit_text("⏳ Ищу свежие новости...")

    try:
        from core.rss_parser import RSSParser
        ai_processor = AIProcessor()
        publisher = Publisher(bot)

        parser = RSSParser()
        async with parser:
            all_entries = []
            for source in sources:
                entries = await parser.parse_feed(source.url)
                if entries:
                    all_entries.extend(entries[:3])

            if not all_entries:
                await msg.edit_text("❌ Не найдено новых новостей в источниках.")
                db.close()
                return

            await msg.edit_text("🧠 Обрабатываю новость с помощью AI...")
            entry = random.choice(all_entries)

            processed_content = await ai_processor.process_content(
                entry,
                {
                    'ai_model': channel.ai_model,
                    'ai_prompt': channel.ai_prompt,
                    'topic': channel.topic
                }
            )

            media_urls = entry.get('media', [])

            await msg.edit_text("✅ Готово! Публикую пост в канал...")
            message_id = await publisher.publish_post(
                channel.channel_id,
                processed_content,
                media_urls
            )

            if message_id:
                new_post = create_post(
                    db, channel_id, sources[0].url,
                    entry['title'], entry['content'],
                    processed_content, media_urls,
                    datetime.utcnow()
                )
                update_post_status(db, new_post.id, "published", message_id)
                await msg.edit_text(
                    "✅ Пост успешно опубликован!",
                    reply_markup=keyboards.channel_menu(channel_id)
                )
            else:
                await msg.edit_text(
                    f"❌ Ошибка при публикации поста в Telegram. Убедитесь, что бот является администратором в канале {channel.channel_name}.")

    except Exception as e:
        await msg.edit_text(f"❌ Произошла ошибка: {str(e)[:100]}")
    finally:
        db.close()


@router.callback_query(F.data.startswith("queue_"))
async def show_queue(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    posts = get_channel_queue(db, channel_id)
    db.close()

    if not posts:
        await callback.message.edit_text(
            "📭 Очередь постов пуста",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"channel_{channel_id}")]
            ])
        )
    else:
        await callback.message.edit_text(
            f"📝 В очереди {len(posts)} постов",
            reply_markup=keyboards.post_queue_menu(channel_id, posts)
        )


@router.callback_query(F.data.startswith("toggle_"))
async def toggle_channel_active(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    channel = crud.toggle_channel_active(db, channel_id)
    db.close()

    if channel:
        status = "запущен" if channel.is_active else "поставлен на паузу"
        await callback.answer(f"Канал {status}")
        await channel_menu(callback, state)


@router.callback_query(F.data.startswith("schedule_"))
async def schedule_menu(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return

    text = f"⏰ Текущий интервал между постами: ~{channel.post_interval // 60} минут.\n\nВыберите новый интервал:"
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.schedule_menu(channel_id, channel.post_interval)
    )


@router.callback_query(F.data.startswith("set_interval_"))
async def set_schedule(callback: CallbackQuery):
    try:
        _, _, channel_id_str, interval_str = callback.data.split("_")
        channel_id = int(channel_id_str)
        interval = int(interval_str)
    except ValueError:
        await callback.answer("Ошибка данных. Попробуйте снова.", show_alert=True)
        return

    db = SessionLocal()
    update_channel_settings(db, channel_id, post_interval=interval)
    db.close()

    await callback.answer(f"Интервал изменен на ~{interval // 60} минут.", show_alert=True)

    callback.data = f"schedule_{channel_id}"
    await schedule_menu(callback)


@router.callback_query(F.data.startswith("delete_"))
async def delete_channel_confirm(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить канал «{channel.channel_name}» и все связанные с ним данные?",
        reply_markup=keyboards.confirm_delete(channel_id)
    )


@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_channel_execute(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[2])
    db = SessionLocal()
    delete_channel(db, channel_id)
    db.close()

    await callback.answer("Канал успешно удален", show_alert=True)
    await show_channels(callback)


@router.callback_query(F.data.regexp(r"^ai_\d+$"))
async def ai_settings_menu(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()

    if not channel:
        await callback.answer("Канал не найден!", show_alert=True)
        return

    text = (
        f"<b>Настройки AI для канала «{channel.channel_name}»</b>\n\n"
        f"<b>Текущая модель:</b> <code>{channel.ai_model}</code>\n"
        f"<b>Режим модерации:</b> {'Включен' if channel.moderation_mode else 'Выключен'}\n\n"
        "Здесь вы можете изменить модель, которая будет обрабатывать тексты, или отредактировать системный промпт."
    )
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.ai_settings_menu(channel_id, channel.moderation_mode)
    )


@router.callback_query(F.data.startswith("ai_model_"))
async def choose_ai_model(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[2])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()

    if not channel:
        await callback.answer("Канал не найден!", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите модель, которую бот будет использовать для обработки новостей:",
        reply_markup=keyboards.ai_models_menu(channel_id, channel.ai_model)
    )


@router.callback_query(F.data.startswith("ai_prompt_"))
async def ai_prompt_change_start(callback: CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[2])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()

    if not channel:
        await callback.answer("Канал не найден!", show_alert=True)
        return

    current_prompt = channel.ai_prompt or "Пока не задан. Будет использован стандартный."

    await state.update_data(channel_id=channel_id)
    await callback.message.edit_text(
        f"<b>Текущий промпт:</b>\n<pre>{current_prompt}</pre>\n\n"
        "Отправьте новый текст системного промпта. Используйте `{topic}` для подстановки темы канала."
    )
    await state.set_state(ChannelStates.waiting_ai_prompt)


@router.message(StateFilter(ChannelStates.waiting_ai_prompt))
async def process_ai_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['channel_id']

    db = SessionLocal()
    update_channel_settings(db, channel_id, ai_prompt=message.text)
    channel = db.query(Channel).filter_by(id=channel_id).first()
    db.close()

    await message.answer("✅ Системный промпт успешно обновлен!")
    await state.clear()

    from aiogram.types.user import User
    from aiogram.types.chat import Chat

    callback_to_return = CallbackQuery(
        id="return_to_ai_menu",
        from_user=message.from_user,
        chat_instance="dummy",
        message=message,
        data=f"ai_{channel_id}"
    )
    await ai_settings_menu(callback_to_return)


@router.callback_query(F.data.startswith("set_model_"))
async def set_ai_model(callback: CallbackQuery):
    parts = callback.data.split("_")
    channel_id = int(parts[2])
    model = "-".join(parts[3:])

    db = SessionLocal()
    update_channel_settings(db, channel_id, ai_model=model)
    db.close()

    await callback.answer(f"Модель изменена на {model}", show_alert=True)
    await ai_settings_menu(callback)


@router.callback_query(F.data.startswith("moderation_"))
async def toggle_moderation(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    db = SessionLocal()
    channel = db.query(Channel).filter_by(id=channel_id).first()
    if channel:
        new_mode = not channel.moderation_mode
        update_channel_settings(db, channel_id, moderation_mode=new_mode)
        mode_text = "включен" if new_mode else "выключен"
        await callback.answer(f"Режим модерации {mode_text}")
        await ai_settings_menu(callback)
    db.close()
