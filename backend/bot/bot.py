"""
Standalone Telegram bot process.
Run with: python bot/bot.py
On Railway this runs as a separate process via ProcFile.txt.
"""
import asyncio
import sys
import os

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from asgiref.sync import sync_to_async
from users.models import Parent
from students.services.stats import student_summary, get_period_range
import os

load_dotenv()

bot = Bot(token="8725934017:AAHFOIn41bvQi51mwtVnggcKIi1gZTDPzAw")
dp = Dispatcher(storage=MemoryStorage())


@sync_to_async
def get_or_create_parent(telegram_id, full_name):
    return Parent.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={"full_name": full_name},
    )


@sync_to_async
def get_parent_children(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        return parent, children
    except Parent.DoesNotExist:
        return None, []


# -- Inline keyboard for easy access --
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="/mystudents")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name

    parent, created = await get_or_create_parent(telegram_id, full_name)

    if created:
        text = (
            "✅ <b>Tizimga muvaffaqiyatli ulandingiz!</b>\n\n"
            "Endi farzandingizning darsga qatnashishi va baholari haqida "
            "avtomatik xabarnomalar olasiz.\n\n"
            f"🪪 <b>Sizning Telegram ID:</b> <code>{telegram_id}</code>\n\n"
            "📌 Ushbu ID-ni o'qituvchiga bering — u sizni tizimda farzandingizga bog'laydi."
        )
    else:
        text = (
            f"👋 <b>Qaytganingizdan xursandmiz, {parent.full_name}!</b>\n\n"
            f"🪪 <b>Sizning Telegram ID:</b> <code>{telegram_id}</code>"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(
        f"🪪 <b>Sizning Telegram ID:</b> <code>{message.from_user.id}</code>",
        parse_mode="HTML",
    )


@dp.message(Command("mystudents"))
async def cmd_mystudents(message: Message):
    parent, children = await get_parent_children(message.from_user.id)

    if parent is None:
        await message.answer(
            "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n"
            "/start buyrug'ini yuboring.",
            parse_mode="HTML",
        )
        return

    if not children:
        await message.answer(
            "ℹ️ Hali farzand bog'lanmagan.\n"
            "O'qituvchingizga Telegram ID-ingizni bering.",
            parse_mode="HTML",
        )
        return

    lines = [f"👨‍👩‍👧 <b>Farzandlaringiz:</b>\n"]
    for child in children:
        lines.append(f"• <b>{child.full_name}</b> — {child.total_points} ball ⭐")

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=get_main_keyboard())


@sync_to_async
def get_stats_for_parent(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        if not children:
            return None, "ℹ️ Hali farzand bog'lanmagan."

        response_lines = ["📊 <b>STATISTIKA</b>\n"]
        for child in children:
            response_lines.append(f"🧑 <b>{child.full_name}</b>\n")

            for period, label in [("monthly", "Oylik"), ("weekly", "Haftalik"), ("overall", "Umumiy")]:
                start, end = get_period_range(period)
                stats = student_summary(child, start, end)

                score_emoji = "⭐" if stats["points"] >= 0 else "❌"
                response_lines.append(
                    f"🔹 <i>{label}</i>:\n"
                    f"   Ball: <b>{stats['points']} {score_emoji}</b>\n"
                    f"   Keldi: <b>{stats['present']}</b> marta\n"
                    f"   Kelmadi: <b>{stats['absent']}</b> marta\n"
                )

        return parent, "\n".join(response_lines)
    except Parent.DoesNotExist:
        return None, "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n/start buyrug'ini yuboring."


@dp.message(Command("stats"))
@dp.message(lambda msg: msg.text == "📊 Statistika")
async def cmd_stats(message: Message):
    parent, text = await get_stats_for_parent(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Mavjud buyruqlar:</b>\n\n"
        "/start — Tizimga ulanish\n"
        "/id — Telegram ID-ingizni ko'rish\n"
        "/mystudents — Farzandlaringizni ko'rish\n"
        "/stats — 📊 Statistika ko'rish\n"
        "/help — Yordam",
        parse_mode="HTML",
    )


async def main():
    while True:
        try:
            print("🤖 Bot ishga tushdi...")
            await dp.start_polling(bot, allowed_updates=["message"])
        except Exception as e:
            print(f"Bot crashed: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
