import random
from dataclasses import dataclass


@dataclass
class CaptchaChallenge:
    question: str
    options: list[str]
    correct_index: int


# Категории эмодзи для генерации капчи
EMOJI_CATEGORIES: dict[str, list[str]] = {
    "фрукт": ["🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍑", "🥝", "🍍"],
    "животное": [
        "🐱",
        "🐶",
        "🐭",
        "🐹",
        "🐰",
        "🦊",
        "🐻",
        "🐼",
        "🐨",
        "🐯",
        "🦁",
        "🐮",
    ],
    "транспорт": [
        "🚗",
        "🚕",
        "🚙",
        "🚌",
        "🚎",
        "🏎️",
        "🚓",
        "🚑",
        "🚒",
        "🛻",
        "🚚",
        "🚛",
    ],
    "птица": ["🐔", "🐧", "🐦", "🐤", "🦆", "🦅", "🦉", "🦜", "🦩", "🕊️", "🦤", "🦢"],
    "цветок": ["🌸", "💮", "🏵️", "🌹", "🥀", "🌺", "🌻", "🌼", "🌷", "💐", "🪷", "🥀"],
    "мороженое": [
        "🍦",
        "🍧",
        "🍨",
        "🍩",
        "🍪",
        "🎂",
        "🍰",
        "🧁",
        "🥧",
        "🍫",
        "🍬",
        "🍭",
    ],
    "рыба": ["🐟", "🐠", "🐡", "🦈", "🐳", "🐋", "🐬", "🦭", "🐙", "🦑", "🦐", "🦞"],
    "погода": ["☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "🌨️", "❄️", "🌪️"],
}

# Эмодзи-дистракторы из других категорий
DISTRACTOR_POOL: list[str] = [
    "⭐",
    "🌟",
    "💫",
    "🔥",
    "💎",
    "🎯",
    "🎲",
    "🎸",
    "🎹",
    "🎺",
    "🎻",
    "🏀",
    "⚽",
    "🏈",
    "⚾",
    "🥎",
    "🎾",
    "🏐",
    "🏉",
    "🥏",
    "🎯",
    "🔮",
    "🧿",
    "🎮",
    "🕹️",
    "🎰",
    "🧩",
    "🪄",
    "🧲",
    "🔑",
    "🗝️",
    "🪄",
    "🎈",
    "🎉",
    "🎊",
    "🎁",
    "🎀",
    "🪅",
    "🎆",
    "🎇",
    "🏮",
    "🧧",
    "📌",
    "📎",
    "✂️",
    "📐",
    "📏",
    "🪞",
    "🪟",
    "📦",
]


def generate_captcha() -> CaptchaChallenge:
    """Генерирует случайную капчу: вопрос с одним правильным и несколькими неправильными вариантами."""
    category_name = random.choice(list(EMOJI_CATEGORIES.keys()))
    category_emojis = EMOJI_CATEGORIES[category_name]

    # Выбираем правильный эмодзи из категории
    correct_emoji = random.choice(category_emojis)

    # Выбираем 3 дистрактора (не из той же категории)
    distractors = random.sample(DISTRACTOR_POOL, 3)

    # Собираем все варианты и перемешиваем
    options = [correct_emoji] + distractors
    random.shuffle(options)
    correct_index = options.index(correct_emoji)

    # Формируем вопрос
    question = f"Выберите {category_name} из предложенных эмодзи:"

    return CaptchaChallenge(
        question=question,
        options=options,
        correct_index=correct_index,
    )
