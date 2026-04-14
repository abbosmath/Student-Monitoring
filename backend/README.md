# EduTrack — Student Monitoring System

A Django web app + Telegram bot for tracking student attendance and performance.

## Features
- Teacher dashboard: CRUD for groups, students, schedules
- One-click attendance with Present / Absent / Late
- Points system — teacher gives points with comments
- Instant Telegram notifications to parents when attendance is saved
- Parents link via bot `/start` command

---

## Local Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your BOT_TOKEN

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal run the bot:
```bash
python bot/bot.py
```

---

## Linking a Parent to a Student

1. Parent sends `/start` to your bot → they get their Telegram ID
2. Parent gives teacher their ID
3. Teacher goes to **Admin panel** → `Users → Parents` → sets `telegram_id`
4. Or teacher edits the student page — it shows a link to Admin

---

## Railway Deployment

1. Push this `backend/` folder to a GitHub repo
2. In Railway: **New Project → Deploy from GitHub**
3. Add a **PostgreSQL** plugin
4. Set environment variables:
   - `SECRET_KEY` — a long random string
   - `BOT_TOKEN` — from @BotFather
   - `DEBUG` — `False`
   - `ALLOWED_HOSTS` — `yourapp.up.railway.app`
   - `DATABASE_URL` — auto-set by Railway PostgreSQL plugin
5. Railway will run migrations and start gunicorn automatically

### Running the bot on Railway
Add a second service in Railway pointing to the same repo, with start command:
```
python bot/bot.py
```
Or use the `Procfile` — Railway will detect both `web` and `bot` processes.

---

## Project Structure

```
backend/
├── config/          # Django settings, urls, wsgi
├── users/           # Teacher & Parent models, auth views
├── students/        # Group, Student, Schedule, GroupMembership
├── attendance/      # Attendance & Performance models + signals
├── notifications/   # Telegram sender service + webhook view
├── bot/             # Standalone aiogram bot process
├── templates/       # All HTML templates
├── Procfile         # Railway process definitions
├── railway.json     # Railway build config
└── requirements.txt
```

---

## Telegram Message Format

```
🟢 Hurmatli RAVSHAN AXMADALIYEV,

Farzandingiz Abdulaziz Ravshanovich
📚 Level 5 | Application development fanidan
📅 12-Aprel 2026 sanasidagi darsga qatnashdi.
⏰ Dars 12:00 - 13:20 oralig'ida o'tkazildi.

Biz sizning bilim olishdagi qat'iyatingiz va ishtiyoqingizni yuqori baholaymiz.

Hurmat bilan,
Fan mentori Javohir Fayzullayev
```
