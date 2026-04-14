from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from students.models import Group, GroupMembership
from .models import Attendance
from datetime import date


@login_required
def take_attendance(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    memberships = GroupMembership.objects.filter(group=group).select_related("student__parent")
    students = [m.student for m in memberships]
    today = date.today()

    # Check if attendance already taken today
    existing = Attendance.objects.filter(group=group, date=today)
    existing_map = {a.student_id: a.status for a in existing}

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"student_{student.id}", "absent")
            obj, created = Attendance.objects.update_or_create(
                student=student,
                group=group,
                date=today,
                defaults={"status": status},
            )
            # Signal fires on create only; manually trigger notification on update too
            if not created:
                from attendance.signals import send_attendance_notification
                send_attendance_notification(Attendance, obj, created=False, update_fields=None)

        return redirect("group_detail", group_id=group_id)

    return render(request, "attendance/take.html", {
        "group": group,
        "students": students,
        "today": today,
        "existing_map": existing_map,
    })


@login_required
def attendance_history(request, group_id):
    group = get_object_or_404(Group, id=group_id, teacher=request.user.teacher)
    records = Attendance.objects.filter(group=group).select_related("student").order_by("-date", "student__full_name")

    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for r in records:
        by_date[r.date].append(r)

    dates = sorted(by_date.keys(), reverse=True)[:30]
    history = [(d, by_date[d]) for d in dates]

    return render(request, "attendance/history.html", {
        "group": group,
        "history": history,
    })
