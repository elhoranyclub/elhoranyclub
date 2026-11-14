web: gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings.prod --workers 3 --bind 0.0.0.0:$PORT --timeout 60 --access-logfile -
release: python manage.py migrate --noinput --settings=config.settings.prod && python manage.py collectstatic --noinput --settings=config.settings.prod
