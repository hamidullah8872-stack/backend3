#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Running migrations..."
python manage.py migrate --noinput
echo "Build complete."
