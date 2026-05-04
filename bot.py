import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from captcha import CaptchaChallenge, generate_captcha
from config import settings

logger = logging.getLogger(__name__)

router = Router()


@dataclass
class UserCaptcha:
    """Хранит состояние капчи для конкретного пользователя."""

    chat_id: int
    challenge: CaptchaChallenge
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    message_id: int | None = None
    test_mode: bool = False


# Хранилище активных капч: user_id -> UserCaptcha
active_captchas: dict[int, UserCaptcha] = {}

# Пользователи, которым не удалось отправить капчу (приватность),
# ждут когда сами напишут /start
# user_id -> chat_id
pending_users: dict[int, int] = {}


def build_captcha_keyboard(challenge: CaptchaChallenge) -> InlineKeyboardMarkup:
    """Строит inline-клавиатуру с вариантами ответа."""
    buttons = []
    for i, option in enumerate(challenge.options):
        buttons.append([InlineKeyboardButton(text=option, callback_data=f"cap:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_captcha(bot: Bot, user_id: int, chat_id: int, user_name: str) -> None:
    """Создаёт и отправляет капчу пользователю. Используется и из join_request, и из /start."""
    challenge = generate_captcha()
    captcha = UserCaptcha(
        chat_id=chat_id,
        challenge=challenge,
        max_attempts=settings.MAX_ATTEMPTS,
    )
    active_captchas[user_id] = captcha

    welcome_text = settings.WELCOME_MESSAGE.format(name=user_name)
    captcha_text = f"\n\n🧩 {challenge.question}\n\nПопыток: {captcha.max_attempts}"
    keyboard = build_captcha_keyboard(challenge)

    try:
        msg = await bot.send_message(
            user_id,
            welcome_text + captcha_text,
            reply_markup=keyboard,
        )
        captcha.message_id = msg.message_id
    except TelegramAPIError as e:
        logger.error("Не удалось отправить капчу пользователю %d: %s", user_id, e)
        active_captchas.pop(user_id, None)
        raise

    # Запускаем таймаут
    asyncio.create_task(schedule_captcha_timeout(bot, user_id, chat_id))


async def schedule_captcha_timeout(bot: Bot, user_id: int, chat_id: int) -> None:
    """Фоновая задача: отклоняет запрос на вступление по истечении таймаута."""
    await asyncio.sleep(settings.CAPTCHA_TIMEOUT)

    captcha = active_captchas.pop(user_id, None)
    if captcha is not None:
        logger.info("Капча для пользователя %d истекла", user_id)
        try:
            await bot.decline_chat_join_request(chat_id, user_id)
        except TelegramAPIError as e:
            logger.warning(
                "Не удалось отклонить запрос пользователя %d: %s", user_id, e
            )

    # Удаляем из ожидающих, если был там
    pending_users.pop(user_id, None)

    try:
        await bot.send_message(
            user_id,
            "⏰ Время проверки истекло. Попробуйте отправить запрос на вступление ещё раз.",
        )
    except TelegramAPIError:
        pass  # Пользователь ограничил ЛС — ничего не поделать


async def schedule_pending_timeout(bot: Bot, user_id: int, chat_id: int) -> None:
    """Фоновая задача: отклоняет запрос, если пользователь так и не написал /start."""
    await asyncio.sleep(settings.CAPTCHA_TIMEOUT)

    chat_id = pending_users.pop(user_id, None)
    if chat_id is not None:
        logger.info(
            "Пользователь %d не написал /start за отведённое время, отклоняем запрос",
            user_id,
        )
        try:
            await bot.decline_chat_join_request(chat_id, user_id)
        except TelegramAPIError as e:
            logger.warning(
                "Не удалось отклонить запрос пользователя %d: %s", user_id, e
            )


@router.chat_join_request()
async def on_join_request(event: ChatJoinRequest, bot: Bot) -> None:
    """Обрабатывает запрос пользователя на вступление в канал."""
    user = event.from_user
    chat_id = event.chat.id

    logger.info(
        "Получен ChatJoinRequest: пользователь %s (id=%d) в чат %d",
        user.full_name,
        user.id,
        chat_id,
    )

    if user.id in active_captchas:
        logger.info("Пользователь %d уже имеет активную капчу, перегенерируем", user.id)

    # Убираем из ожидающих, если был
    pending_users.pop(user.id, None)

    # Пытаемся отправить капчу
    try:
        await send_captcha(bot, user.id, chat_id, user.first_name or user.full_name)
    except TelegramAPIError:
        # Не смогли отправить — скорее всего пользователь ограничил ЛС
        logger.info(
            "Пользователь %d ограничил получение сообщений, ждём /start",
            user.id,
        )
        pending_users[user.id] = chat_id
        asyncio.create_task(schedule_pending_timeout(bot, user.id, chat_id))


@router.callback_query(F.data.startswith("cap:"))
async def on_captcha_answer(callback: CallbackQuery, bot: Bot) -> None:
    """Обрабатывает ответ пользователя на капчу."""
    user_id = callback.from_user.id

    # Проверяем, есть ли активная капча
    captcha = active_captchas.get(user_id)
    if captcha is None:
        await callback.answer(
            "⏰ Время проверки истекло. Попробуйте ещё раз.", show_alert=True
        )
        return

    # Парсим выбранный вариант
    try:
        selected_index = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка. Попробуйте ещё раз.", show_alert=True)
        return

    # Проверяем ответ
    if selected_index == captcha.challenge.correct_index:
        # ✅ Правильный ответ
        active_captchas.pop(user_id, None)

        if captcha.test_mode:
            success_text = (
                "✅ ТЕСТ: Капча пройдена!\n\n"
                "В боевом режиме запрос на вступление был бы одобрен."
            )
        else:
            try:
                await bot.approve_chat_join_request(captcha.chat_id, user_id)
                logger.info("Пользователь %d прошёл капчу, запрос одобрен", user_id)
            except TelegramAPIError as e:
                logger.warning(
                    "Не удалось одобрить запрос пользователя %d: %s", user_id, e
                )

            success_text = "✅ Поздравляем! Вы прошли проверку.\n\nДобро пожаловать в Барахолку! 🎉"

        try:
            await callback.message.edit_text(success_text, reply_markup=None)
        except TelegramAPIError:
            pass

        await callback.answer("✅ Правильно!", show_alert=False)
    else:
        # ❌ Неправильный ответ
        captcha.attempts += 1
        remaining = captcha.max_attempts - captcha.attempts

        if remaining <= 0:
            # Попытки исчерпаны
            active_captchas.pop(user_id, None)

            if captcha.test_mode:
                fail_text = (
                    "❌ ТЕСТ: Капча не пройдена.\n\n"
                    "В боевом режиме запрос на вступление был бы отклонён.\n"
                    "Отправьте /test чтобы попробовать снова."
                )
            else:
                try:
                    await bot.decline_chat_join_request(captcha.chat_id, user_id)
                    logger.info(
                        "Пользователь %d не прошёл капчу, запрос отклонён", user_id
                    )
                except TelegramAPIError as e:
                    logger.warning(
                        "Не удалось отклонить запрос пользователя %d: %s", user_id, e
                    )

                fail_text = (
                    "❌ К сожалению, вы не прошли проверку.\n\n"
                    "Вы можете отправить запрос на вступление ещё раз и попробовать снова."
                )
            try:
                await callback.message.edit_text(fail_text, reply_markup=None)
            except TelegramAPIError:
                pass

            await callback.answer("❌ Попытки исчерпаны.", show_alert=True)
        else:
            # Ещё остались попытки — обновляем сообщение
            wrong_text = "❌ Неверно!"
            # Генерируем новую капчу для следующей попытки
            new_challenge = generate_captcha()
            captcha.challenge = new_challenge

            captcha_text = (
                f"\n\n🧩 {new_challenge.question}\n\nПопыток осталось: {remaining}"
            )
            keyboard = build_captcha_keyboard(new_challenge)

            try:
                await callback.message.edit_text(
                    wrong_text + captcha_text,
                    reply_markup=keyboard,
                )
            except TelegramAPIError:
                pass

            await callback.answer("❌ Неверно! Попробуйте ещё раз.", show_alert=False)


@router.message(CommandStart())
async def on_start(message: Message, bot: Bot) -> None:
    """Обрабатывает команду /start — если пользователь пишет напрямую."""
    user = message.from_user
    user_id = user.id
    # Команда может прийти как /start или /start join
    args = (
        message.text.split(maxsplit=1)[1].strip()
        if len(message.text.split()) > 1
        else ""
    )

    logger.info(
        "Получен /start от пользователя %s (id=%d), args='%s'",
        user.full_name,
        user_id,
        args,
    )

    # Если пользователь в списке ожидающих — отправляем капчу
    chat_id = pending_users.pop(user_id, None)
    if chat_id is not None:
        logger.info("Пользователь %d написал /start, отправляем капчу", user_id)
        try:
            await send_captcha(bot, user_id, chat_id, user.first_name or user.full_name)
        except TelegramAPIError:
            await message.answer(
                "❌ Произошла ошибка при отправке проверки. Попробуйте позже."
            )
        return

    # Если у пользователя уже есть активная капча — напоминаем
    if user_id in active_captchas:
        await message.answer(
            "🧩 Вы уже получили проверку! Ответьте на неё выше. "
            "Если не видите — попробуйте прокрутить чат вверх."
        )
        return

    # Обычный /start — без контекста join request
    await message.answer(
        "👋 Привет! Я — бот-проверка для канала Барахолка.\n\n"
        "Чтобы вступить в канал, отправьте запрос на вступление, "
        "и я отправлю вам проверку (капчу) в личные сообщения.\n\n"
        "Для тестирования капчи отправьте /test",
    )


@router.message(F.text == "/test")
async def on_test(message: Message, bot: Bot) -> None:
    """Тестовая команда — отправляет капчу без запроса на вступление."""
    user = message.from_user
    user_id = user.id

    logger.info("Тест капчи для пользователя %s (id=%d)", user.full_name, user_id)

    challenge = generate_captcha()
    captcha = UserCaptcha(
        chat_id=int(settings.CHANNEL_ID),
        challenge=challenge,
        max_attempts=settings.MAX_ATTEMPTS,
        test_mode=True,
    )
    active_captchas[user_id] = captcha

    welcome_text = f"🧪 ТЕСТОВЫЙ РЕЖИМ\n\n{settings.WELCOME_MESSAGE.format(name=user.first_name or user.full_name)}"
    captcha_text = f"\n\n🧩 {challenge.question}\n\nПопыток: {captcha.max_attempts}"

    keyboard = build_captcha_keyboard(challenge)
    await message.answer(welcome_text + captcha_text, reply_markup=keyboard)
