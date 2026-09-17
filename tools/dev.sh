#!/bin/sh
if [ -f ".env" ]; then
  eval "$(grep -v '^\#\|^ *\t*$' .env 2>/dev/null)"
  echo "Using .env"
else
  echo "no .env"
fi
DJANGO_USER="voisinter-django"
DJANGO_GROUP="services"
DJANGO_ROOT="/home/voisinter-django/voisinter-dev"

sudo -u $DJANGO_USER -g $DJANGO_GROUP make -C $DJANGO_ROOT production
sudo -u $DJANGO_USER -g $DJANGO_GROUP make -C $DJANGO_ROOT run