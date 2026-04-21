import threading

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from students.models import Student, GroupMembership
from students.services.stats import student_summary, get_period_range
from users.models import Parent
from datetime import date

def _send_linked_notification(telegram_id, student_name):
    try:
        import asyncio
        from notifications.services import send_message
        text = (
            f"✅ <b>Muvaffaqiyatli bog'landi!</b>\n\n"
            f"Siz <b>{student_name}</b> ning ota-onasi sifatida tizimga ulangansiz.\n\n"
            f"Endi quyidagi xabarnomalarni olasiz:\n"
            f"📋 Davomat — darsga qatnashganda\n"
            f"⭐ Ballar — o'qituvchi ball berganda\n\n"
            f"Farzandingiz muvaffaqiyatlarini kuzatib boring! 🎓"
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_message(telegram_id, text))
        loop.close()
    except Exception as e:
        print(f"[Link notification error] {e}")

@login_required
def students_list(request):
    teacher = request.user.teacher
    memberships = GroupMembership.objects.filter(
        group__teacher=teacher
    ).select_related("student__parent").order_by("student__full_name")
    seen = set()
    students = []
    for m in memberships:
        if m.student.id not in seen:
            seen.add(m.student.id)
            students.append(m.student)
    return render(request, "students/list.html", {"students": students})


@login_required
def student_create(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        Student.objects.create(full_name=full_name, parent=None)
        return redirect("students_list")
    return render(request, "students/create.html")


@login_required
def student_detail(request, student_id):
    from attendance.models import Attendance, Performance
    student = get_object_or_404(Student, id=student_id)
    attendances = Attendance.objects.filter(student=student).order_by("-date")[:20]
    performances = Performance.objects.filter(student=student).order_by("-date")[:20]

    # Personal stats for detail page
    def _stats(period):
        s, e = get_period_range(period)
        return student_summary(student, s, e)

    return render(request, "students/detail.html", {
        "student": student,
        "attendances": attendances,
        "performances": performances,
        "weekly_stats": _stats("weekly"),
        "monthly_stats": _stats("monthly"),
        "overall_stats": _stats("overall"),
    })


@login_required
def student_edit(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    error = None

    if request.method == "POST":
        student.full_name = request.POST.get("full_name")
        student.save()

        if student.parent:
            student.parent.full_name = request.POST.get("parent_name", "")
            student.parent.phone = request.POST.get("parent_phone", "")

            telegram_id_raw = request.POST.get("telegram_id", "").strip()
            if telegram_id_raw:
                try:
                    telegram_id = int(telegram_id_raw)
                    conflict = Parent.objects.filter(
                        telegram_id=telegram_id
                    ).exclude(id=student.parent.id).first()
                    if conflict:
                        error = f"This Telegram ID is already linked to: {conflict.full_name}"
                    else:
                        student.parent.telegram_id = telegram_id
                except ValueError:
                    error = "Telegram ID must be a number only"

            if not error:
                # Notify parent that they are now linked
                threading.Thread(
                    target=_send_linked_notification,
                    args=(telegram_id, student.full_name),
                    daemon=True
                ).start()
                student.parent.save()
                return redirect("student_detail", student_id=student.id)
        else:
            return redirect("student_detail", student_id=student.id)

    return render(request, "students/edit.html", {"student": student, "error": error})

@login_required
def student_delete(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == "POST":
        student.delete()
        return redirect("students_list")
    return render(request, "students/confirm_delete.html", {"student": student})


@login_required
def give_points(request, student_id):
    from attendance.models import Performance
    student = get_object_or_404(Student, id=student_id)
    if request.method == "POST":
        points = int(request.POST.get("points", 0))
        comment = request.POST.get("comment", "")

        # Update total_points FIRST before creating Performance
        student.total_points += points
        student.save()

        # Create Performance after save so signal reads correct total
        Performance.objects.create(
            student=student,
            points=points,
            comment=comment,
            date=date.today(),
            teacher=request.user.teacher,
        )
        return redirect("student_detail", student_id=student.id)
    return render(request, "students/give_points.html", {"student": student})


@login_required
def deduct_points(request, student_id):
    """Subtract points from a student (clamped to 0). Telegram notification fires via signal."""
    from attendance.models import Performance
    student = get_object_or_404(Student, id=student_id)
    error = None
    if request.method == "POST":
        try:
            amount = int(request.POST.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0
        comment = request.POST.get("comment", "").strip()
        if amount <= 0:
            error = "Ayiriladigan ball musbat son bo'lishi kerak."
        else:
            with transaction.atomic():
                # Re-fetch with row lock for concurrency safety
                student = Student.objects.select_for_update().get(pk=student_id)
                actual_deduction = min(amount, student.total_points)  # clamp to 0
                student.total_points -= actual_deduction
                student.save(update_fields=["total_points"])
                # Negative Performance record triggers existing signal → Telegram notification
                Performance.objects.create(
                    student=student,
                    points=-actual_deduction,
                    comment=comment,
                    date=date.today(),
                    teacher=request.user.teacher,
                )
            return redirect("student_detail", student_id=student.id)
    return render(request, "students/deduct_points.html", {"student": student, "error": error})
