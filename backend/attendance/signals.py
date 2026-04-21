from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Attendance, Performance
import threading


def _notify(telegram_id, text):
    try:
        import asyncio
        from notifications.services import send_message
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_message(telegram_id, text))
        loop.close()
    except Exception as e:
        print(f"[Notification error] {e}")


@receiver(post_save, sender=Attendance)
def send_attendance_notification(sender, instance, created, **kwargs):
    if not created:
        return
    student = instance.student
    parent = student.parent
    if not parent or not parent.telegram_id:
        return

    group = instance.group
    schedules = group.schedules.all()
    start = schedules[0].start_time.strftime("%H:%M") if schedules else "—"
    end = schedules[0].end_time.strftime("%H:%M") if schedules else "—"

    months_uz = {
        1:"Yanvar",2:"Fevral",3:"Mart",4:"Aprel",
        5:"May",6:"Iyun",7:"Iyul",8:"Avgust",
        9:"Sentabr",10:"Oktabr",11:"Noyabr",12:"Dekabr",
    }
    date_str = f"{instance.date.day}-{months_uz[instance.date.month]} {instance.date.year}"
    teacher_name = group.teacher.full_name or group.teacher.user.username

    if instance.status == "present":
        emoji = "🟢"
        action = "qatnashdi"
        extra = f"Dars {start} - {end} oralig'ida o'tkazildi.\n\nBiz sizning farzandingizning bilim olishdagi qat'iyatini va ishtiyoqini yuqori baholaymiz."
    elif instance.status == "late":
        emoji = "🟡"
        action = "kechikib keldi"
        extra = f"Dars {start} - {end} oralig'ida o'tkazildi."
    else:
        emoji = "🔴"
        action = "qatnashmadi"
        extra = "Iltimos, sababini o'qituvchi bilan muhokama qiling."

    text = (
        f"{emoji} Hurmatli {parent.full_name.upper()},\n\n"
        f"Farzandingiz {student.full_name}\n"
        f"📚 {group.name} kursidan\n"
        f"📅 {date_str} sanasidagi darsga {action}.\n"
        f"⏰ {extra}\n\n"
        f"Hurmat bilan,\n"
        f"Fan mentori {teacher_name}"
    )

    threading.Thread(target=_notify, args=(parent.telegram_id, text), daemon=True).start()


@receiver(post_save, sender=Performance)
def send_points_notification(sender, instance, created, **kwargs):
    if not created:
        return
    student = instance.student
    parent = student.parent
    if not parent or not parent.telegram_id:
        return

    teacher_name = instance.teacher.full_name if instance.teacher else "O'qituvchi"
    comment_line = f"\n💬 Sabab: {instance.comment}" if instance.comment else ""

    if instance.points >= 0:
        # Points awarded
        text = (
            f"⭐ Hurmatli {parent.full_name.upper()},\n\n"
            f"Farzandingiz <b>{student.full_name}</b>\n"
            f"📅 {instance.date} sanasida\n"
            f"🏆 <b>+{instance.points} ball</b> oldi!{comment_line}\n\n"
            f"Jami ball: <b>{student.total_points}</b> ⭐\n\n"
            f"Hurmat bilan,\n"
            f"Fan mentori {teacher_name}"
        )
    else:
        # Points deducted
        deducted = abs(instance.points)
        text = (
            f"❌ Hurmatli {parent.full_name.upper()},\n\n"
            f"Farzandingiz <b>{student.full_name}</b>\n"
            f"📅 {instance.date} sanasida\n"
            f"<b>−{deducted} ball</b> ayirildi.{comment_line}\n\n"
            f"Joriy jami ball: <b>{student.total_points}</b> ⭐\n\n"
            f"Hurmat bilan,\n"
            f"Fan mentori {teacher_name}"
        )

    threading.Thread(target=_notify, args=(parent.telegram_id, text), daemon=True).start()