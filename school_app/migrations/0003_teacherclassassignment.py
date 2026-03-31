from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school_app', '0002_student_admission_class_student_dob_in_figure_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherClassAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('teacher_id', models.IntegerField(db_index=True)),
                ('class_name', models.CharField(max_length=100)),
                ('section_name', models.CharField(blank=True, max_length=100, null=True)),
                ('assignment_source', models.CharField(default='master_schedule', max_length=50)),
                ('is_primary', models.BooleanField(default=False)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='teacherclassassignment',
            index=models.Index(fields=['teacher_id', 'is_primary'], name='school_app_t_teacher_3ebfd0_idx'),
        ),
    ]
