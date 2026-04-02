import calendar
from datetime import date, datetime

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Student, Section, Attendance, FeeLedger, Exam, Mark, TeacherClassAssignment, SchoolSetting, Timetable, Announcement
from django.http import HttpResponse
from .serializers import StudentSerializer, SectionSerializer, AttendanceSerializer, FeeLedgerSerializer, ExamSerializer, MarkSerializer, TimetableSerializer

def health_check(request):
    return HttpResponse("School Management System Backend is Online", status=200)

class MultiTenantMixin:
    """Helper to filter objects by school_id from headers."""
    def get_queryset(self):
        school_id = self.request.headers.get('x-school-id') or self.request.query_params.get('school_id')
        queryset = super().get_queryset()
        if school_id:
            return queryset.filter(school_id=school_id)
        return queryset

class StudentViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    from rest_framework.decorators import action

    @action(detail=False, url_path='class/(?P<class_name>[^/.]+)/students')
    def by_class(self, request, class_name=None):
        section_name = request.query_params.get('section')
        school_id = request.headers.get('x-school-id') or request.query_params.get('school_id')
        
        queryset = Student.objects.filter(class_name__iexact=class_name)
        if section_name:
            queryset = queryset.filter(section_name__iexact=section_name)
        if school_id:
            queryset = queryset.filter(school_id=school_id)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class SectionViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

class AttendanceViewSet(MultiTenantMixin, viewsets.ModelViewSet):
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

    @action(detail=False, methods=['post'], url_path='submit-bulk')
    def submit_bulk(self, request):
        records = request.data
        if not isinstance(records, list):
            return Response({"status": "error", "message": "Expected a list of records"}, status=status.HTTP_400_BAD_REQUEST)
            
        school_id = request.headers.get('x-school-id') or request.query_params.get('school_id')
        synced = 0
        for r in records:
            try:
                student = Student.objects.get(id=r.get('student'))
                sync_id = f"{student.sync_id}_{r.get('date')}_{r.get('class_name')}"
                Attendance.objects.update_or_create(
                    student=student,
                    date=r.get('date'),
                    defaults={
                        'school_id': school_id,
                        'status': r.get('status', 'Present'),
                        'class_name': r.get('class_name', ''),
                        'section_name': r.get('section_name', ''),
                        'sync_id': sync_id,
                    }
                )
                synced += 1
            except Student.DoesNotExist:
                continue
        return Response({"status": "success", "synced": synced})

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

class FeeLedgerViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = FeeLedger.objects.all()
    serializer_class = FeeLedgerSerializer

class ExamViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer

class MarkViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Mark.objects.all()
    serializer_class = MarkSerializer

class TimetableViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer

class AnnouncementViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Announcement.objects.all()
    from .serializers import AnnouncementSerializer
    serializer_class = AnnouncementSerializer

class AllSectionsView(APIView):
    """Returns all unique classes and sections."""
    def get(self, request):
        school_id = request.headers.get('x-school-id') or request.query_params.get('school_id')
        queryset = Section.objects.all()
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        sections = list(queryset.values('class_name', 'section_name').distinct())
        return Response(sections)

class TeacherAssignmentsView(APIView):
    """Returns assignments for a specific teacher."""
    def get(self, request, teacher_id):
        school_id = request.headers.get('x-school-id') or request.query_params.get('school_id')
        queryset = TeacherClassAssignment.objects.filter(teacher_id=teacher_id)
        if school_id:
            queryset = queryset.filter(school_id=school_id)
            
        from .serializers import TeacherClassAssignmentSerializer
        serializer = TeacherClassAssignmentSerializer(queryset, many=True)
        return Response(serializer.data)


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
            'registration_number': setting.reg_no or '',
            'phone': setting.phone or '',
            'logo_path': f"/api/school/logo/?t={datetime.now().timestamp()}",
        })


class SchoolLogoView(APIView):
    """Serves the school logo image."""

    def get(self, request):
        setting = SchoolSetting.get_active()
        if setting.logo:
            return HttpResponse(setting.logo.read(), content_type="image/png")
class SyncDataView(APIView):
    """
    Receives and synchronizes FULL bulk data from the PC application (SQLite) 
    to the cloud (Supabase/PostgreSQL).
    """

    def post(self, request):
        data = request.data
        school_id = request.headers.get('x-school-id') or '123456'
        if not data:
            print(f"[Sync] Error: No data received for school_id: {school_id}")
            return Response({"status": "error", "message": "No data received"}, status=status.HTTP_400_BAD_REQUEST)

        print(f"[Sync] Received payload for school_id: {school_id}")
        students_payload = data.get('students', [])
        
        try:
            # 1. Sync School Settings & Logo
            settings_data = data.get('settings')
            if settings_data:
                setting, created = SchoolSetting.objects.get_or_create(school_id=school_id)
                setting.school_name = settings_data.get('school_name', setting.school_name)
                setting.reg_no = settings_data.get('registration_number', setting.reg_no)
                setting.phone = settings_data.get('phone', setting.phone)
                
                logo_b64 = data.get('logo_base64')
                if logo_b64:
                    from django.core.files.base import ContentFile
                    import base64
                    try:
                        format, imgstr = logo_b64.split(';base64,') if ';base64,' in logo_b64 else (None, logo_b64)
                        ext = format.split('/')[-1] if format else 'png'
                        setting.logo.save(f"logo_{school_id}.{ext}", ContentFile(base64.b64decode(imgstr)), save=False)
                    except Exception as e:
                        print(f"[Sync] Logo decoding error: {e}")
                
                setting.save()

            # 2. Sync Users
            users_list = data.get('users', [])
            from django.contrib.auth.models import User
            synced_users = 0
            for u in users_list:
                if not u or not isinstance(u, dict): continue
                identifier = str(u.get('phone', u.get('username', ''))).strip()
                password = u.get('password')
                role = u.get('role', 'teacher')
                is_manager = u.get('manager_access', 0) == 1
                
                if not identifier or not password: continue
                
                user, _ = User.objects.get_or_create(username=identifier)
                user.set_password(password)
                user.is_staff = (role == 'admin')
                user.is_superuser = (role == 'admin' or is_manager)
                user.first_name = (u.get('full_name') or '')[:150]
                user.save()
                synced_users += 1

            # 3. Sync Students
            students_list = data.get('students', [])
            synced_students = 0
            for s in students_list:
                if not s or not isinstance(s, dict): continue
                sid = s.get('sync_id')
                if not sid: continue
                
                Student.objects.update_or_create(
                    sync_id=sid,
                    defaults={
                        'school_id': school_id,
                        'name': (s.get('name') or '')[:200],
                        'father_name': (s.get('father_name') or '')[:200],
                        'class_name': (s.get('class_name') or '')[:100],
                        'section_name': (s.get('section_name') or '')[:100],
                        'phone': (s.get('phone') or '')[:50],
                        'admission_no': (s.get('admission_no') or '')[:100],
                        'roll_no': (s.get('roll_no') or '')[:50],
                        'status': (s.get('status') or 'Active')[:50],
                        'gender': (s.get('gender') or '')[:20],
                        'religion': (s.get('religion') or '')[:100],
                    }
                )
                synced_students += 1

            # 4. Sync Exams
            exams_list = data.get('exams', [])
            synced_exams = 0
            exam_map = {}
            for e in exams_list:
                if not e or not isinstance(e, dict): continue
                esid = e.get('sync_id') or f"exam_{school_id}_{e.get('exam_name')}_{e.get('year')}"
                obj, _ = Exam.objects.update_or_create(
                    sync_id=esid,
                    defaults={
                        'school_id': school_id,
                        'exam_name': e.get('exam_name'),
                        'year': e.get('year', 2026),
                    }
                )
                exam_map[e.get('id')] = obj
                synced_exams += 1

            # 5. Sync Marks
            marks_list = data.get('marks', [])
            synced_marks = 0
            for m in marks_list:
                if not m or not isinstance(m, dict): continue
                msid = m.get('sync_id')
                if not msid: continue
                
                try:
                    student_obj = Student.objects.get(sync_id=m.get('student_sync_id'))
                    exam_obj = exam_map.get(m.get('exam_id')) or Exam.objects.filter(exam_name=m.get('exam_name'), year=m.get('year'), school_id=school_id).first()
                    if not exam_obj: continue

                    Mark.objects.update_or_create(
                        sync_id=msid,
                        defaults={
                            'school_id': school_id,
                            'student': student_obj,
                            'exam': exam_obj,
                            'subject': m.get('subject'),
                            'marks': m.get('marks', 0),
                            'term': m.get('term', '1st Term'),
                        }
                    )
                    synced_marks += 1
                except Student.DoesNotExist:
                    continue

            # 6. Sync Teacher Assignments
            assignments_list = data.get('assignments', [])
            synced_assignments = 0
            for a in assignments_list:
                if not a or not isinstance(a, dict): continue
                asid = a.get('sync_id')
                if not asid: continue
                TeacherClassAssignment.objects.update_or_create(
                    sync_id=asid,
                    defaults={
                        'school_id': school_id,
                        'teacher_id': a.get('teacher_id'),
                        'class_name': a.get('class_name'),
                        'section_name': a.get('section_name', 'Default'),
                        'is_primary': True
                    }
                )
                synced_assignments += 1

            # 7. Sync Attendance
            attendance_list = data.get('attendance', [])
            synced_attendance = 0
            for att in attendance_list:
                if not att or not isinstance(att, dict): continue
                asid = att.get('sync_id') or f"{att.get('student_sync_id')}_{att.get('date')}_{att.get('class_name')}"
                
                try:
                    student_obj = Student.objects.get(sync_id=att.get('student_sync_id'))
                    Attendance.objects.update_or_create(
                        sync_id=asid,
                        defaults={
                            'school_id': school_id,
                            'student': student_obj,
                            'date': att.get('date'),
                            'status': att.get('status'),
                            'class_name': att.get('class_name'),
                            'section_name': att.get('section_name'),
                        }
                    )
                    synced_attendance += 1
                except Student.DoesNotExist:
                    continue

            # 8. Sync Timetable
            timetable_list = data.get('timetable', [])
            synced_timetable = 0
            for t in timetable_list:
                if not t or not isinstance(t, dict): continue
                tsid = t.get('sync_id')
                if not tsid: continue
                Timetable.objects.update_or_create(
                    sync_id=tsid,
                    defaults={
                        'school_id': school_id,
                        'class_name': t.get('class_name'),
                        'section_name': t.get('section_name'),
                        'day': t.get('day'),
                        'subject': t.get('subject'),
                        'teacher_id': t.get('teacher_id'),
                        'teacher_name': t.get('teacher_name'),
                        'start_time': t.get('start_time'),
                        'end_time': t.get('end_time'),
                    }
                )
                synced_timetable += 1

            # 9. Sync Announcements
            announcements_list = data.get('announcements', [])
            synced_announcements = 0
            for ann in announcements_list:
                if not ann or not isinstance(ann, dict): continue
                asid = ann.get('sync_id')
                if not asid: continue
                Announcement.objects.update_or_create(
                    sync_id=asid,
                    defaults={
                        'school_id': school_id,
                        'title': ann.get('title'),
                        'content': ann.get('content'),
                        'class_name': ann.get('class_name'),
                        'section_name': ann.get('section_name'),
                        'created_at': ann.get('created_at'),
                    }
                )
                synced_announcements += 1

            return Response({
                "status": "success",
                "message": "Synchronization completed.",
                "counts": {
                    "users": synced_users,
                    "students": synced_students,
                    "exams": synced_exams,
                    "marks": synced_marks,
                    "attendance": synced_attendance,
                    "timetable": synced_timetable,
                    "announcements": synced_announcements,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[Sync] CRITICAL ERROR: {error_details}")
            return Response({"status": "error", "message": f"Sync Error: {error_details}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
