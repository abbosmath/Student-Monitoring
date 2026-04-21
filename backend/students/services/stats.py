"""
Statistics calculation helpers.
All stats are computed dynamically from existing Performance and Attendance records.
No new DB tables; no migrations required.
"""
from datetime import date, timedelta
from django.db.models import Sum, Q
from attendance.models import Performance, Attendance
from students.models import Group, GroupMembership, Student


def get_period_range(period: str):
    """Return (start_date, end_date) tuple. start_date is None for 'overall'."""
    today = date.today()
    if period == "weekly":
        return today - timedelta(days=6), today
    elif period == "monthly":
        return today.replace(day=1), today
    else:  # overall
        return None, today


def student_summary(student, start, end):
    """
    Return a dict with aggregated stats for one student within [start, end].
    If start is None, no lower-bound date filter is applied (overall).
    """
    perf_qs = Performance.objects.filter(student=student)
    att_qs = Attendance.objects.filter(student=student)

    if start:
        perf_qs = perf_qs.filter(date__gte=start)
        att_qs = att_qs.filter(date__gte=start)
    if end:
        perf_qs = perf_qs.filter(date__lte=end)
        att_qs = att_qs.filter(date__lte=end)

    points = perf_qs.aggregate(total=Sum("points"))["total"] or 0
    present = att_qs.filter(status="present").count()
    late = att_qs.filter(status="late").count()
    absent = att_qs.filter(status="absent").count()

    return {
        "points": points,
        "present": present,
        "late": late,
        "absent": absent,
        "total_sessions": present + late + absent,
    }


def group_leaderboard(group, period: str):
    """
    Return a list of dicts sorted by points desc (within the period) for one group.
    Each dict: {student, points, present, late, absent, rank}
    """
    start, end = get_period_range(period)
    memberships = GroupMembership.objects.filter(group=group).select_related("student__parent")
    rows = []
    for m in memberships:
        s = m.student
        summary = student_summary(s, start, end)
        rows.append({"student": s, **summary})

    rows.sort(key=lambda r: r["points"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def all_groups_leaderboard(teacher, period: str):
    """
    Return a flat leaderboard across ALL groups of a teacher, deduplicating students.
    Each dict: {student, points, present, late, absent, rank, groups}
    """
    start, end = get_period_range(period)
    groups = Group.objects.filter(teacher=teacher)
    memberships = GroupMembership.objects.filter(group__in=groups).select_related(
        "student__parent", "group"
    )

    # Collect unique students + their group names
    student_groups: dict[int, list] = {}
    student_objs: dict[int, Student] = {}
    for m in memberships:
        sid = m.student.id
        student_objs[sid] = m.student
        student_groups.setdefault(sid, []).append(m.group.name)

    rows = []
    for sid, student in student_objs.items():
        summary = student_summary(student, start, end)
        rows.append({
            "student": student,
            **summary,
            "groups": ", ".join(student_groups[sid]),
        })

    rows.sort(key=lambda r: r["points"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def student_rank_in_group(student, group, period: str) -> int | None:
    """Return rank (1-based) of a student in their group for the given period."""
    rows = group_leaderboard(group, period)
    for row in rows:
        if row["student"].id == student.id:
            return row["rank"]
    return None
