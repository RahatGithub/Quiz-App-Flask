# app/routes/main.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import current_user
from app.models import Quiz, QuizAttempt, QuestionResponse
from app import db
import json
import random
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('quiz/index.html')

@main_bp.route('/topics')
def topics():
    topics = ['Science', 'Technology', 'History']
    return render_template('quiz/topics.html', topics=topics)

@main_bp.route('/start_quiz/<topic>')
def start_quiz(topic):
    # Create a new quiz attempt
    quiz = Quiz.query.filter_by(topic=topic).first()
    if not quiz:
        quiz = Quiz(topic=topic)
        db.session.add(quiz)
        db.session.commit()
    
    # Create attempt
    attempt = QuizAttempt(quiz_id=quiz.id)
    if current_user.is_authenticated:
        attempt.user_id = current_user.id
    
    db.session.add(attempt)
    db.session.commit()
    
    # Store attempt ID in session
    session['attempt_id'] = attempt.id
    session['level'] = 1
    session['score'] = 0
    session['questions_answered'] = 0
    session['level_questions'] = []  # Will store the IDs of questions for current level
    
    # Load questions for the first level
    _load_level_questions(topic, 1)
    
    return redirect(url_for('main.question'))

def _load_level_questions(topic, level):
    """Helper function to load 10 random questions for a level"""
    # Load all questions from JSON
    with open('questions.json', 'r') as f:
        all_questions = json.load(f)
    
    # Filter questions by topic and level
    level_questions = [q for q in all_questions if q['topic'] == topic and q['level'] == level]
    
    # Select 10 random questions (or all if less than 10)
    if len(level_questions) > 10:
        level_questions = random.sample(level_questions, 10)
    
    # Store question IDs in session
    session['level_questions'] = [q['id'] for q in level_questions]
    session['questions_answered'] = 0


@main_bp.route('/question')
def question():
    # Check if we've reached the question limit for this level
    if session.get('questions_answered', 0) >= 10:
        return redirect(url_for('main.level_complete'))
    
    # Check if we have questions loaded for this level
    if not session.get('level_questions'):
        topic = Quiz.query.get(QuizAttempt.query.get(session['attempt_id']).quiz_id).topic
        _load_level_questions(topic, session.get('level', 1))
    
    # Get next question ID from the loaded questions
    question_id = session['level_questions'][session.get('questions_answered', 0)]
    
    # Load questions from JSON
    with open('questions.json', 'r') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    if not question:
        return redirect(url_for('main.level_complete'))
    
    # Select the correct answer and 3 random incorrect options
    correct_answer = question['correct_answer']
    incorrect_options = [opt for opt in question['options'] if opt != correct_answer]
    selected_options = random.sample(incorrect_options, 3) + [correct_answer]
    random.shuffle(selected_options)  # Shuffle to randomize position
    
    # Store current question in session
    session['current_question'] = question['id']
    
    return render_template('quiz/question.html', 
                          question=question['text'], 
                          options=selected_options,
                          level=session.get('level', 1),
                          question_num=session.get('questions_answered', 0) + 1,
                          total_questions=10,
                          timer=30)


@main_bp.route('/submit_answer', methods=['POST'])
def submit_answer():
    # Get data from form
    answer = request.form.get('answer')
    time_taken = request.form.get('time_taken', 30)
    question_id = session.get('current_question')
    
    # Load questions from JSON
    with open('questions.json', 'r') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    # Calculate points
    is_correct = answer == question['correct_answer']
    points = question['points'] if is_correct else -question['points'] // 2  # Negative marking
    
    # Save response
    response = QuestionResponse(
        attempt_id=session['attempt_id'],
        question_id=question_id,
        user_answer=answer,
        is_correct=is_correct,
        time_taken=time_taken,
        points=points
    )
    db.session.add(response)
    
    # Update attempt score
    attempt = QuizAttempt.query.get(session['attempt_id'])
    attempt.score += points
    session['score'] = attempt.score
    
    # Increment questions answered counter
    session['questions_answered'] = session.get('questions_answered', 0) + 1
    
    db.session.commit()
    
    # Check if level is complete
    if session.get('questions_answered', 0) >= 10:
        return redirect(url_for('main.level_complete'))
    
    return redirect(url_for('main.question'))


def submit_answer():
    # Get data from form
    answer = request.form.get('answer')
    time_taken = request.form.get('time_taken', 30)
    question_id = session.get('current_question')
    
    # Load questions from JSON
    with open('questions.json', 'r') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    # Calculate points
    is_correct = answer == question['correct_answer']
    points = question['points'] if is_correct else -question['points'] // 2  # Negative marking
    
    # Save response
    response = QuestionResponse(
        attempt_id=session['attempt_id'],
        question_id=question_id,
        user_answer=answer,
        is_correct=is_correct,
        time_taken=time_taken,
        points=points
    )
    db.session.add(response)
    
    # Update attempt score
    attempt = QuizAttempt.query.get(session['attempt_id'])
    attempt.score += points
    session['score'] = attempt.score
    
    # Increment questions answered counter
    session['questions_answered'] = session.get('questions_answered', 0) + 1
    
    db.session.commit()
    
    # Check if level is complete
    if session.get('questions_answered', 0) >= 10:
        return redirect(url_for('main.level_complete'))
    
    return redirect(url_for('main.question'))


@main_bp.route('/skip_question')
def skip_question():
    question_id = session.get('current_question')
    
    # Load questions from JSON to get the question details
    with open('questions.json', 'r') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    # Record the skipped question with 0 points
    response = QuestionResponse(
        attempt_id=session['attempt_id'],
        question_id=question_id,
        user_answer=None,  # No answer provided
        is_correct=False,  # Automatically marked as incorrect
        time_taken=0,      # No time recorded
        points=0           # 0 points for skipping
    )
    db.session.add(response)
    
    # Increment questions answered counter
    session['questions_answered'] = session.get('questions_answered', 0) + 1
    
    db.session.commit()
    
    # Check if level is complete
    if session.get('questions_answered', 0) >= 10:
        return redirect(url_for('main.level_complete'))
    
    return redirect(url_for('main.question'))


@main_bp.route('/level_complete')
def level_complete():
    attempt = QuizAttempt.query.get(session['attempt_id'])
    current_level = session.get('level', 1)
    
    # Get responses for current level
    level_responses = QuestionResponse.query.filter_by(
        attempt_id=attempt.id
    ).order_by(QuestionResponse.id.desc()).limit(10).all()
    
    # Calculate level statistics
    total_correct = sum(1 for r in level_responses if r.is_correct)
    total_questions = len(level_responses)
    percentage = (total_correct / total_questions) * 100 if total_questions > 0 else 0
    level_score = sum(r.points for r in level_responses)
    
    # Check if user passed level (60% threshold)
    passed = percentage >= 60
    
    if passed and current_level < 4:
        # Update level reached
        attempt.level_reached = current_level + 1
        db.session.commit()
        
        # Prepare for next level (but don't increment yet - wait for user to proceed)
        next_level = current_level + 1
        
        return render_template('quiz/level_complete.html', 
                              passed=True, 
                              level=current_level,
                              score=level_score,
                              total_correct=total_correct,
                              total_questions=total_questions,
                              percentage=percentage,
                              next_level=next_level)
    elif passed and current_level == 4:
        # Completed the quiz
        attempt.is_complete = True
        db.session.commit()
        return redirect(url_for('main.quiz_complete'))
    else:
        # Failed the level
        attempt.is_complete = True
        db.session.commit()
        return render_template('quiz/level_complete.html', 
                              passed=False, 
                              level=current_level,
                              score=level_score,
                              total_correct=total_correct,
                              total_questions=total_questions,
                              percentage=percentage)

@main_bp.route('/next_level/<int:level>')
def next_level(level):
    # Update session with new level
    session['level'] = level
    session['questions_answered'] = 0
    session['level_questions'] = []
    
    # Load questions for the new level
    topic = Quiz.query.get(QuizAttempt.query.get(session['attempt_id']).quiz_id).topic
    _load_level_questions(topic, level)
    
    return redirect(url_for('main.question'))

@main_bp.route('/quiz_complete')
def quiz_complete():
    attempt = QuizAttempt.query.get(session['attempt_id'])
    return render_template('quiz/complete.html', score=attempt.score)