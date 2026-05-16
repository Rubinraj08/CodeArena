from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Task, TestCase, Submission, TestResult, Badge, TaskAssignment
from datetime import datetime, timezone
import subprocess, sys, json, os, tempfile, re, shutil
from groq import Groq

app = Flask(__name__)
app.config['SECRET_KEY'] = 'codearena-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///codearena.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'

groq_api_key = "Your_Groq_API_Key_Here"
groq_client = Groq(api_key=GROQ_API_KEY)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─────────────────────────────────────────────
# AI MENTOR
# ─────────────────────────────────────────────

def get_ai_mentor_feedback(submission):
    try:
        task = submission.task
        prompt = f"""
        Role: Helpful Programming Mentor
        Task: {task.title}
        Requirement: {task.description}
        
        Student Code ({submission.language}):
        {submission.code}
        
        Status: {submission.status}
        Score: {submission.score}%
        
        Provide constructive feedback to the student. 
        If they failed, explain why and give a hint. 
        If they passed, suggest a small optimization or praise their logic.
        Keep it concise, encouraging, and tactical.
        """
        
        completion = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"❌ AI Mentor Failure: {e}")
        return "The AI Mentor is analyzing your code. Check back in a moment for detailed insights!"

# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'student')

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'})
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already taken.'})
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered.'})

    avatars = {'student': '🧑‍💻', 'teacher': '👩‍🏫'}
    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, email=email, password_hash=pw_hash,
                role=role, avatar=avatars.get(role, '🧑‍💻'))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = User.query.filter_by(username=username).first()
    if user and bcrypt.check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    return jsonify({'success': False, 'message': 'Invalid credentials.'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'teacher':
        my_tasks = Task.query.filter_by(creator_id=current_user.id).order_by(Task.created_at.desc()).all()
        all_submissions = Submission.query.join(Task).filter(Task.creator_id == current_user.id).all()
        students = User.query.filter_by(role='student').order_by(User.xp.desc()).all()
        # Add flagged_count to each student (exclude waived ones)
        for s in students:
            # Count only flags that are NOT WAIVED. Explicitly handle NULL statuses.
            s.flagged_count = Submission.query.filter_by(student_id=s.id, is_flagged=True)\
                .filter(db.or_(Submission.violation_status != 'waived', Submission.violation_status.is_(None))).count()
        return render_template('dashboard.html', tasks=my_tasks, submissions=all_submissions,
                               students=students, role='teacher')
    else:
        tasks = Task.query.filter_by(is_published=True).order_by(Task.created_at.desc()).all()
        my_submissions = Submission.query.filter_by(student_id=current_user.id).all()
        # Pending disputes for student
        pending_disputes = Submission.query.filter_by(student_id=current_user.id, is_flagged=True, violation_status='pending').all()
        solved_ids = {s.task_id for s in my_submissions if s.status == 'pass'}
        leaderboard = User.query.filter_by(role='student').order_by(User.xp.desc()).limit(10).all()
        badges = Badge.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard.html', tasks=tasks, submissions=my_submissions,
                               solved_ids=solved_ids, leaderboard=leaderboard, badges=badges, role='student',
                               assigned_tasks=current_user.assigned_tasks, pending_disputes=pending_disputes)

# ─────────────────────────────────────────────
# TASK MANAGEMENT (Teacher)
# ─────────────────────────────────────────────

@app.route('/task/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    
    assign_to_id = request.args.get('assign_to')
    assign_to_name = None
    if assign_to_id:
        student = User.query.get(assign_to_id)
        if student:
            assign_to_name = student.username
            
    return render_template('create_task.html', assign_to_id=assign_to_id, assign_to_name=assign_to_name)

@app.route('/task/save', methods=['POST'])
@login_required
def save_task():
    if current_user.role != 'teacher':
        return jsonify({'success': False})
    data = request.get_json()
    diff = data.get('difficulty', 'easy')
    xp_map = {'easy': 50, 'medium': 100, 'hard': 200}
    task = Task(
        title=data['title'], description=data['description'],
        topic=data['topic'], difficulty=diff,
        xp_reward=xp_map.get(diff, 50),
        time_limit=int(data.get('time_limit', 60)),
        creator_id=current_user.id,
        is_published=data.get('publish', False)
    )
    db.session.add(task)
    db.session.flush()
    for tc in data.get('test_cases', []):
        test_case = TestCase(task_id=task.id, input_data=tc['input'],
                             expected_output=tc['output'],
                             is_hidden=tc.get('hidden', False),
                             description=tc.get('description', ''))
        db.session.add(test_case)
    
    # Optional direct assignment
    assign_to_id = data.get('assign_to')
    if assign_to_id:
        assignment = TaskAssignment(student_id=assign_to_id, task_id=task.id, assigned_by=current_user.id)
        db.session.add(assignment)
        
    db.session.commit()
    return jsonify({'success': True, 'task_id': task.id})

@app.route('/task/<int:task_id>/publish', methods=['POST'])
@login_required
def publish_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.creator_id != current_user.id:
        return jsonify({'success': False})
    task.is_published = not task.is_published
    db.session.commit()
    return jsonify({'success': True, 'published': task.is_published})

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.creator_id != current_user.id:
        return jsonify({'success': False})
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/task/generate-ai', methods=['POST'])
@login_required
def generate_task_ai():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.get_json()
    user_prompt = data.get('prompt', '').strip()
    
    if not user_prompt:
        return jsonify({'success': False, 'message': 'Prompt is required'})
    
    try:
        system_prompt = """
        You are an expert competitive programming problem setter. 
        Generate a programming challenge based on the user prompt.
        Return the response in STRICT JSON format. 
        Ensure 'difficulty' is one of: 'easy', 'medium', 'hard'.
        Ensure 'time_limit' is an integer (default 60).
        'test_cases' should be an array of objects with 'input', 'output', 'hidden' (boolean), and 'description'.
        Generate at least 3 test cases, with at least one hidden.
        IMPORTANT: Return ONLY the raw JSON string. No markdown block, no extra text.
        """
        
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate a challenge for: {user_prompt}"}
            ],
            temperature=0.7,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        
        generated_data = json.loads(completion.choices[0].message.content)
        return jsonify({'success': True, 'data': generated_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/task/assign', methods=['POST'])
@login_required
def assign_task():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    data = request.get_json()
    student_id = data.get('student_id')
    task_id = data.get('task_id')
    
    if not student_id or not task_id:
        return jsonify({'success': False, 'message': 'Invalid data'})
    
    # Check if already assigned
    existing = TaskAssignment.query.filter_by(student_id=student_id, task_id=task_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Task already assigned to this student'})
    
    assignment = TaskAssignment(student_id=student_id, task_id=task_id, assigned_by=current_user.id)
    db.session.add(assignment)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/teacher/tasks')
@login_required
def get_teacher_tasks():
    if current_user.role != 'teacher':
        return jsonify([])
    tasks = Task.query.filter_by(creator_id=current_user.id).all()
    return jsonify([{'id': t.id, 'title': t.title} for t in tasks])

# ─────────────────────────────────────────────
# EDITOR & SUBMISSION
# ─────────────────────────────────────────────

@app.route('/task/<int:task_id>/solve')
@login_required
def solve_task(task_id):
    if current_user.role != 'student':
        return redirect(url_for('dashboard'))
    task = Task.query.get_or_404(task_id)
    # Allow if published OR if specifically assigned to this student
    is_assigned = TaskAssignment.query.filter_by(student_id=current_user.id, task_id=task_id).first() is not None
    if not task.is_published and not is_assigned:
        return redirect(url_for('dashboard'))
    visible_cases = [tc for tc in task.test_cases if not tc.is_hidden]
    return render_template('editor.html', task=task, test_cases=visible_cases)

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    data = request.get_json()
    task_id = data.get('task_id')
    code = data.get('code', '')
    language = data.get('language', 'python')
    time_taken = data.get('time_taken', 0)
    tab_switches = data.get('tab_switches', 0)
    copy_paste_count = data.get('copy_paste_count', 0)
    integrity_log = json.dumps(data.get('integrity_log', []))

    # Backend Duplicate Check (within 15 seconds)
    last_sub = Submission.query.filter_by(student_id=current_user.id, task_id=task_id).order_by(Submission.submitted_at.desc()).first()
    if last_sub and (datetime.now(timezone.utc) - last_sub.submitted_at.replace(tzinfo=timezone.utc)).total_seconds() < 15:
        return jsonify({'success': False, 'message': 'Slow down! Too many submissions.'})

    task = Task.query.get_or_404(task_id)
    test_cases = task.test_cases

    results = []
    passed_count = 0

    for tc in test_cases:
        result = run_code(code, language, tc.input_data, tc.expected_output)
        results.append({'test_case_id': tc.id, **result})
        if result['passed']:
            passed_count += 1

    score = (passed_count / len(test_cases) * 100) if test_cases else 0
    status = 'pass' if score == 100 else ('fail' if score > 0 else 'error')

    # XP only on first pass
    existing_pass = Submission.query.filter_by(
        student_id=current_user.id, task_id=task_id, status='pass').first()
    xp_earned = task.xp_reward if status == 'pass' and not existing_pass else 0

    is_flagged = tab_switches > 2 or copy_paste_count > 2
    xp_penalty = 0
    if is_flagged:
        xp_penalty = 25
        # Prevent XP from dropping below 0
        current_user.xp = max(0, current_user.xp - xp_penalty)
        db.session.add(current_user)

    if xp_earned > 0:
        current_user.xp += xp_earned
        # Level up logic
        while current_user.xp >= current_user.level * 100:
            current_user.level += 1
        db.session.add(current_user)

    submission = Submission(
        student_id=current_user.id, task_id=task_id,
        code=code, language=language, status=status,
        score=score, xp_earned=xp_earned, time_taken=time_taken,
        tab_switches=tab_switches, copy_paste_count=copy_paste_count,
        is_flagged=is_flagged, integrity_log=integrity_log,
        violation_status='pending' if is_flagged else None
    )
    db.session.add(submission)
    db.session.flush()

    for r in results:
        tr = TestResult(submission_id=submission.id, test_case_id=r['test_case_id'],
                        passed=r['passed'], actual_output=r.get('actual', ''),
                        error_message=r.get('error', ''))
        db.session.add(tr)

    if xp_earned > 0:
        current_user.xp += xp_earned
        new_level = 1 + current_user.xp // 100
        current_user.level = new_level
        award_badges(current_user)
        
        # Mark assignment as completed if it exists
        assignment = TaskAssignment.query.filter_by(student_id=current_user.id, task_id=task_id, status='assigned').first()
        if assignment:
            assignment.status = 'completed'

    db.session.commit()

    analysis = get_ai_mentor_feedback(submission)
    submission.ai_analysis = analysis
    
    db.session.commit()

    return jsonify({
        'success': True, 'status': status, 'score': score,
        'xp_earned': xp_earned, 'xp_penalty': xp_penalty, 'results': results,
        'passed': passed_count, 'total': len(test_cases),
        'is_flagged': is_flagged,
        'ai_analysis': analysis
    })

# ─────────────────────────────────────────────
# INTEGRITY & DISPUTE RESOLUTION
# ─────────────────────────────────────────────

@app.route('/student/violation/dispute/<int:submission_id>', methods=['POST'])
@login_required
def submit_dispute(submission_id):
    sub = Submission.query.get_or_404(submission_id)
    if sub.student_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'success': False, 'message': 'Justification is required'}), 400
    
    sub.violation_reason = reason
    db.session.commit()
    return jsonify({'success': True})

@app.route('/teacher/student/<int:student_id>/flagged')
@login_required
def get_student_flagged(student_id):
    if current_user.role != 'teacher':
        return jsonify([]), 403
    subs = Submission.query.filter_by(student_id=student_id, is_flagged=True).order_by(Submission.submitted_at.desc()).all()
    res = []
    for s in subs:
        res.append({
            'id': s.id,
            'task_title': s.task.title,
            'submitted_at': s.submitted_at.strftime('%Y-%m-%d %H:%M'),
            'tab_switches': s.tab_switches,
            'copy_paste': s.copy_paste_count,
            'reason': s.violation_reason,
            'status': s.violation_status
        })
    return jsonify(res)

@app.route('/teacher/violation/resolve/<int:submission_id>', methods=['POST'])
@login_required
def resolve_violation(submission_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False}), 403
    
    data = request.get_json()
    action = data.get('action') # 'waive' or 'reject'
    sub = Submission.query.get_or_404(submission_id)
    
    # Check if already processed to avoid multiple XP additions
    if sub.violation_status in ['waived', 'rejected'] and action == sub.violation_status:
        return jsonify({'success': True, 'message': 'Already processed'})

    if action == 'waive':
        # Only restore XP if it was previously penalized (status is 'pending' or 'rejected')
        if sub.violation_status != 'waived':
            sub.violation_status = 'waived'
            # Restore XP only once
            student = User.query.get(sub.student_id)
            if student:
                student.xp += 25
                # Level up logic
                while student.xp >= student.level * 100:
                    student.level += 1
                db.session.add(student)
    elif action == 'reject':
        sub.violation_status = 'rejected'
    
    db.session.commit()
    return jsonify({'success': True})
    try:
        results_summary = ""
        for i, r in enumerate(submission.test_results):
            status = "Pass" if r.passed else "Fail"
            results_summary += f"Test Case {i+1}: {status}\n"
            if not r.passed:
                results_summary += f"  Input: {r.test_case.input_data}\n"
                results_summary += f"  Expected: {r.test_case.expected_output}\n"
                results_summary += f"  Actual: {r.actual_output}\n"
                if r.error_message:
                    results_summary += f"  Error: {r.error_message}\n"
        
        prompt = f"""
Analyze the following code submission for the task: "{submission.task.title}"
Task Description: {submission.task.description}
Language: {submission.language}

Code:
```{submission.language}
{submission.code}
```

Test Results:
{results_summary}

Please provide a detailed analysis in HTML format (using Tailwind-like utility classes or clean inline styles if needed, but primarily semantic HTML for a card-based UI) covering the following:
1. **Standard Verdict**: One of (Accepted, WA, TLE, MLE, RE, CE).
2. **Test-case-level breakdown**: Brief Pass/Fail summary per case.
3. **Root-cause analysis**: Why did it fail (if it did)?
4. **Custom recommendations**: Specific steps to fix or improve.
5. **Edge-case hints**: Points like Overflow, Null input, Boundary issues, etc.
6. **Time/Space optimizations**: Suggestions if applicable.
7. **Visual Debugging Assistance**: A comparison table of Input vs Expected vs Actual for failed cases.
8. **Improvement Tracking**: Note any patterns (e.g., "You often miss boundary cases").

Format the response as a single <div> containing the analysis. Use <h3> for sections and <ul>/<li> for lists.
"""
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2048
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"<div class='error'>AI Mentor currently unavailable: {str(e)}</div>"

def run_code(code, language, input_data, expected_output):
    temp_dir = tempfile.mkdtemp()
    try:
        if language == 'python':
            fname = os.path.join(temp_dir, 'solution.py')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
            cmd = [sys.executable, fname]
        elif language == 'javascript':
            fname = os.path.join(temp_dir, 'solution.js')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
            cmd = ['node', fname]
        elif language == 'c':
            src = os.path.join(temp_dir, 'solution.c')
            exe = os.path.join(temp_dir, 'solution.exe')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            compile_res = subprocess.run(['gcc', src, '-o', exe], capture_output=True, text=True)
            if compile_res.returncode != 0:
                return {'passed': False, 'actual': '', 'error': f'Compilation Error:\n{compile_res.stderr}'}
            cmd = [exe]
        elif language == 'cpp':
            src = os.path.join(temp_dir, 'solution.cpp')
            exe = os.path.join(temp_dir, 'solution.exe')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            compile_res = subprocess.run(['g++', src, '-o', exe], capture_output=True, text=True)
            if compile_res.returncode != 0:
                return {'passed': False, 'actual': '', 'error': f'Compilation Error:\n{compile_res.stderr}'}
            cmd = [exe]
        elif language == 'java':
            # Java needs class name to match file name. Assuming Solution class.
            src = os.path.join(temp_dir, 'Solution.java')
            with open(src, 'w', encoding='utf-8') as f:
                f.write(code)
            compile_res = subprocess.run(['javac', src], capture_output=True, text=True)
            if compile_res.returncode != 0:
                return {'passed': False, 'actual': '', 'error': f'Compilation Error:\n{compile_res.stderr}'}
            cmd = ['java', '-cp', temp_dir, 'Solution']
        else:
            return {'passed': False, 'actual': '', 'error': f'Unsupported language: {language}'}

        result = subprocess.run(
            cmd,
            input=input_data, capture_output=True, text=True, timeout=5
        )
        actual = result.stdout.strip()
        expected = expected_output.strip()
        passed = actual == expected
        error = result.stderr.strip()
        
        return {'passed': passed, 'actual': actual, 'error': error}
        
    except subprocess.TimeoutExpired:
        return {'passed': False, 'actual': '', 'error': 'Time Limit Exceeded'}
    except Exception as e:
        return {'passed': False, 'actual': '', 'error': str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def award_badges(user):
    existing = {b.name for b in user.badges}
    all_subs = Submission.query.filter_by(student_id=user.id, status='pass').count()
    badge_defs = [
        ('First Blood', '🩸', 'Solved your first challenge', all_subs >= 1),
        ('On Fire', '🔥', 'Solved 5 challenges', all_subs >= 5),
        ('Code Warrior', '⚔️', 'Solved 10 challenges', all_subs >= 10),
        ('XP Hunter', '💎', 'Earned 500 XP', user.xp >= 500),
        ('Legend', '👑', 'Reached Level 10', user.level >= 10),
    ]
    for name, icon, desc, cond in badge_defs:
        if cond and name not in existing:
            badge = Badge(user_id=user.id, name=name, icon=icon, description=desc)
            db.session.add(badge)

# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@app.route('/analytics/teacher')
@login_required
def teacher_analytics():
    if current_user.role != 'teacher':
        return jsonify({})
    tasks = Task.query.filter_by(creator_id=current_user.id).all()
    task_ids = [t.id for t in tasks]
    data = []
    for task in tasks:
        subs = Submission.query.filter_by(task_id=task.id).all()
        pass_count = sum(1 for s in subs if s.status == 'pass')
        avg_score = sum(s.score for s in subs) / len(subs) if subs else 0
        data.append({
            'title': task.title, 'difficulty': task.difficulty,
            'submissions': len(subs), 'pass_rate': round(pass_count / len(subs) * 100 if subs else 0, 1),
            'avg_score': round(avg_score, 1)
        })
    return jsonify({'tasks': data})

@app.route('/analytics/student/<int:student_id>')
@login_required
def student_analytics(student_id):
    if current_user.role != 'teacher' and current_user.id != student_id:
        return jsonify({})
    student = User.query.get_or_404(student_id)
    subs = Submission.query.filter_by(student_id=student_id).all()
    flagged = [s for s in subs if s.is_flagged]
    return jsonify({
        'username': student.username, 'xp': student.xp, 'level': student.level,
        'total_submissions': len(subs),
        'passed': sum(1 for s in subs if s.status == 'pass'),
        'flagged_count': len(flagged),
        'avg_score': round(sum(s.score for s in subs) / len(subs) if subs else 0, 1)
    })

@app.route('/submission/<int:sub_id>/log')
@login_required
def view_log(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    if current_user.role != 'teacher':
        return jsonify({})
    return jsonify({
        'username': sub.student.username,
        'task': sub.task.title,
        'tab_switches': sub.tab_switches,
        'copy_paste_count': sub.copy_paste_count,
        'is_flagged': sub.is_flagged,
        'integrity_log': json.loads(sub.integrity_log),
        'time_taken': sub.time_taken,
        'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M') if sub.submitted_at else 'N/A'
    })

@app.route('/submission/<int:sub_id>/analysis')
@login_required
def get_submission_analysis(sub_id):
    sub = Submission.query.get_or_404(sub_id)
    # Allow teacher or the student who made the submission
    if current_user.role != 'teacher' and current_user.id != sub.student_id:
        return jsonify({'analysis': 'Unauthorized'}), 403
    return jsonify({'analysis': sub.ai_analysis})

# ─────────────────────────────────────────────
# INIT & SEED
# ─────────────────────────────────────────────

def seed_data():
    if User.query.count() > 0:
        return
    # Demo teacher
    teacher = User(username='teacher1', email='teacher@arena.com',
                   password_hash=bcrypt.generate_password_hash('teacher123').decode(),
                   role='teacher', avatar='👩‍🏫')
    db.session.add(teacher)
    db.session.flush()

    # Demo student
    student = User(username='student1', email='student@arena.com',
                   password_hash=bcrypt.generate_password_hash('student123').decode(),
                   role='student', avatar='🧑‍💻', xp=150, level=2)
    db.session.add(student)
    db.session.flush()

    # Demo tasks
    tasks_data = [
        ('Hello World', 'Print "Hello, World!" to the console.', 'Basics', 'easy',
         [('', 'Hello, World!', False)]),
        ('Sum of Two Numbers', 'Read two integers and print their sum.\nInput: two space-separated integers.\nOutput: their sum.',
         'Math', 'easy', [('3 5', '8', False), ('10 20', '30', False), ('0 0', '0', True)]),
        ('Fibonacci Nth Term', 'Given N, print the Nth Fibonacci number (0-indexed).\nF(0)=0, F(1)=1.',
         'Algorithms', 'medium', [('5', '5', False), ('10', '55', False), ('0', '0', True)]),
        ('Palindrome Check', 'Given a string, print True if it is a palindrome, False otherwise.',
         'Strings', 'medium', [('racecar', 'True', False), ('hello', 'False', False)]),
        ('Bubble Sort', 'Read N integers on one line (space-separated) and print them sorted.',
         'Sorting', 'hard', [('5 2 8 1 9', '1 2 5 8 9', False), ('3 1 2', '1 2 3', True)]),
    ]

    for title, desc, topic, diff, tcs in tasks_data:
        xp_map = {'easy': 50, 'medium': 100, 'hard': 200}
        task = Task(title=title, description=desc, topic=topic, difficulty=diff,
                    xp_reward=xp_map[diff], time_limit=60,
                    creator_id=teacher.id, is_published=True)
        db.session.add(task)
        db.session.flush()
        for inp, out, hidden in tcs:
            db.session.add(TestCase(task_id=task.id, input_data=inp,
                                    expected_output=out, is_hidden=hidden))

    db.session.commit()
    print("✅ Demo data seeded!")

def patch_database():
    with app.app_context():
        # Get connection engine
        engine = db.engine
        import sqlite3
        from sqlalchemy import text
        
        # Check 'submissions' columns
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(submissions)"))
            columns = [row[1] for row in result]
            
            if not columns:
                return # Table might not exist yet
                
            missing = []
            if 'ai_analysis' not in columns: missing.append('ai_analysis')
            if 'violation_reason' not in columns: missing.append('violation_reason')
            if 'violation_status' not in columns: missing.append('violation_status')
            if 'tab_switches' not in columns: missing.append('tab_switches')
            if 'copy_paste_count' not in columns: missing.append('copy_paste_count')
            if 'is_flagged' not in columns: missing.append('is_flagged')
            if 'integrity_log' not in columns: missing.append('integrity_log')
            
            if missing:
                print(f"🛠 Database Patch: Adding missing columns {missing}")
                # We use raw sqlite for ALTER TABLE to be fast
                for col in missing:
                    try:
                        conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {col} TEXT"))
                    except Exception as e:
                        print(f"Error adding {col}: {e}")
                conn.commit()

with app.app_context():
    db.create_all()
    patch_database()
    seed_data()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
