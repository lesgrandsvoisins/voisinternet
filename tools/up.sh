#!/bin/sh
if [ -f ".env" ]; then
  eval "$(grep -v '^\#\|^ *\t*$' .env 2>/dev/null)"
  echo "Using .env"
else
  echo "no .env"
fi
DJANGO_USER="voisinger-django"
DJANGO_GROUP="services"
DJANGO_ROOT="/var/voisinter/voisinter"

sudo -u $DJANGO_USER -g $DJANGO_GROUP make -C $DJANGO_ROOT production
sudo systemctl restart voisinter-django.service