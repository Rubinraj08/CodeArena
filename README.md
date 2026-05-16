CodeArena
A gamified coding platform built with Flask, where users can solve coding challenges, earn badges, and compete in a fun environment.

Features
User authentication and profiles
Coding challenges with test cases
Real-time code execution and validation
Badge system for achievements
Leaderboards and competition
AI-powered code assistance (using Groq API)
Admin panel for task creation
Installation
Clone the repository:

git clone https://github.com/Vishnuprasath18/CodeArena-.git
cd CodeArena-
Create a virtual environment:

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:

pip install -r requirements.txt
Set up the database:

python models.py  # This will create the database
Set environment variables:

Create a .env file in the root directory
Add your Groq API key: GROQ_API_KEY=your_api_key_here
Usage
Run the application:

python app.py
Open your browser and go to http://localhost:5000

Register an account or log in

Start solving coding challenges!

Environment Variables
GROQ_API_KEY: Your Groq API key for AI code assistance (optional)
Project Structure
app.py: Main Flask application
models.py: Database models
templates/: HTML templates
static/: CSS and JavaScript files
instance/: Database files (not committed)
Contributing
Fork the repository
Create a feature branch
Make your changes
Submit a pull request
License
This project is licensed under the MIT License.
