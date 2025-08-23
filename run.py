# run.py
from app import create_app, db
from app.models import User, Quiz, QuizAttempt, QuestionResponse

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Quiz': Quiz, 
        'QuizAttempt': QuizAttempt,
        'QuestionResponse': QuestionResponse
    }

if __name__ == '__main__':
    app.run(debug=True)