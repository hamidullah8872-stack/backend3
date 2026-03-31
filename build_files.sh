#!/bin/bash

echo "BUILD START"

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create static directory explicitly
mkdir -p staticfiles_build
touch staticfiles_build/placeholder.txt

# Collect static files
python manage.py collectstatic --noinput --clear || echo "collectstatic failed, but directory exists"

echo "BUILD END"
