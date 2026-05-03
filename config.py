import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")
    WELCOME_MESSAGE: str = os.getenv(
        "WELCOME_MESSAGE",
        "👋 Привет, {name}! Добро пожаловать в Барахолку!\n\n"
        "Чтобы вступить в канал, необходимо пройти небольшую проверку. "
        "Выберите правильный ответ из предложенных вариантов ниже.",
    )
    CAPTCHA_TIMEOUT: int = int(os.getenv("CAPTCHA_TIMEOUT", "300"))
    MAX_ATTEMPTS: int = int(os.getenv("MAX_ATTEMPTS", "3"))

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не задан. Укажите его в .env файле.")
        if not self.CHANNEL_ID:
            raise ValueError("CHANNEL_ID не задан. Укажите его в .env файле.")


settings = Settings()
