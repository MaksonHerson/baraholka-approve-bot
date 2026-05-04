import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import router
from config import settings


async def main() -> None:
    settings.validate()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger = logging.getLogger(__name__)
    logger.info("Бот запускается... Канал: %s", settings.CHANNEL_ID)

    # Проверяем, что бот может подключиться к API
    try:
        me = await bot.get_me()
        logger.info("Подключено к Telegram API: @%s (id=%d)", me.username, me.id)
    except Exception as e:
        logger.error("Не удалось подключиться к Telegram API: %s", e)
        return

    # Проверяем, нет ли установленного вебхука
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url:
        logger.warning("Обнаружен активный вебхук: %s — удаляем", webhook_info.url)
    else:
        logger.info("Вебхук не установлен, всё ок")

    # Устанавливаем описание бота — видно при открытии профиля
    try:
        await bot.set_my_short_description(
            "Бот-проверка для канала Барахолка. "
            f"Напишите /start чтобы пройти капчу и вступить в канал."
        )
        await bot.set_my_description(
            "🛡 Бот-антибот для канала Барахолка\n\n"
            "Если вы отправили запрос на вступление в канал — "
            "нажмите кнопку Start ниже или отправьте /start, "
            "чтобы пройти проверку (капчу) и быть допущенным в канал.\n\n"
            f"Ссылка для быстрого доступа: https://t.me/{me.username}?start=join"
        )
        logger.info("Описание профиля бота установлено")
    except Exception as e:
        logger.warning("Не удалось установить описание бота: %s", e)

    # Удаляем вебхук на случай если был установлен ранее
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Вебхук сброшен, начинаем polling...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    asyncio.run(main())
