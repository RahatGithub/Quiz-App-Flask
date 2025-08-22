# app/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import User, Quiz, QuizAttempt, QuestionResponse
from app import db

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
def check_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    users = User.query.all()
    quizzes = Quiz.query.all()
    attempts = QuizAttempt.query.all()
    
    return render_template('admin/dashboard.html', 
                          users=users,
                          quizzes=quizzes,
                          attempts=attempts)

@admin_bp.route('/view_attempt/<int:attempt_id>')
@login_required
def view_attempt(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    responses = QuestionResponse.query.filter_by(attempt_id=attempt_id).all()
    
    return render_template('admin/view_attempt.html',
                          attempt=attempt,
                          responses=responses)