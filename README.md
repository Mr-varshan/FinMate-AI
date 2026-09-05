# FinMate AI
Student-friendly financial literacy web application built with Flask for the IBM SkillsBuild Hackathon.

## Features
- User registration and login
- Monthly budget planner
- Expense tracking and history
- Affordability checker
- FinMate AI advisor with IBM watsonx.ai fallback mode
- Responsive pastel dashboard with left-side navigation

## Run locally
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Open `http://127.0.0.1:5000`.


## Profile
- Open **Profile** from the sidebar or click the avatar.
- Update name and email.
- To change password, enter the current password and a new password of at least 6 characters.

## Database
FinMate AI uses **SQLite**, so no separate database server is required for the hackathon demo. The application automatically creates `finance.db` in the project folder.

Stored data includes:
- User name, email and securely hashed password
- Monthly budgets and savings goals
- Expenses and spending history
- FinMate AI conversation history
- Basic account activity logs

### Important for deployment
For a production deployment, use a managed database such as PostgreSQL because some free hosting services use temporary or ephemeral local storage. Never commit real user data or a production `finance.db` file to a public GitHub repository.
