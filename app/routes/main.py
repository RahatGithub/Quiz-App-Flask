
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import current_user
from app.models import Quiz, QuizAttempt, QuestionResponse
from app import db
import json, random, time

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
    with open('questions.json', 'r', encoding='utf-8') as f:
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
    # Check if the attempt_id exists in the session
    if 'attempt_id' not in session:
        flash('Your quiz session was reset. Please start a new quiz.')
        return redirect(url_for('main.topics'))

    # Check if we've reached the question limit for this level
    if session.get('questions_answered', 0) >= 10:
        return redirect(url_for('main.level_complete'))
    
    # Add refresh detection
    if 'last_question_time' in session:
        # Calculate time since last question
        last_time = session.get('last_question_time', 0)
        current_time = time.time()
        # If less than 5 seconds have passed since showing the same question
        # and we're not on the first question of the level
        if (current_time - last_time < 5 and 
            session.get('questions_answered', 0) > 0 and
            session.get('current_question') == session['level_questions'][session.get('questions_answered', 0)]):
            # This is likely a refresh, redirect to topics
            flash('Page refresh detected. Your quiz has been reset.')
            session.pop('attempt_id', None)
            return redirect(url_for('main.topics'))
    
    # Update last question time
    session['last_question_time'] = time.time()
    
    # Check if we have questions loaded for this level
    if not session.get('level_questions'):
        topic = Quiz.query.get(QuizAttempt.query.get(session['attempt_id']).quiz_id).topic
        _load_level_questions(topic, session.get('level', 1))
    
    # Get next question ID from the loaded questions
    question_id = session['level_questions'][session.get('questions_answered', 0)]
    
    # Load questions from JSON
    with open('questions.json', 'r', encoding='utf-8') as f:
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
    
    # Store current question and selected options in session
    session['current_question'] = question['id']
    session['current_options'] = selected_options
    
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
    time_taken = int(request.form.get('time_taken', 30))
    question_id = session.get('current_question')
    
    # Load questions from JSON
    with open('questions.json', 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    # Check if the question was answered (not skipped or timed out)
    timed_out = time_taken >= 30
    
    # Calculate points
    is_correct = answer == question['correct_answer'] if answer else False
    
    # Determine points: 
    # - If correct: award full points
    # - If skipped or timed out: 0 points
    # - If wrong answer (actively selected incorrect): negative marking
    if is_correct:
        points = question['points']
    elif not answer or timed_out:  # Skipped or timed out
        points = 0
    else:  # Wrong answer
        points = -question['points'] // 2  # Negative marking
    
    # Get the options that were presented to the user
    presented_options = session.get('current_options', [])
    
    # Save response with presented options
    response = QuestionResponse(
        attempt_id=session['attempt_id'],
        question_id=question_id,
        user_answer=answer,
        is_correct=is_correct,
        time_taken=time_taken,
        points=points,
        presented_options=json.dumps(presented_options)  # Store as JSON string
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
    with open('questions.json', 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    
    # Find the current question
    question = next((q for q in all_questions if q['id'] == question_id), None)
    
    # Get the options that were presented to the user
    presented_options = session.get('current_options', [])
    
    # Record the skipped question with 0 points
    response = QuestionResponse(
        attempt_id=session['attempt_id'],
        question_id=question_id,
        user_answer=None,  # No answer provided
        is_correct=False,  # Automatically marked as incorrect
        time_taken=0,      # No time recorded
        points=0,          # 0 points for skipping
        presented_options=json.dumps(presented_options)  # Store as JSON string
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
    
    # Load all questions from JSON
    with open('questions.json', 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    
    # Get all responses for this attempt
    all_responses = QuestionResponse.query.filter_by(
        attempt_id=attempt.id
    ).order_by(QuestionResponse.id.asc()).all()
    
    # Filter responses for the current level
    level_responses = []
    for response in all_responses:
        # Find the question to get its level
        question = next((q for q in all_questions if q['id'] == response.question_id), None)
        if question and question['level'] == current_level:
            level_responses.append(response)
    
    # Limit to the first 10 responses for this level
    level_responses = level_responses[:10]
    
    # Filter questions for the current level
    level_questions = [q for q in all_questions if q['level'] == current_level]

    # Get points from the first question of this level (if available)
    question_points = level_questions[0]['points'] if level_questions else 10

    # Calculate total possible points (10 questions per level)
    total_possible_points = 10 * question_points

    # Prepare detailed question data
    questions_detail = []
    for response in level_responses:
        # Find the question details from JSON
        question_data = next((q for q in all_questions if q['id'] == response.question_id), None)
        if question_data:
            # Get the correct answer
            correct_answer = question_data['correct_answer']
            
            # Use the exact options that were presented to the user
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
            
            questions_detail.append({
                'text': question_data['text'],
                'options': options,
                'correct_answer': correct_answer,
                'user_answer': response.user_answer,
                'is_correct': response.is_correct,
                'points': response.points,
                'skipped': response.user_answer is None
            })
    
    # Calculate level statistics
    total_correct = sum(1 for r in level_responses if r.is_correct)
    total_questions = len(level_responses)
    percentage_correct = (total_correct / total_questions) * 100 if total_questions > 0 else 0
    
    # Calculate score (ensure it's not negative)
    level_score = sum(r.points for r in level_responses)
    display_score = max(0, level_score)  # Display score is never negative
    
    # Calculate percentage of points obtained
    percentage_points = (display_score / total_possible_points) * 100 if total_possible_points > 0 else 0
    
    # Check if user passed level (60% of total possible points)
    passed = percentage_points >= 60
    
    if passed and current_level < 4:
        # Update level reached
        attempt.level_reached = current_level + 1
        db.session.commit()
        
        # Prepare for next level
        next_level = current_level + 1
        
        return render_template('quiz/level_complete.html', 
                              passed=True, 
                              level=current_level,
                              score=display_score,
                              total_correct=total_correct,
                              total_questions=total_questions,
                              percentage_correct=percentage_correct,
                              percentage_points=percentage_points,
                              total_possible_points=total_possible_points,
                              next_level=next_level,
                              questions_detail=questions_detail)
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
                              score=display_score,
                              total_correct=total_correct,
                              total_questions=total_questions,
                              percentage_correct=percentage_correct,
                              percentage_points=percentage_points,
                              total_possible_points=total_possible_points,
                              questions_detail=questions_detail)

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
    attempt.level_reached = 5
    quiz = Quiz.query.get(attempt.quiz_id)
    
    return render_template('quiz/complete.html', attempt=attempt, quiz=quiz)


