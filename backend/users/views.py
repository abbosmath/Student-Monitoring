from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Teacher


def login_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("/groups/")
        error = "Invalid username or password"
    return render(request, "auth/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("/auth/login/")


def register_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        full_name = request.POST.get("full_name")
        subject = request.POST.get("subject", "")

        if User.objects.filter(username=username).exists():
            error = "Username already taken"
        else:
            user = User.objects.create_user(username=username, password=password)
            Teacher.objects.create(user=user, full_name=full_name, subject=subject)
            login(request, user)
            return redirect("/groups/")
    return render(request, "auth/register.html", {"error": error})
