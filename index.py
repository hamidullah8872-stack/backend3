# index.py
import os
import sys
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# Add path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_backend.settings')

# Entry point for Vercel
application = get_wsgi_application()

# 🚀 Self-Repair: Run migrations on startup to create missing tables (Timetable, Announcements)
try:
    print("[Vercel Startup] Running database migrations...")
    call_command('migrate', '--noinput')
    print("[Vercel Startup] Migrations complete.")
except Exception as e:
    print(f"[Vercel Startup] Migration Error: {e}")

app = application
