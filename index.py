# index.py
import os
import sys
from django.core.wsgi import get_wsgi_application

# Add path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_backend.settings')

# Entry point for Vercel
application = get_wsgi_application()
app = application
