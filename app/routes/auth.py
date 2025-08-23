from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Quiz, QuizAttempt, QuestionResponse
from app import db
import random, json 

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Invalid username or password')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return render_template('auth/register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Make first user an admin (for demo purposes)
        if User.query.count() == 0:
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        # Auto-login the user after registration
        login_user(user)
        flash('Registration successful! You are now logged in.')
        
        # Redirect to the home page
        return redirect(url_for('main.index'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@auth_bp.route('/profile')
@login_required
def profile():
    # Get all quiz attempts for the current user, ordered by most recent
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
        .order_by(QuizAttempt.date_attempted.desc()).all()
    
    return render_template('auth/profile.html', attempts=attempts)


@auth_bp.route('/attempt_details/<int:attempt_id>')
@login_required
def attempt_details(attempt_id):
    # Get the attempt and verify it belongs to current user
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    
    # Security check - make sure this attempt belongs to the current user
    if attempt.user_id != current_user.id:
        flash('You are not authorized to view this attempt')
        return redirect(url_for('auth.profile'))
    
    # Get all responses for this attempt
    responses = QuestionResponse.query.filter_by(attempt_id=attempt_id)\
        .order_by(QuestionResponse.id.asc()).all()
    
    # Load questions from JSON
    with open('questions.json', 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    
     # Organize responses by level
    levels_data = {}
    for response in responses:
        # Find the question
        question_data = next((q for q in all_questions if q['id'] == response.question_id), None)
        if question_data:
            level = question_data['level']
            
            # Initialize level data if not exists
            if level not in levels_data:
                levels_data[level] = {
                    'responses': [],
                    'total_points': 0,
                    'total_correct': 0,
                    'total_possible_points': 0
                }
            
            # Use the exact options that were presented to the user
            correct_answer = question_data['correct_answer']
            if response.presented_options:
                try:
                    options = json.loads(response.presented_options)
                except:
                    # Fallback if there's an issue with the stored options
                    incorrect_options = [opt for opt in question_data['options'] if opt != correct_answer]
                    options = random.sample(incorrect_options, 3) + [correct_answer]
                    random.shuffle(options)
            else:
                # Fallback for old records without stored options
                incorrect_options = [opt for opt in question_data['options'] if opt != correct_answer]
                options = random.sample(incorrect_options, 3) + [correct_answer]
                random.shuffle(options)
            
            # Add response to level data
            levels_data[level]['responses'].append({
                'text': question_data['text'],
                'options': options,
                'correct_answer': correct_answer,
                'user_answer': response.user_answer,
                'is_correct': response.is_correct,
                'points': response.points,
                'skipped': response.user_answer is None,
                'possible_points': question_data['points']
            })
            
            # Update level statistics
            levels_data[level]['total_points'] += response.points
            if response.is_correct:
                levels_data[level]['total_correct'] += 1
            levels_data[level]['total_possible_points'] += question_data['points']
    
    # Sort levels
    sorted_levels = sorted(levels_data.items())
    
    return render_template('auth/attempt_details.html', 
                          attempt=attempt, 
                          levels_data=sorted_levels,
                          quiz=Quiz.query.get(attempt.quiz_id))