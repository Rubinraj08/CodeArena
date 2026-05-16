from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'student' or 'teacher'
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    avatar = db.Column(db.String(10), default='🧑‍💻')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    submissions = db.relationship('Submission', backref='student', lazy=True, foreign_keys='Submission.student_id')
    tasks = db.relationship('Task', backref='creator', lazy=True)
    badges = db.relationship('Badge', backref='user', lazy=True)

    def xp_to_next_level(self):
        return self.level * 100

    def xp_progress(self):
        return min(100, int((self.xp % (self.level * 100)) / (self.level * 100) * 100))


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # 'easy', 'medium', 'hard'
    xp_reward = db.Column(db.Integer, default=50)
    time_limit = db.Column(db.Integer, default=60)  # minutes
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    test_cases = db.relationship('TestCase', backref='task', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='task', lazy=True)

    def difficulty_color(self):
        return {'easy': '#00ff88', 'medium': '#ffaa00', 'hard': '#ff4444'}.get(self.difficulty, '#ffffff')

    def difficulty_xp(self):
        return {'easy': 50, 'medium': 100, 'hard': 200}.get(self.difficulty, 50)


class TestCase(db.Model):
    __tablename__ = 'test_cases'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(200), default='')


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(30), default='python')
    status = db.Column(db.String(20), default='pending')  # 'pass', 'fail', 'error'
    score = db.Column(db.Float, default=0.0)
    xp_earned = db.Column(db.Integer, default=0)
    time_taken = db.Column(db.Integer, default=0)  # seconds
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Integrity fields
    tab_switches = db.Column(db.Integer, default=0)
    copy_paste_count = db.Column(db.Integer, default=0)
    is_flagged = db.Column(db.Boolean, default=False)
    integrity_log = db.Column(db.Text, default='[]')
    ai_analysis = db.Column(db.Text, nullable=True)
    
    # Dispute fields
    violation_reason = db.Column(db.Text, nullable=True)
    violation_status = db.Column(db.String(20), default=None) # 'pending', 'waived', 'rejected'

    test_results = db.relationship('TestResult', backref='submission', lazy=True, cascade='all, delete-orphan')


class TestResult(db.Model):
    __tablename__ = 'test_results'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_cases.id'), nullable=False)
    passed = db.Column(db.Boolean, default=False)
    actual_output = db.Column(db.Text, default='')
    error_message = db.Column(db.Text, default='')

    test_case = db.relationship('TestCase', backref='test_results', lazy=True)


class Badge(db.Model):
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='assigned')  # 'assigned', 'completed'

    student = db.relationship('User', foreign_keys=[student_id], backref='assigned_tasks')
    task = db.relationship('Task', backref='assignments')
    teacher = db.relationship('User', foreign_keys=[assigned_by])
