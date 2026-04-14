from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from students.models import Group, Schedule, GroupMembership, Student


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
