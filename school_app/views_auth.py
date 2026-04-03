from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .middleware import get_current_school_config

class LoginView(APIView):
    """
    Handles teacher and parent login. 
    Expects 'phone' or 'username' and 'password' in the body.
    Processes multi-tenancy headers via middleware.
    """
    def post(self, request):
        data = request.data
        identifier = data.get('phone') or data.get('username')
        password = data.get('password')

        if not identifier or not password:
            return Response(
                {"status": "error", "message": "Missing credentials"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log identifying headers for debugging (visible in server logs)
        config = getattr(request, 'school_config', {})
        print(f"[LoginView] Login attempt for '{identifier}' with School ID: {config.get('school_id')}")

        try:
            # In a real multi-tenant scenario, you'd switch databases or Supabase instances here 
            # using the values in `config`. 
            # For now, we authenticate against the local Django users.
            
            # Try finding by username first, then by email (if phone is stored in email or similar workaround)
            user = authenticate(username=identifier, password=password)
            
            if not user:
                # Fallback: check if identifier matches a phone number (if we have a profile)
                # Since we don't have a profile model yet, we try to match username exactly
                try:
                    user_obj = User.objects.get(username=identifier)
                    if user_obj.check_password(password):
                        user = user_obj
                except User.DoesNotExist:
                    pass

                # Prepare standard response matching mobile app expectations
                # Convention: School ID is the first 6 digits of the phone/username or '123456'
                school_id = identifier[:6] if identifier and identifier.isdigit() else "123456"
                
                return Response({
                    "status": "success",
                    "school_id": school_id,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.first_name,
                        "role": "admin" if user.is_staff else "teacher",
                        "phone": identifier if identifier.isdigit() else "",
                        "manager_access": user.is_superuser
                    }
                }, status=status.HTTP_200_OK)

        except Exception as e:
            error_msg = str(e)
            print(f"[LoginView] CRITICAL ERROR during authenticate: {error_msg}")
            
            detail = ""
            if "failed to resolve host" in error_msg:
                detail = " (DNS issues detected. Check your DATABASE_URL in Vercel settings.)"
            elif "Device or resource busy" in error_msg:
                detail = " (Resource busy error sometimes indicates a problem with Python's DNS resolver on Vercel. Try using a Supabase Pooler URL.)"

            return Response(
                {"status": "error", "message": f"Server Error during login: {error_msg}{detail}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"status": "error", "message": "Invalid password or username"},
            status=status.HTTP_401_UNAUTHORIZED
        )
