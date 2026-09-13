web: python backend/manage.py migrate --noinput && (python backend/bot/bot.py &) && gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:$PORT

