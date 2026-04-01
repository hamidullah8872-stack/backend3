from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from django.conf import settings
from rest_framework.permissions import AllowAny

class DbDebugView(APIView):
    permission_classes = [AllowAny]
    """
    Diagnostic endpoint to check database connection, 
    engine, and required tables.
    """
    def get(self, request):
        debug_info = {
            "database_url_present": bool(os.environ.get('DATABASE_URL')),
            "database_engine": settings.DATABASES['default'].get('ENGINE'),
            "tables": [],
            "error": None
        }

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                tables = [row[0] for row in cursor.fetchall()]
                debug_info["tables"] = tables
        except Exception as e:
            # Fallback for sqlite3 if postgres fails
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    debug_info["tables"] = tables
                    debug_info["error"] = f"Postgres check failed, Sqlite check: {str(e)}"
            except Exception as e2:
                debug_info["error"] = f"Database diagnostic failed: {str(e)} | {str(e2)}"

        return Response(debug_info)
