import json
import asyncio
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from users.models import Parent

logger = logging.getLogger(__name__)

bot = Bot(token="8725934017:AAHFOIn41bvQi51mwtVnggcKIi1gZTDPzAw")


async def process_update(update_data: dict):
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())

    # Register handlers inline
    @dp.message()
    async def handle_message(message):
        text = message.text or ""

        if text.startswith("/start"):
            telegram_id = message.from_user.id
            full_name = message.from_user.full_name

            parent, created = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: Parent.objects.get_or_create(
                    telegram_id=telegram_id,
                    defaults={"full_name": full_name}
                )
            )
            if created:
                reply = (
                    "✅ Siz tizimga muvaffaqiyatli ulandingiz!\n\n"
                    "Endi farzandingizning darsga qatnashishi haqida xabarnomalar olasiz.\n\n"
                    f"Sizning Telegram ID: <code>{telegram_id}</code>\n"
                    "Ushbu ID ni o'qituvchiga bering — u sizni tizimda bog'laydi."
                )
            else:
                reply = (
                    f"👋 Qaytganingizdan xursandmiz, {parent.full_name}!\n\n"
                    f"Sizning Telegram ID: <code>{telegram_id}</code>"
                )
            await message.answer(reply, parse_mode="HTML")

        elif text.startswith("/id"):
            await message.answer(
                f"Sizning Telegram ID: <code>{message.from_user.id}</code>",
                parse_mode="HTML"
            )

        elif text.startswith("/mystudents"):
            telegram_id = message.from_user.id
            try:
                parent = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Parent.objects.get(telegram_id=telegram_id)
                )
                children = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: list(parent.children.all())
                )
                if children:
                    names = "\n".join(f"• {c.full_name} ({c.total_points} ball)" for c in children)
                    await message.answer(f"👨‍👩‍👧 Farzandlaringiz:\n\n{names}", parse_mode="HTML")
                else:
                    await message.answer("Hali farzand bog'lanmagan.")
            except Parent.DoesNotExist:
                await message.answer("Siz tizimda ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring.")

    update = Update(**update_data)
    await dp.process_update(update)


@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            asyncio.run(process_update(data))
        except Exception as e:
            logger.error(f"Webhook error: {e}")
        return HttpResponse("ok")
    return HttpResponse("Webhook active")
