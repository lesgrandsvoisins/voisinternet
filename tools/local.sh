#!/bin/sh
if [ -f ".env" ] && [ -d "./core" ] && [ -d "./voisinternet" ]; then
  eval "$(grep -v '^\#\|^ *\t*$' .env 2>/dev/null)"
  pyexec=./.venv/bin/python
  eval "$pyexec manage.py makemigrations"
  eval "$pyexec manage.py migrate"
  eval "$pyexec manage.py collectstatic --noinput"
  eval "$pyexec manage.py runserver $DJANGO_IP:$DJANGO_PORT"
else
  echo "Please execute from root directory of application with .venv from python -m venv .venv"
fi 