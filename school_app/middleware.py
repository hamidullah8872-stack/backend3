import threading

_thread_local = threading.local()

def get_current_school_config():
    """ Returns a dict with school_id, supabase_url, supabase_key from current request context. """
    return getattr(_thread_local, 'school_config', {})

class MultiTenancyMiddleware:
    """
    Middleware that extracts x-school-id, x-supabase-url, and x-supabase-key headers 
    and stores them in thread-local storage for use during the request lifecycle.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # Extract headers (Django converts headers like 'x-school-id' to 'HTTP_X_SCHOOL_ID')
            school_id = request.META.get('HTTP_X_SCHOOL_ID')
            supabase_url = request.META.get('HTTP_X_SUPABASE_URL')
            supabase_key = request.META.get('HTTP_X_SUPABASE_KEY')

            # Store in thread-local
            _thread_local.school_config = {
                'school_id': school_id,
                'supabase_url': supabase_url,
                'supabase_key': supabase_key,
            }

            # Also attach to request object for easy access in views
            request.school_config = _thread_local.school_config
        except Exception as e:
            print(f"[MultiTenancyMiddleware] ERROR: {e}")
            request.school_config = {}

        response = self.get_response(request)

        # Cleanup after request
        if hasattr(_thread_local, 'school_config'):
            try:
                del _thread_local.school_config
            except AttributeError:
                pass

        return response
