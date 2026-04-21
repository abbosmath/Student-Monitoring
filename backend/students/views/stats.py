from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from students.models import Group
from students.services.stats import group_leaderboard, all_groups_leaderboard

PERIODS = ["monthly", "weekly", "overall"]
PERIOD_LABELS = {"monthly": "Oylik", "weekly": "Haftalik", "overall": "Umumiy"}


@login_required
def stats_overview(request):
    """Teacher: leaderboard across ALL their groups."""
    teacher = request.user.teacher
    period = request.GET.get("period", "monthly")
    if period not in PERIODS:
        period = "monthly"

    rows = all_groups_leaderboard(teacher, period)
    groups = Group.objects.filter(teacher=teacher)

    return render(request, "stats/overview.html", {
        "rows": rows,
        "period": period,
        "period_label": PERIOD_LABELS[period],
        "periods": PERIODS,
        "period_labels": PERIOD_LABELS,
        "groups": groups,
    })


@login_required
def stats_group(request, group_id):
    """Teacher: leaderboard inside a specific group."""
    teacher = request.user.teacher
    group = get_object_or_404(Group, id=group_id, teacher=teacher)
    period = request.GET.get("period", "monthly")
    if period not in PERIODS:
        period = "monthly"

    rows = group_leaderboard(group, period)
    groups = Group.objects.filter(teacher=teacher)

    return render(request, "stats/group.html", {
        "group": group,
        "rows": rows,
        "period": period,
        "period_label": PERIOD_LABELS[period],
        "periods": PERIODS,
        "period_labels": PERIOD_LABELS,
        "groups": groups,
    })
