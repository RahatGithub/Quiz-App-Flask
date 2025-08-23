# app/models.py
from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(50), nullable=False)
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for anonymous users
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    level_reached = db.Column(db.Integer, default=1)
    score = db.Column(db.Integer, default=0)
    date_attempted = db.Column(db.DateTime, default=datetime.utcnow)
    is_complete = db.Column(db.Boolean, default=False)
    
    # Store individual question responses
    responses = db.relationship('QuestionResponse', backref='attempt', lazy=True, cascade="all, delete-orphan")


class QuestionResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=False)
    question_id = db.Column(db.String(50), nullable=False)  # ID from JSON file
    user_answer = db.Column(db.String(200), nullable=True)
    is_correct = db.Column(db.Boolean, default=False)
    time_taken = db.Column(db.Integer, nullable=True)  # Time in seconds
    points = db.Column(db.Integer, default=0)  # Points earned or lost
    presented_options = db.Column(db.String(500), nullable=True)  # Store options as JSON string

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))