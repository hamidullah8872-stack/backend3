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

        try:
            # Log identifying headers for debugging (visible in server logs)
            config = getattr(request, 'school_config', {})
            print(f"[LoginView] Attempt: '{identifier}' (School: {config.get('school_id')})")
            
            identifier = identifier.strip()
            # 1. Standard Django authenticate
            user = authenticate(username=identifier, password=password)
            
            # 2. Manual fallback with diagnostics
            if not user:
                print(f"[LoginView] Standard authenticate failed for {identifier}. Trying manual check...")
                try:
                    user_obj = User.objects.get(username=identifier)
                    pwd_ok = user_obj.check_password(password)
                    print(f"[LoginView] Found user {user_obj.username}. Active: {user_obj.is_active}. Pwd matches: {pwd_ok}")
                    if user_obj.is_active and pwd_ok:
                        user = user_obj
                except User.DoesNotExist:
                    print(f"[LoginView] User '{identifier}' not found in Cloud database.")

            if user:
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
                        "role": "admin" if (user.is_staff or user.is_superuser) else "teacher",
                        "phone": identifier if identifier.isdigit() else "",
                        "manager_access": user.is_superuser
                    }
                }, status=status.HTTP_200_OK)

        except Exception as e:
            error_msg = str(e)
            print(f"[LoginView] CRITICAL ERROR during authenticate: {error_msg}")
            return Response(
                {"status": "error", "message": f"Server Error during login: {error_msg}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"status": "error", "message": "Invalid password or username"},
            status=status.HTTP_401_UNAUTHORIZED
        )
