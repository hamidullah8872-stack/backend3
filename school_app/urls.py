from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StudentViewSet,
    SectionViewSet,
    AttendanceViewSet,
    FeeLedgerViewSet,
    ExamViewSet,
    MarkViewSet,
    TeacherMonthlyAttendanceHistoryView,
    SchoolInfoView,
    SchoolLogoView,
)
from .views_auth import LoginView

router = DefaultRouter()
router.register(r'students', StudentViewSet)
router.register(r'sections', SectionViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'fee_ledgers', FeeLedgerViewSet)
router.register(r'exams', ExamViewSet)
router.register(r'marks', MarkViewSet)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('school/info/', SchoolInfoView.as_view(), name='school_info'),
    path('school/logo/', SchoolLogoView.as_view(), name='school_logo'),
    path('teachers/<int:teacher_id>/monthly-attendance-history/', TeacherMonthlyAttendanceHistoryView.as_view()),
    path('', include(router.urls)),
]
