import calendar
from datetime import date, datetime

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Student, Section, Attendance, FeeLedger, Exam, Mark, TeacherClassAssignment, SchoolSetting, Timetable, Announcement
from django.http import HttpResponse
from .serializers import StudentSerializer, SectionSerializer, AttendanceSerializer, FeeLedgerSerializer, ExamSerializer, MarkSerializer, TimetableSerializer

def health_check(request):
    return HttpResponse("School Management System Backend is Online", status=200)

class MultiTenantMixin:
    """Helper to filter objects by school_id from headers."""
    def get_queryset(self):
        # Default to '123456' for compatibility during migration
        school_id = self.request.headers.get('x-school-id') or self.request.query_params.get('school_id') or '123456'
        queryset = super().get_queryset()
        return queryset.filter(school_id=school_id)

class StudentViewSet(MultiTenantMixin, viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

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

    @transaction.atomic
    def post(self, request):
        data = request.data
        school_id = request.headers.get('x-school-id') or '123456'
        if not data:
            print(f"[Sync] Error: No data received for school_id: {school_id}")
            return Response({"status": "error", "message": "No data received"}, status=status.HTTP_400_BAD_REQUEST)

        print(f"[Sync] >>> STARTING FULL SYNC for school_id: {school_id} <<<")
        
        try:
            # 1. Sync School Settings & Logo
            settings_data = data.get('settings')
            if settings_data:
                print("[Sync] 1/7: Settings & Logo...")
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
                        print(f"[Sync] Logo decoding warning: {e}")
                setting.save()

            # 2. Sync Users (High-level data, keep as loop)
            users_list = data.get('users', [])
            print(f"[Sync] 2/7: Users ({len(users_list)})...")
            from django.contrib.auth.models import User
            for u in users_list:
                if not u or not isinstance(u, dict): continue
                identifier = str(u.get('phone', u.get('username', ''))).strip()
                password = u.get('password')
                if not identifier or not password: continue
                user, _ = User.objects.get_or_create(username=identifier)
                user.set_password(password)
                user.first_name = (u.get('full_name') or '')[:150]
                user.save()

            # 3. FAST SYNC: 🚀 Students (Bulk)
            students_list = data.get('students', [])
            print(f"[Sync] 3/7: Students ({len(students_list)})...")
            student_objs = []
            for s in students_list:
                if not s or not isinstance(s, dict) or not s.get('sync_id'): continue
                student_objs.append(Student(
                    sync_id=s['sync_id'],
                    school_id=school_id,
                    name=(s.get('name') or '')[:200],
                    father_name=(s.get('father_name') or '')[:200],
                    class_name=(s.get('class_name') or '')[:100],
                    section_name=(s.get('section_name') or '')[:100],
                    phone=(s.get('phone') or '')[:50],
                    admission_no=(s.get('admission_no') or '')[:100],
                    roll_no=(s.get('roll_no') or '')[:50],
                    status=(s.get('status') or 'Active')[:50],
                    gender=(s.get('gender') or '')[:20],
                    religion=(s.get('religion') or '')[:100],
                    student_id=s.get('student_id') or s['sync_id'][:50],
                ))
            
            if student_objs:
                Student.objects.bulk_create(
                    student_objs, 
                    update_conflicts=True, 
                    unique_fields=['sync_id'], 
                    update_fields=['school_id', 'name', 'father_name', 'class_name', 'section_name', 'phone', 'admission_no', 'roll_no', 'status', 'gender', 'religion', 'student_id']
                )

            # Map sync_id -> local database primary key (re-fetch after bulk)
            student_map = {s.sync_id: s.id for s in Student.objects.filter(school_id=school_id)}

            # 4. FAST SYNC: 🚀 Exams (Bulk)
            exams_list = data.get('exams', [])
            print(f"[Sync] 4/7: Exams ({len(exams_list)})...")
            exam_objs = []
            for e in exams_list:
                if not e or not isinstance(e, dict): continue
                esid = e.get('sync_id') or f"exam_{school_id}_{e.get('exam_name')}_{e.get('year')}"
                exam_objs.append(Exam(
                    sync_id=esid,
                    school_id=school_id,
                    exam_name=e.get('exam_name'),
                    year=e.get('year', 2026),
                ))
            if exam_objs:
                Exam.objects.bulk_create(exam_objs, update_conflicts=True, unique_fields=['sync_id'], update_fields=['exam_name', 'year'])
            
            exam_map = {e.sync_id: e.id for e in Exam.objects.filter(school_id=school_id)}

            # 5. FAST SYNC: 🚀 Marks (Bulk)
            marks_list = data.get('marks', [])
            print(f"[Sync] 5/7: Marks ({len(marks_list)})...")
            mark_objs = []
            seen_marks = set()
            for m in marks_list:
                sid = m.get('sync_id')
                stid = student_map.get(m.get('student_sync_id'))
                esid = f"exam_{school_id}_{m.get('exam_name')}_{m.get('year')}"
                exid = exam_map.get(esid)
                subj = m.get('subject')
                term = m.get('term', '1st Term')
                if not sid or not stid or not exid or not subj: continue
                
                # DE-DUPLICATE: One mark per student/exam/subject/term
                mark_key = (stid, exid, subj, term)
                if mark_key in seen_marks: continue
                seen_marks.add(mark_key)

                mark_objs.append(Mark(
                    sync_id=sid,
                    school_id=school_id,
                    student_id=stid,
                    exam_id=exid,
                    subject=subj,
                    marks=m.get('marks', 0),
                    term=term,
                ))
            if mark_objs:
                Mark.objects.bulk_create(mark_objs, update_conflicts=True, unique_fields=['sync_id'], update_fields=['marks', 'subject', 'term'])

            # 6. FAST SYNC: 🚀 Attendance (Bulk)
            attendance_list = data.get('attendance', [])
            print(f"[Sync] 6/7: Attendance ({len(attendance_list)})...")
            att_objs = []
            seen_attendance = set()
            for att in attendance_list:
                sid = att.get('sync_id') or f"{att.get('student_sync_id')}_{att.get('date')}_{att.get('class_name')}"
                stid = student_map.get(att.get('student_sync_id'))
                date = att.get('date')
                if not stid or not date: continue
                
                # DE-DUPLICATE: One attendance record per student/date
                att_key = (stid, date)
                if att_key in seen_attendance: continue
                seen_attendance.add(att_key)

                att_objs.append(Attendance(
                    sync_id=sid,
                    school_id=school_id,
                    student_id=stid,
                    date=date,
                    status=att.get('status', 'Present'),
                    class_name=att.get('class_name', ''),
                    section_name=att.get('section_name', 'Default'),
                ))
            if att_objs:
                Attendance.objects.bulk_create(att_objs, update_conflicts=True, unique_fields=['sync_id'], update_fields=['status', 'date', 'class_name', 'section_name'])

            # 7. FAST SYNC: 🚀 Timetable & Announcements (Bulk Overwrite)
            print("[Sync] 7/7: Timetable, Announcements & Assignments...")
            timetable_list = data.get('timetable', [])
            Timetable.objects.filter(school_id=school_id).delete()
            time_objs = [Timetable(
                school_id=school_id,
                class_name=t.get('class_name'),
                section_name=t.get('section_name', 'Default'),
                day=t.get('day'),
                subject=t.get('subject'),
                teacher_id=t.get('teacher_id', 0),
                teacher_name=t.get('teacher_name', ''),
                start_time=t.get('start_time', ''),
                end_time=t.get('end_time', ''),
                sync_id=t.get('sync_id')
            ) for t in timetable_list]
            Timetable.objects.bulk_create(time_objs)

            ann_list = data.get('announcements', [])
            Announcement.objects.filter(school_id=school_id).delete()
            ann_objs = [Announcement(
                school_id=school_id,
                title=a.get('title'),
                content=a.get('content'),
                class_name=a.get('class_name'),
                section_name=a.get('section_name'),
                created_at=a.get('created_at'),
                sync_id=a.get('sync_id')
            ) for a in ann_list]
            Announcement.objects.bulk_create(ann_objs)

            # Sync Teacher Assignments
            assignments_list = data.get('assignments', [])
            TeacherClassAssignment.objects.filter(school_id=school_id).delete()
            asgn_objs = [TeacherClassAssignment(
                school_id=school_id,
                teacher_id=a.get('teacher_id'),
                class_name=a.get('class_name'),
                section_name=a.get('section_name', 'Default'),
                is_primary=True,
                sync_id=a.get('sync_id')
            ) for a in assignments_list]
            TeacherClassAssignment.objects.bulk_create(asgn_objs)

            print(f"[Sync] <<< COMPLETED FULL SYNC for school_id: {school_id} >>>")

            # Return success with counts
            return Response({
                "status": "success", 
                "message": "Bulk Synchronizaton completed.",
                "counts": {
                    "students": len(student_objs),
                    "marks": len(mark_objs),
                    "attendance": len(att_objs),
                    "timetable": len(time_objs),
                    "announcements": len(ann_objs),
                    "assignments": len(asgn_objs),
                    "users": len(users_list),
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[Sync] CRITICAL ERROR: {error_details}")
            return Response({"status": "error", "message": f"Sync Error: {error_details}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
