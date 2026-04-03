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
    SyncDataView,
    TimetableViewSet,
    AnnouncementViewSet,
    AllSectionsView,
    TeacherAssignmentsView,
    StudentFeeHistoryView,
    PayFeeView,
)
from .views_auth import LoginView
from .debug_views import DbDebugView

router = DefaultRouter()
router.register(r'students', StudentViewSet)
router.register(r'sections', SectionViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'fee_ledgers', FeeLedgerViewSet)
router.register(r'exams', ExamViewSet)
router.register(r'marks', MarkViewSet)
router.register(r'timetable', TimetableViewSet)
router.register(r'announcements', AnnouncementViewSet)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('school/info/', SchoolInfoView.as_view(), name='school_info'),
    path('school/logo/', SchoolLogoView.as_view(), name='school_logo'),
    path('db-debug/', DbDebugView.as_view(), name='db_debug'),
    path('sync/', SyncDataView.as_view(), name='sync_data'),
    path('all-sections/', AllSectionsView.as_view(), name='all_sections'),
    path('teacher/<int:teacher_id>/assignments/', TeacherAssignmentsView.as_view(), name='teacher_assignments'),
    path('teachers/<int:teacher_id>/monthly-attendance-history/', TeacherMonthlyAttendanceHistoryView.as_view()),
    path('student/<int:student_id>/fees/', StudentFeeHistoryView.as_view(), name='student_fees'),
    path('fees/pay/', PayFeeView.as_view(), name='pay_fee'),
    path('', include(router.urls)),
]
