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

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, URLInputFile
from aiogram.filters import Command, or_f
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from asgiref.sync import sync_to_async
from django.db import transaction, close_old_connections

def sync_db_action(func):
    def wrapper(*args, **kwargs):
        close_old_connections()
        try:
            return func(*args, **kwargs)
        finally:
            close_old_connections()
    return wrapper

def sync_to_async_db(func):
    return sync_to_async(sync_db_action(func))

import time
from datetime import date
from users.models import Parent
from students.models import MarketItem, MarketOrder, Student, GroupMembership, Test, TestQuestion, TestOption, TestSubmission
from attendance.models import Performance
from students.services.stats import student_summary, get_period_range
from django.conf import settings
import socket

def _ensure_single_instance():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 47382))
        return s
    except socket.error:
        print("⚠️ Duplicate bot.py instance detected. Exiting this duplicate process.")
        sys.exit(0)

_bot_lock_socket = _ensure_single_instance()

BOT_TOKEN = os.getenv("BOT_TOKEN") or getattr(settings, "BOT_TOKEN", "")
if not BOT_TOKEN:
    print("ℹ️ BOT_TOKEN is not set in environment variables. Telegram bot service disabled.")
    sys.exit(0)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@sync_to_async_db
def get_or_create_parent(telegram_id, full_name):
    return Parent.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={"full_name": full_name},
    )


@sync_to_async_db
def get_parent_children(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        return parent, children
    except Parent.DoesNotExist:
        return None, []


# -- Keyboard layout --
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="📝 Testlar"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="🛒 Do'kon"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="/mystudents")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)



# -- TEST FUNCTIONS FOR PUPILS --

USER_TEST_SESSIONS = {}


@sync_to_async_db
def get_available_tests_for_parent(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        if not children:
            return None, [], [], "ℹ️ Hali farzand bog'lanmagan."

        group_ids = list(GroupMembership.objects.filter(student__in=children).values_list("group_id", flat=True))
        raw_tests = list(Test.objects.filter(group_id__in=group_ids, is_active=True).select_related("group").order_by("-created_at"))

        if not raw_tests:
            return parent, children, [], "📝 Hozircha faol guruh testlari mavjud emas."

        tests = []
        for t in raw_tests:
            tests.append({
                "id": t.id,
                "title": t.title,
                "group_name": t.group.name,
                "question_count": t.questions.count(),
                "deadline": t.deadline,
                "time_limit_minutes": t.time_limit_minutes,
            })

        test_ids = [t["id"] for t in tests]
        submissions = list(TestSubmission.objects.filter(student__in=children, test_id__in=test_ids))
        sub_map = {(s.student_id, s.test_id): s for s in submissions}

        return parent, children, tests, (sub_map, None)
    except Parent.DoesNotExist:
        return None, [], [], "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n/start buyrug'ini yuboring."


def get_full_question_image_url(q):
    url = q.get_image_display_url()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    domain = os.getenv("HOST_DOMAIN", "https://student-monitoring-production.up.railway.app")
    return f"{domain.rstrip('/')}{url}"


@sync_to_async_db
def load_test_details(test_id, child_id):
    try:
        test = Test.objects.get(pk=test_id)
        student = Student.objects.get(pk=child_id)
        existing_sub = TestSubmission.objects.filter(student=student, test=test).first()
        if existing_sub:
            return None, None, f"✅ <b>{student.full_name}</b> ushbu testni allaqachon topshirgan!\nNatija: <b>{existing_sub.score} / {existing_sub.total_questions}</b> ball"

        if test.is_expired():
            return None, None, "❌ Ushbu testning topshirish muddati tugagan."

        questions = list(test.questions.prefetch_related("options").all())
        if not questions:
            return None, None, "❌ Ushbu testda hali savollar mavjud emas."

        q_list = []
        for q in questions:
            opts = list(q.options.all())
            img_path = q.image.path if (q.image and os.path.exists(q.image.path)) else None
            q_list.append({
                "id": q.id,
                "text": q.question_text,
                "image_path": img_path,
                "image_url": get_full_question_image_url(q),
                "points": q.points,
                "options": [{"id": opt.id, "text": opt.option_text, "is_correct": opt.is_correct} for opt in opts]
            })

        return test, student, (q_list, None)
    except Exception as e:
        return None, None, f"❌ Xatolik: {str(e)}"


@sync_to_async_db
def complete_test_submission(student_id, test_id, score, total_questions):
    try:
        with transaction.atomic():
            student = Student.objects.select_for_update().get(pk=student_id)
            test = Test.objects.select_related("group").get(pk=test_id)

            sub, created = TestSubmission.objects.get_or_create(
                student=student,
                test=test,
                defaults={
                    "score": score,
                    "total_questions": total_questions,
                    "max_possible_points": total_questions,
                }
            )

            if created and score > 0:
                student.total_points += score
                student.save()

                Performance.objects.create(
                    student=student,
                    teacher=test.teacher,
                    points=score,
                    performance_type="exam",
                    comment=f"📝 Test: {test.title} ({score}/{total_questions})",
                    date=date.today()
                )

            return {
                "student_full_name": student.full_name,
                "student_points": student.total_points,
                "test_title": test.title,
                "group_name": test.group.name,
                "score": score,
                "total_questions": total_questions,
            }
    except Exception as e:
        print(f"[Test submission save error]: {e}")
        return None


@dp.message(or_f(Command("tests"), F.text == "📝 Testlar", F.text.contains("Testlar")))
async def cmd_tests(message: Message):
    parent, children, tests, result = await get_available_tests_for_parent(message.from_user.id)
    if isinstance(result, str):
        await message.answer(result, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    sub_map, _ = result
    lines = ["📝 <b>TESTLAR VA ONLAYN IMTIHONLAR</b>\n"]
    for child in children:
        lines.append(f"👤 <b>{child.full_name}</b> (Joriy ball: {child.total_points} ⭐)")
    lines.append("\n📌 <b>Mavjud guruh testlari:</b>\n")

    inline_keyboard_rows = []
    for test in tests:
        q_cnt = test["question_count"]
        deadline_text = test["deadline"].strftime('%d.%m.%Y %H:%M') if test["deadline"] else "Cheklovsiz"
        duration_text = f"{test['time_limit_minutes']} daqiqa" if test['time_limit_minutes'] > 0 else "Cheklovsiz"

        lines.append(
            f"📋 <b>{test['title']}</b> ({test['group_name']})\n"
            f"   Savollar: <b>{q_cnt} ta</b> | Vaqt: <b>{duration_text}</b> | Deadline: <b>{deadline_text}</b>\n"
        )

        for child in children:
            sub = sub_map.get((child.id, test["id"]))
            if sub:
                lines.append(f"   ✓ <i>{child.full_name} topshirgan: {sub.score}/{sub.total_questions} ball</i>\n")
            else:
                btn_text = f"▶️ Testni boshlash ({test['title']})"
                if len(children) > 1:
                    btn_text = f"▶️ {child.full_name}: {test['title']}"
                inline_keyboard_rows.append([
                    InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"start_test:{test['id']}:{child.id}"
                    )
                ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_rows) if inline_keyboard_rows else None
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=reply_markup or get_main_keyboard())


@dp.callback_query(lambda c: c.data and c.data.startswith("start_test:"))
async def process_start_test_callback(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    test_id = int(parts[1])
    child_id = int(parts[2])

    test, student, data = await load_test_details(test_id, child_id)
    if isinstance(data, str):
        await callback_query.answer()
        await callback_query.message.answer(data, parse_mode="HTML")
        return

    q_list, _ = data
    user_id = callback_query.from_user.id

    USER_TEST_SESSIONS[user_id] = {
        "test_id": test_id,
        "child_id": child_id,
        "current_index": 0,
        "questions": q_list,
        "score": 0,
        "responses": [],
    }

    await callback_query.answer()
    await send_next_question_message(callback_query.message, user_id)


async def send_next_question_message(message: Message, user_id: int):
    session = USER_TEST_SESSIONS.get(user_id)
    if not session:
        await message.answer("❌ Test sessiyasi topilmadi. Qaytadan /tests buyrug'ini yuboring.")
        return

    idx = session["current_index"]
    questions = session["questions"]

    if idx >= len(questions):
        score = session["score"]
        total_q = len(questions)
        student_id = session["child_id"]
        test_id = session["test_id"]
        responses = session.get("responses", [])

        res = await complete_test_submission(student_id, test_id, score, total_q)
        USER_TEST_SESSIONS.pop(user_id, None)

        if res:
            summary_lines = [
                f"🎉 <b>TEST YAKUNLANDI!</b>\n",
                f"📋 Test: <b>{res['test_title']}</b> ({res['group_name']})",
                f"👤 O'quvchi: <b>{res['student_full_name']}</b>\n",
                f"🎯 Natija: <b>{res['score']} / {res['total_questions']}</b> to'g'ri javob!",
                f"⭐ <b>+{res['score']} ball</b> umumiy ballingizga qo'shildi!\n",
                "----------------------------------------",
                "📊 <b>SAVOLLAR TAHLILI:</b>\n"
            ]

            for item in responses:
                if item["is_correct"]:
                    summary_lines.append(
                        f"<b>{item['question_num']}. {item['question_text']}</b>\n"
                        f"✅ Javobingiz: <i>{item['selected_text']}</i> (+1 ball)\n"
                    )
                else:
                    summary_lines.append(
                        f"<b>{item['question_num']}. {item['question_text']}</b>\n"
                        f"❌ Javobingiz: <i>{item['selected_text']}</i> (0 ball)\n"
                    )

            summary_lines.append("----------------------------------------")
            summary_lines.append(f"Joriy umumiy ballingiz: <b>{res['student_points']} ⭐</b>")
            summary_lines.append("📌 O'qituvchining veb-panelida natijangiz saqlandi.")

            res_text = "\n".join(summary_lines)
        else:
            res_text = f"✅ Test yakunlandi! Natijangiz: <b>{score}/{total_q}</b>"

        await message.answer(res_text, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    q = questions[idx]
    q_title = f"\n\n<b>{q['text']}</b>" if q['text'] else ""
    text = (
        f"📝 <b>Savol {idx + 1} / {len(questions)}:</b>{q_title}"
    )

    opt_labels = ["A", "B", "C", "D", "E", "F"]
    keyboard_rows = []
    for opt_i, opt in enumerate(q["options"]):
        lbl = opt_labels[opt_i] if opt_i < len(opt_labels) else str(opt_i + 1)
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{lbl}) {opt['text']}",
                callback_data=f"ans_q:{idx}:{opt['id']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    photo = None
    if q.get("image_path"):
        try:
            photo = FSInputFile(q["image_path"])
        except Exception:
            photo = None

    if not photo and q.get("image_url"):
        img_url = q["image_url"]
        photo = URLInputFile(img_url) if img_url.startswith("http") else img_url

    if photo:
        try:
            await message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"[Bot question photo send error]: {e}")
            await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


@dp.callback_query(lambda c: c.data and c.data.startswith("ans_q:"))
async def process_answer_callback(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    q_idx = int(parts[1])
    opt_id = int(parts[2])
    user_id = callback_query.from_user.id

    session = USER_TEST_SESSIONS.get(user_id)
    if not session or session["current_index"] != q_idx:
        await callback_query.answer("⚠️ Ushbu savolga allaqachon javob berilgan.")
        return

    q = session["questions"][q_idx]
    selected_opt = None
    correct_opt = None

    for opt in q["options"]:
        if opt["id"] == opt_id:
            selected_opt = opt
        if opt["is_correct"]:
            correct_opt = opt

    is_correct = bool(selected_opt and selected_opt["is_correct"])

    if is_correct:
        session["score"] += q["points"]

    session["responses"].append({
        "question_num": q_idx + 1,
        "question_text": q["text"] if q["text"] else f"Savol #{q_idx + 1}",
        "selected_text": selected_opt["text"] if selected_opt else "Javob berilmadi",
        "correct_text": correct_opt["text"] if correct_opt else "—",
        "is_correct": is_correct,
    })

    session["current_index"] += 1
    await callback_query.answer()
    await send_next_question_message(callback_query.message, user_id)


@dp.callback_query(lambda c: c.data and c.data.startswith("buy_item:"))
async def process_buy_callback(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    item_id = int(parts[1])
    child_id = int(parts[2])

    success, msg = await process_market_purchase(callback_query.from_user.id, item_id, child_id)
    await callback_query.answer()
    await callback_query.message.answer(msg, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Mavjud buyruqlar:</b>\n\n"
        "/start — Tizimga ulanish\n"
        "/id — Telegram ID-ingizni ko'rish\n"
        "/mystudents — Farzandlaringizni ko'rish\n"
        "/stats — 📊 Statistika ko'rish\n"
        "/tests — 📝 Testlar (Onlayn Imtihonlar)\n"
        "/market — 🛒 Do'kon (Gamification)\n"
        "/help — Yordam",
        parse_mode="HTML",
    )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name

    parent, created = await get_or_create_parent(telegram_id, full_name)

    if created:
        text = (
            "✅ <b>Tizimga muvaffaqiyatli ulandingiz!</b>\n\n"
            "Endi farzandingizning darsga qatnashishi, baholari va market xaridlari haqida "
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


@sync_to_async_db
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


@dp.message(or_f(Command("stats"), F.text == "📊 Statistika", F.text.contains("Statistika")))
async def cmd_stats(message: Message):
    parent, text = await get_stats_for_parent(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


# -- MARKET / DO'KON FUNCTIONS --

@sync_to_async_db
def get_market_data_for_parent(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        if not children:
            return None, [], [], "ℹ️ Hali farzand bog'lanmagan."
        items = list(MarketItem.objects.filter(is_active=True, quantity__gt=0).order_by("-created_at"))
        if not items:
            return parent, children, [], "🛒 Hozircha do'konda faol mahsulotlar yo'q."
        return parent, children, items, None
    except Parent.DoesNotExist:
        return None, [], [], "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n/start buyrug'ini yuboring."


@sync_to_async_db
def process_market_purchase(telegram_id, item_id, child_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        student = parent.children.filter(id=child_id).first()
        if not student:
            return False, "❌ Farzand topilmadi."

        with transaction.atomic():
            student = Student.objects.select_for_update().get(pk=student.id)
            item = MarketItem.objects.select_for_update().get(pk=item_id)

            if not item.is_active or item.quantity <= 0:
                return False, f"❌ Kechirasiz, '{item.title}' tugab qoldi."

            if student.total_points < item.points_cost:
                return False, f"❌ Yetarli ball yo'q!\n\nFarzandingizda: <b>{student.total_points} ⭐</b>\nMahsulot narxi: <b>{item.points_cost} ⭐</b>"

            # Deduct points & reduce stock quantity
            student.total_points -= item.points_cost
            student.save()

            item.quantity -= 1
            item.save()

            # Create market order
            MarketOrder.objects.create(
                student=student,
                item=item,
                points_spent=item.points_cost,
                status="pending"
            )

            # Create Performance record (logs deduction in points history)
            Performance.objects.create(
                student=student,
                teacher=item.teacher,
                points=-item.points_cost,
                comment=f"🛒 Do'kon xaridi: {item.title}",
                date=date.today()
            )

            success_msg = (
                f"🎉 <b>MUVAFFAQIYATLI XARID!</b>\n\n"
                f"Farzandingiz <b>{student.full_name}</b> "
                f"\"{item.title}\" mahsulotini <b>{item.points_cost} ⭐</b> ga xarid qildi!\n\n"
                f"⭐ Qolgan ballari: <b>{student.total_points} ⭐</b>\n\n"
                f"📌 O'qituvchiga (saytda) bildirishnoma yuborildi. Topshirilgach o'qituvchi holatni o'zgartiradi."
            )
            return True, success_msg
    except Exception as e:
        return False, f"❌ Xatolik yuz berdi: {str(e)}"


def get_full_image_url(item):
    url = item.get_image_display_url()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    domain = os.getenv("HOST_DOMAIN", "https://student-monitoring-production.up.railway.app")
    return f"{domain.rstrip('/')}{url}"


@dp.message(or_f(Command("market"), F.text == "🛒 Do'kon", F.text.contains("Do'kon")))
async def cmd_market(message: Message):
    parent, children, items, err = await get_market_data_for_parent(message.from_user.id)
    if err:
        await message.answer(err, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    summary_lines = ["🛒 <b>GAMIFICATION DO'KONI (MARKET)</b>\n"]
    for child in children:
        summary_lines.append(f"👤 <b>{child.full_name}</b>: {child.total_points} ⭐")
    summary_lines.append("\n🎁 <b>Mavjud Mahsulot va Chegirmalar:</b>")

    await message.answer("\n".join(summary_lines), parse_mode="HTML", reply_markup=get_main_keyboard())

    for item in items:
        icon = "🏷️" if item.item_type == "discount" else "📦"
        discount_info = f" ({item.discount_percent}% chegirma)" if item.discount_percent else ""
        desc = f"\n📝 <i>{item.description}</i>" if item.description else ""

        caption = (
            f"{icon} <b>{item.title}</b>{discount_info}\n"
            f"💰 Narxi: <b>{item.points_cost} ⭐</b> | Qoldiq: <b>{item.quantity} ta</b>{desc}"
        )

        inline_keyboard_rows = []
        for child in children:
            btn_text = f"🛒 Xarid qilish: {item.title} ({item.points_cost} ⭐)"
            if len(children) > 1:
                btn_text = f"🛒 {child.full_name}: {item.title} ({item.points_cost} ⭐)"
            inline_keyboard_rows.append([
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"buy_item:{item.id}:{child.id}"
                )
            ])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard_rows)

        photo = None
        if item.image:
            try:
                if os.path.exists(item.image.path):
                    photo = FSInputFile(item.image.path)
            except Exception:
                photo = None

        if not photo:
            image_url = get_full_image_url(item)
            if image_url:
                photo = URLInputFile(image_url) if image_url.startswith("http") else image_url

        if photo:
            try:
                await message.answer_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"[Bot image send error for {item.title}]: {e}")
                await message.answer(
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        else:
            await message.answer(
                text=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )



@dp.callback_query(lambda c: c.data and c.data.startswith("buy_item:"))
async def process_buy_callback(callback_query: CallbackQuery):
    parts = callback_query.data.split(":")
    item_id = int(parts[1])
    child_id = int(parts[2])

    success, msg = await process_market_purchase(callback_query.from_user.id, item_id, child_id)
    await callback_query.answer()
    await callback_query.message.answer(msg, parse_mode="HTML", reply_markup=get_main_keyboard())


@sync_to_async_db
def get_group_leaderboard_for_parent(telegram_id):
    try:
        parent = Parent.objects.get(telegram_id=telegram_id)
        children = list(parent.children.all())
        if not children:
            return None, "ℹ️ Hali farzand bog'lanmagan."

        child_ids = set(c.id for c in children)
        memberships = GroupMembership.objects.filter(student__in=children).select_related("group")
        if not memberships.exists():
            return parent, "ℹ️ Farzandlaringiz hali biror guruhga biriktirilmagan."

        groups = list(set(m.group for m in memberships))
        response_lines = ["🏆 <b>GURUH REYTINGI (LEADERBOARD)</b>\n"]

        for group in groups:
            response_lines.append(f"👥 <b>Guruh: {group.name}</b> ({group.subject})")

            group_members = list(
                GroupMembership.objects.filter(group=group)
                .select_related("student")
                .order_by("-student__total_points", "student__full_name")
            )

            if not group_members:
                response_lines.append("   <i>Guruhda o'quvchilar yo'q</i>\n")
                continue

            for rank_idx, m in enumerate(group_members, start=1):
                st = m.student
                is_my_child = st.id in child_ids

                if rank_idx == 1:
                    rank_icon = "🥇"
                elif rank_idx == 2:
                    rank_icon = "🥈"
                elif rank_idx == 3:
                    rank_icon = "🥉"
                else:
                    rank_icon = f"<b>#{rank_idx}</b>"

                my_tag = " 👈 <b>(Siz)</b>" if is_my_child else ""

                if is_my_child:
                    response_lines.append(
                        f"{rank_icon} <b>{st.full_name}</b> — <b>{st.total_points} ⭐</b>{my_tag}"
                    )
                else:
                    response_lines.append(
                        f"{rank_icon} {st.full_name} — <b>{st.total_points} ⭐</b>"
                    )

            response_lines.append("")

        response_lines.append("📌 <i>Yuqoriroq o'ringa ko'tarilish uchun darslarda faol bo'ling va testlarni topshiring!</i>")
        return parent, "\n".join(response_lines)

    except Parent.DoesNotExist:
        return None, "❌ Siz tizimda ro'yxatdan o'tmagansiz.\n/start buyrug'ini yuboring."


@dp.message(or_f(Command("rating"), Command("leaderboard"), F.text == "🏆 Reyting", F.text.contains("Reyting")))
async def cmd_rating(message: Message):
    parent, text = await get_group_leaderboard_for_parent(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Mavjud buyruqlar:</b>\n\n"
        "/start — Tizimga ulanish\n"
        "/id — Telegram ID-ingizni ko'rish\n"
        "/mystudents — Farzandlaringizni ko'rish\n"
        "/tests — 📝 Testlar (Onlayn Imtihonlar)\n"
        "/rating — 🏆 Guruh Reytingi (Leaderboard)\n"
        "/stats — 📊 Statistika ko'rish\n"
        "/market — 🛒 Do'kon (Gamification)\n"
        "/help — Yordam",
        parse_mode="HTML",
    )


async def main():
    while True:
        try:
            print("🤖 Bot ishga tushdi...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        except Exception as e:
            print(f"Bot crashed: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

