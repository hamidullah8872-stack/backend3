from django.db import models

class Student(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    student_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    admission_no = models.CharField(max_length=100, null=True, blank=True)
    roll_no = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, null=True, blank=True)
    class_name = models.CharField(max_length=100)
    section_name = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    dob = models.CharField(max_length=50, null=True, blank=True)
    dob_words = models.CharField(max_length=200, null=True, blank=True)
    dob_in_figure = models.CharField(max_length=100, null=True, blank=True)
    admission_date = models.CharField(max_length=50, null=True, blank=True)
    admission_class = models.CharField(max_length=100, null=True, blank=True)
    slc_no = models.CharField(max_length=100, null=True, blank=True)
    religion = models.CharField(max_length=50, null=True, blank=True)
    national_id = models.CharField(max_length=100, null=True, blank=True)
    reason_of_leaving = models.TextField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    picture = models.ImageField(upload_to='student_pictures/', null=True, blank=True)
    status = models.CharField(max_length=50, default="Active")
    discount_amount = models.FloatField(default=0)
    discount_percent = models.FloatField(default=0)
    is_free = models.BooleanField(default=False)
    custom_fee = models.FloatField(default=0)
    family_head_id = models.IntegerField(null=True, blank=True)
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.class_name}"

class Section(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    class_name = models.CharField(max_length=100)
    section_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('class_name', 'section_name')

    def __str__(self):
        return f"{self.class_name} - {self.section_name}"

class Attendance(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    class_name = models.CharField(max_length=100)
    section_name = models.CharField(max_length=100, null=True, blank=True)
    date = models.CharField(max_length=50)
    status = models.CharField(max_length=20)
    time = models.CharField(max_length=50, null=True, blank=True)
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'date')

class FeeLedger(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_ledgers')
    class_name = models.CharField(max_length=100)
    month = models.CharField(max_length=50)
    year = models.IntegerField()
    base_fee = models.FloatField()
    discount = models.FloatField(default=0)
    monthly_fee = models.FloatField()
    previous_due = models.FloatField(default=0)
    total_payable = models.FloatField()
    paid_amount = models.FloatField(default=0)
    status = models.CharField(max_length=50)
    created_at = models.CharField(max_length=50, null=True, blank=True)

class Exam(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    exam_name = models.CharField(max_length=200)
    year = models.IntegerField()
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.exam_name} ({self.year})"

class Mark(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100)
    marks = models.IntegerField()
    term = models.CharField(max_length=100, default='1st Term')
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'exam', 'subject', 'term')


class TeacherClassAssignment(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    teacher_id = models.IntegerField(db_index=True)
    class_name = models.CharField(max_length=100)
    section_name = models.CharField(max_length=100, null=True, blank=True)
    assignment_source = models.CharField(max_length=50, default='master_schedule')
    is_primary = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['teacher_id', 'is_primary']),
        ]

    def __str__(self):
        section = f" - {self.section_name}" if self.section_name else ""
        return f"Teacher {self.teacher_id}: {self.class_name}{section}"

class Timetable(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    class_name = models.CharField(max_length=100)
    section_name = models.CharField(max_length=100, null=True, blank=True)
    day = models.CharField(max_length=20)
    subject = models.CharField(max_length=100)
    teacher_id = models.IntegerField()
    teacher_name = models.CharField(max_length=200, null=True, blank=True)
    start_time = models.CharField(max_length=50)
    end_time = models.CharField(max_length=50)
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.day}: {self.class_name} - {self.subject}"


class SchoolSetting(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    school_name = models.CharField(max_length=255, default="Skyronix Model School")
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    reg_no = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.school_name

    @classmethod
    def get_active(cls, school_id=None):
        if school_id:
            return cls.objects.filter(school_id=school_id).first() or cls(school_id=school_id, school_name="Skyronix Model School")
        return cls.objects.first() or cls(school_name="Skyronix Model School")

class Announcement(models.Model):
    school_id = models.CharField(max_length=100, null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    class_name = models.CharField(max_length=100, null=True, blank=True)
    section_name = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.CharField(max_length=100, null=True, blank=True)
    sync_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
