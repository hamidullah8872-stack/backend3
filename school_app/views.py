import calendar
from datetime import date, datetime

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Student, Section, Attendance, FeeLedger, Exam, Mark, TeacherClassAssignment, SchoolSetting
from django.http import HttpResponse
from .serializers import StudentSerializer, SectionSerializer, AttendanceSerializer, FeeLedgerSerializer, ExamSerializer, MarkSerializer

def health_check(request):
    return HttpResponse("School Management System Backend is Online", status=200)

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        date = self.request.query_params.get('date')
        class_name = self.request.query_params.get('class_name')
        section_name = self.request.query_params.get('section_name')

        if date:
            queryset = queryset.filter(date=date)
        if class_name:
            queryset = queryset.filter(class_name=class_name)
        if section_name:
            queryset = queryset.filter(section_name=section_name)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        student = validated['student']
        date = validated['date']

        defaults = {
            'class_name': validated.get('class_name', ''),
            'section_name': validated.get('section_name', ''),
            'status': validated.get('status', 'Present'),
            'time': validated.get('time'),
            'sync_id': validated.get('sync_id'),
        }

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            date=date,
            defaults=defaults,
        )

        output = self.get_serializer(attendance)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(output.data, status=response_status)

class FeeLedgerViewSet(viewsets.ModelViewSet):
    queryset = FeeLedger.objects.all()
    serializer_class = FeeLedgerSerializer

class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer

class MarkViewSet(viewsets.ModelViewSet):
    queryset = Mark.objects.all()
    serializer_class = MarkSerializer


class TeacherMonthlyAttendanceHistoryView(APIView):
    """
    Returns assignment, roster, and a monthly attendance matrix for a teacher.
    """

    def get(self, request, teacher_id: int):
        today = date.today()
        month = self._safe_int(request.query_params.get('month'), today.month)
        year = self._safe_int(request.query_params.get('year'), today.year)
        month = min(max(month, 1), 12)
        year = min(max(year, 2000), 2100)

        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])

        assignments = TeacherClassAssignment.objects.filter(teacher_id=teacher_id).filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=month_end),
            Q(effective_to__isnull=True) | Q(effective_to__gte=month_start),
        ).order_by('-is_primary', '-updated_at')

        assignment = assignments.first()
        if not assignment:
            return Response(
                {
                    'teacher_id': teacher_id,
                    'month': month,
                    'year': year,
                    'assigned_class': None,
                    'dates': self._build_dates(year, month),
                    'students': [],
                    'matrix': [],
                    'message': 'No active class assignment found for the selected period.',
                },
                status=status.HTTP_200_OK,
            )

        student_filters = Q(class_name=assignment.class_name)
        if assignment.section_name:
            student_filters &= Q(section_name=assignment.section_name)
        else:
            student_filters &= (Q(section_name='') | Q(section_name__isnull=True))

        students = list(Student.objects.filter(student_filters).order_by('roll_no', 'name'))
        student_ids = [s.id for s in students]

        attendance_filters = Q(
            student_id__in=student_ids,
            class_name=assignment.class_name,
            date__startswith=f'{year:04d}-{month:02d}-',
        )
        if assignment.section_name:
            attendance_filters &= Q(section_name=assignment.section_name)
        else:
            attendance_filters &= (Q(section_name='') | Q(section_name__isnull=True))

        attendance_rows = Attendance.objects.filter(attendance_filters).order_by('-updated_at')

        by_student = {sid: {} for sid in student_ids}
        for row in attendance_rows:
            day = self._extract_day(row.date)
            if day is None:
                continue
            day_iso = f'{year:04d}-{month:02d}-{day:02d}'
            if day_iso in by_student[row.student_id]:
                continue
            by_student[row.student_id][day_iso] = self._status_code(row.status)

        dates = self._build_dates(year, month)
        matrix = []
        for st in students:
            attendance_by_date = {}
            student_dates = by_student.get(st.id, {})
            for d in dates:
                attendance_by_date[d] = student_dates.get(d, '-')
            matrix.append({
                'student_id': st.id,
                'roll_no': st.roll_no or '',
                'name': st.name or '',
                'father_name': st.father_name or '',
                'attendance_by_date': attendance_by_date,
            })

        return Response(
            {
                'teacher_id': teacher_id,
                'month': month,
                'year': year,
                'assigned_class': {
                    'class_name': assignment.class_name,
                    'section_name': assignment.section_name or '',
                    'assignment_source': assignment.assignment_source,
                    'is_primary': assignment.is_primary,
                },
                'dates': dates,
                'students': [
                    {
                        'id': st.id,
                        'roll_no': st.roll_no or '',
                        'name': st.name or '',
                        'father_name': st.father_name or '',
                    }
                    for st in students
                ],
                'matrix': matrix,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _safe_int(raw, fallback):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _build_dates(year: int, month: int):
        last_day = calendar.monthrange(year, month)[1]
        return [f'{year:04d}-{month:02d}-{day:02d}' for day in range(1, last_day + 1)]

    @staticmethod
    def _extract_day(date_str: str):
        if not date_str:
            return None
        try:
            parsed = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return parsed.day
        except ValueError:
            return None

    @staticmethod
    def _status_code(status_label: str):
        label = (status_label or '').strip().lower()
        if label == 'present':
            return 'P'
        if label == 'absent':
            return 'A'
        if label == 'leave':
            return 'L'
        return '-'


class SchoolInfoView(APIView):
    """Returns general school information."""

    def get(self, request):
        setting = SchoolSetting.get_active()
        return Response({
            'school_name': setting.school_name,
            'reg_no': setting.reg_no or '',
            'phone': setting.phone or '',
            'logo_path': setting.logo.url if setting.logo else '',
        })


class SchoolLogoView(APIView):
    """Serves the school logo image."""

    def get(self, request):
        setting = SchoolSetting.get_active()
        if setting.logo:
            return HttpResponse(setting.logo.read(), content_type="image/png")
        return HttpResponse("No logo found", status=404)
