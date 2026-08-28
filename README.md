# CampusMoney AI

CampusMoney AI is a student financial-literacy prototype for an IBM SkillsBuild hackathon.

## What it demonstrates

- Student budget planner
- Expense tracker
- Spending-pattern analyzer
- "Can I afford this?" checker
- Loan explanation + EMI calculator
- Scholarship/aid discovery
- AI financial-literacy advisor
- IBM watsonx.ai integration
- IBM Bob project context/rules through `AGENTS.md` and `.bob/rules/`

## 1. Install Python

Python 3.10+ is recommended.

## 2. Create a virtual environment

### Windows PowerShell
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Windows CMD
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install packages

```bash
pip install -r requirements.txt
```

## 4. Configure IBM watsonx.ai

Copy `.env.example` to `.env`.

Set:

```text
IBM_CLOUD_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=your_chat_capable_model_id
```

The exact model available depends on your watsonx.ai account/project. The application calls the watsonx.ai `/ml/v1/text/chat` API.

If you do not set credentials, the application automatically uses a local fallback advisor. This is useful for a hackathon demo before cloud configuration is ready.

## 5. Run

```bash
python app.py
```

Open:

http://127.0.0.1:5000

## 6. Use IBM Bob

Open the project folder in IBM Bob and run `/init` if needed. The included `AGENTS.md` describes the architecture and safety requirements. The `.bob/rules/security.md` contains project security rules.

Useful Bob prompts:

1. "Review the complete project for security issues and fix them."
2. "Add a CSV export feature for expenses."
3. "Create automated tests for all Flask API routes."
4. "Improve the mobile UI without adding a large frontend framework."
5. "Review the watsonx.ai integration and make error handling production-safe."

## Hackathon demo flow

1. Set monthly income to ₹20,000.
2. Set a savings goal of ₹3,000.
3. Add food, transport, hostel and entertainment budgets.
4. Add 5-10 expenses.
5. Show the category spending bars.
6. Use "Can I afford this?" for a ₹2,500 purchase.
7. Calculate a sample education loan.
8. Open Scholarships.
9. Ask the AI advisor: "How can I reduce my food spending without affecting my studies?"
10. Explain that IBM Bob was used as the AI software-development partner and IBM watsonx.ai powers the end-user AI advisor.

## Important

This is an educational prototype. Do not use it as a substitute for professional financial advice. Real scholarship deadlines, eligibility and lender terms must be verified from official sources.
