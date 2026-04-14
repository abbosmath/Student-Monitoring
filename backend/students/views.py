from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Group, Schedule, GroupMembership, Student
from users.models import Parent
from datetime import date


# ─── GROUPS ──────────────────────────────────────────────

@login_required
def groups_list(request):
    teacher = request.user.teacher
    groups = Group.objects.filter(teacher=teacher).prefetch_related("schedules", "memberships")
    return render(request, "groups/list.html", {"groups": groups})


@login_required
def group_create(request):
    if request.method == "POST":
        name = request.POST.get("name")
        subject = request.POST.get("subject", "")
        group = Group.objects.create(name=name, subject=subject, teacher=request.user.teacher)
        days = request.POST.getlist("day")
        starts = request.POST.getlist("start_time")
        ends = request.POST.getlist("end_time")
        for day, start, end in zip(days, starts, ends):
            if day and start and end:
                Schedule.objects.create(group=group, day_of_week=int(day), start_time=start, end_time=end)
        return redirect("groups_list")
    return render(request, "groups/create.html")


@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    memberships = group.memberships.select_related("student__parent")
    all_students = Student.objects.exclude(memberships__group=group)
    return render(request, "groups/detail.html", {
        "group": group,
        "memberships": memberships,
        "all_students": all_students,
    })


@login_required
def group_edit(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    if request.method == "POST":
        group.name = request.POST.get("name")
        group.subject = request.POST.get("subject", "")
        group.save()
        group.schedules.all().delete()
        days = request.POST.getlist("day")
        starts = request.POST.getlist("start_time")
        ends = request.POST.getlist("end_time")
        for day, start, end in zip(days, starts, ends):
            if day and start and end:
                Schedule.objects.create(group=group, day_of_week=int(day), start_time=start, end_time=end)
        return redirect("group_detail", group_id=group.id)
    return render(request, "groups/edit.html", {"group": group})


@login_required
def group_delete(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    if request.method == "POST":
        group.delete()
        return redirect("groups_list")
    return render(request, "groups/confirm_delete.html", {"group": group})


@login_required
def add_student_to_group(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    if request.method == "POST":
        student_id = request.POST.get("student_id")
        student = get_object_or_404(Student, id=student_id)
        GroupMembership.objects.get_or_create(group=group, student=student)
    return redirect("group_detail", group_id=group_id)


@login_required
def remove_student_from_group(request, group_id, student_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    if request.method == "POST":
        GroupMembership.objects.filter(group=group, student_id=student_id).delete()
    return redirect("group_detail", group_id=group_id)


# ─── STUDENTS ────────────────────────────────────────────

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
        parent_name = request.POST.get("parent_name", "")
        parent_phone = request.POST.get("parent_phone", "")
        parent = Parent.objects.create(full_name=parent_name, phone=parent_phone)
        Student.objects.create(full_name=full_name, parent=parent)
        return redirect("students_list")
    return render(request, "students/create.html")


@login_required
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    from attendance.models import Attendance, Performance
    attendances = Attendance.objects.filter(student=student).order_by("-date")[:20]
    performances = Performance.objects.filter(student=student).order_by("-date")[:20]
    return render(request, "students/detail.html", {
        "student": student,
        "attendances": attendances,
        "performances": performances,
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
                    error = "Telegram ID must be a number only (e.g. 123456789)"
            elif request.POST.get("clear_telegram"):
                student.parent.telegram_id = None

            if not error:
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
    student = get_object_or_404(Student, id=student_id)
    if request.method == "POST":
        from attendance.models import Performance
        points = int(request.POST.get("points", 0))
        comment = request.POST.get("comment", "")
        Performance.objects.create(
            student=student,
            points=points,
            comment=comment,
            date=date.today(),
            teacher=request.user.teacher,
        )
        student.total_points += points
        student.save()
        return redirect("student_detail", student_id=student.id)
    return render(request, "students/give_points.html", {"student": student})
