import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from config.settings import BOT_TOKEN
from bot.handlers import router
from admin.panel import admin_router
from core.scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='🚀 Запустить/перезапустить бота'),
        BotCommand(command='/my_channels', description='📊 Мои каналы'),
        BotCommand(command='/add_channel', description='➕ Добавить новый канал'),
        BotCommand(command='/admin', description='👑 Панель администратора')
    ]
    await bot.set_my_commands(main_menu_commands)

async def main():
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN не найден! Проверьте ваш .env файл.")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(router)
    dp.include_router(admin_router)

    await set_main_menu(bot)

    scheduler = Scheduler(bot)
    scheduler.start()

    try:
        logger.info("Бот запущен")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по команде пользователя")