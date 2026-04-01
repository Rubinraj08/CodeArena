from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Task, TestCase, Submission, TestResult, Badge
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

GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
        return render_template('dashboard.html', tasks=my_tasks, submissions=all_submissions,
                               students=students, role='teacher')
    else:
        tasks = Task.query.filter_by(is_published=True).order_by(Task.created_at.desc()).all()
        my_submissions = Submission.query.filter_by(student_id=current_user.id).all()
        solved_ids = {s.task_id for s in my_submissions if s.status == 'pass'}
        leaderboard = User.query.filter_by(role='student').order_by(User.xp.desc()).limit(10).all()
        badges = Badge.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard.html', tasks=tasks, submissions=my_submissions,
                               solved_ids=solved_ids, leaderboard=leaderboard, badges=badges, role='student')

# ─────────────────────────────────────────────
# TASK MANAGEMENT (Teacher)
# ─────────────────────────────────────────────

@app.route('/task/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))
    return render_template('create_task.html')

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

# ─────────────────────────────────────────────
# EDITOR & SUBMISSION
# ─────────────────────────────────────────────

@app.route('/task/<int:task_id>/solve')
@login_required
def solve_task(task_id):
    if current_user.role != 'student':
        return redirect(url_for('dashboard'))
    task = Task.query.get_or_404(task_id)
    if not task.is_published:
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

    is_flagged = tab_switches > 3 or copy_paste_count > 5

    submission = Submission(
        student_id=current_user.id, task_id=task_id,
        code=code, language=language, status=status,
        score=score, xp_earned=xp_earned, time_taken=time_taken,
        tab_switches=tab_switches, copy_paste_count=copy_paste_count,
        is_flagged=is_flagged, integrity_log=integrity_log
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

    db.session.commit()

    analysis = get_ai_mentor_feedback(submission)
    submission.ai_analysis = analysis
    
    db.session.commit()

    return jsonify({
        'success': True, 'status': status, 'score': score,
        'xp_earned': xp_earned, 'results': results,
        'passed': passed_count, 'total': len(test_cases),
        'is_flagged': is_flagged,
        'ai_analysis': analysis
    })

def get_ai_mentor_feedback(submission):
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True, port=5000)
