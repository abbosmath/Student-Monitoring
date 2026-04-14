import os
from aiogram import Bot
from django.conf import settings


async def send_message(telegram_id: int, text: str):
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
    finally:
        await bot.session.close()
