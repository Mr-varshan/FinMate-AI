import os, sqlite3, json
from datetime import datetime
from math import pow
from functools import wraps
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from dotenv import load_dotenv

load_dotenv()
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'finance.db')
app=Flask(__name__)
secret_key=os.getenv('SECRET_KEY')
if not secret_key:
    if os.getenv('TESTING'):
        secret_key='test-secret-key'
    else:
        raise RuntimeError('SECRET_KEY environment variable is required. Create a .env file for local development.')
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE','0') == '1',
)
CATEGORIES=['Food','Transport','Education','Hostel/Rent','Bills','Shopping','Entertainment','Healthcare','Subscriptions','Other']

def db():
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row; return conn

def init_db():
    conn=db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS budgets (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,month TEXT NOT NULL,income REAL NOT NULL DEFAULT 0,savings_goal REAL NOT NULL DEFAULT 0,food REAL NOT NULL DEFAULT 0,transport REAL NOT NULL DEFAULT 0,education REAL NOT NULL DEFAULT 0,hostel REAL NOT NULL DEFAULT 0,bills REAL NOT NULL DEFAULT 0,shopping REAL NOT NULL DEFAULT 0,entertainment REAL NOT NULL DEFAULT 0,healthcare REAL NOT NULL DEFAULT 0,subscriptions REAL NOT NULL DEFAULT 0,other REAL NOT NULL DEFAULT 0,UNIQUE(user_id,month),FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,amount REAL NOT NULL,category TEXT NOT NULL,description TEXT,spent_on TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,month TEXT NOT NULL,user_message TEXT NOT NULL,assistant_response TEXT NOT NULL,ai_enabled INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,action TEXT NOT NULL,details TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, spent_on);
    CREATE INDEX IF NOT EXISTS idx_conversations_user_created ON conversations(user_id, created_at);
    ''')
    # Safe migration for older databases.
    for table in ('budgets','expenses'):
        cols=[r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
        if 'user_id' not in cols:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN user_id INTEGER')
    conn.commit(); conn.close()

def login_required(f):
    @wraps(f)
    def wrapped(*args,**kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'): return jsonify({'error':'Please log in first.'}),401
            return redirect(url_for('login'))
        return f(*args,**kwargs)
    return wrapped

def month_now(): return datetime.now().strftime('%Y-%m')

def parse_nonnegative(value, field_name, allow_zero=True):
    try:
        number=float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} must be a valid number.')
    if number < 0 or (not allow_zero and number == 0):
        raise ValueError(f'{field_name} must be greater than zero.' if not allow_zero else f'{field_name} cannot be negative.')
    return number

def valid_month(value):
    try:
        datetime.strptime(value, '%Y-%m')
        return True
    except (TypeError, ValueError):
        return False

def valid_date(value):
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return True
    except (TypeError, ValueError):
        return False
def empty_budget(month):
    return {'id':None,'month':month,'income':0,'savings_goal':0,'food':0,'transport':0,'education':0,'shopping':0,'healthcare':0}
def get_budget(user_id,month):
    conn=db(); row=conn.execute('SELECT * FROM budgets WHERE user_id=? AND month=?',(user_id,month)).fetchone(); conn.close()
    if not row: return empty_budget(month)
    full=dict(row)
    return {k: full.get(k, 0) for k in ('id','month','income','savings_goal','food','transport','education','healthcare')}
def get_expenses(user_id,month=None):
    conn=db()
    if month: rows=conn.execute('SELECT * FROM expenses WHERE user_id=? AND substr(spent_on,1,7)=? ORDER BY spent_on DESC,id DESC',(user_id,month)).fetchall()
    else: rows=conn.execute('SELECT * FROM expenses WHERE user_id=? ORDER BY spent_on DESC,id DESC',(user_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]
def log_activity(user_id, action, details=''):
    conn=db(); conn.execute('INSERT INTO activity_logs(user_id,action,details,created_at) VALUES(?,?,?,?)',(user_id,action,details,datetime.now().isoformat())); conn.commit(); conn.close()
def save_conversation(user_id, month, message, answer, ai_enabled):
    conn=db(); conn.execute('INSERT INTO conversations(user_id,month,user_message,assistant_response,ai_enabled,created_at) VALUES(?,?,?,?,?,?)',(user_id,month,message,answer,1 if ai_enabled else 0,datetime.now().isoformat())); conn.commit(); conn.close()
def dashboard(user_id,month):
    budget=get_budget(user_id,month); expenses=get_expenses(user_id,month); totals={c:0 for c in CATEGORIES}; total=0
    for e in expenses: totals[e['category']]=totals.get(e['category'],0)+e['amount']; total+=e['amount']
    bm={'Food':budget.get('food',0),'Transport':budget.get('transport',0),'Education':budget.get('education',0),'Healthcare':budget.get('healthcare',0)}
    return {'month':month,'budget':budget,'expenses':expenses,'category_spending':totals,'category_budget':bm,'total_spent':round(total,2),'planned_expenses':round(sum(bm.values()),2),'remaining':round(budget['income']-total,2),'savings_goal':round(budget['savings_goal'],2)}

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or not email or not password: return render_template('register.html',error='All fields are required.')
        if len(password)<6: return render_template('register.html',error='Password must contain at least 6 characters.')
        conn=db()
        try:
            conn.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),datetime.now().isoformat())); conn.commit()
        except sqlite3.IntegrityError:
            conn.close(); return render_template('register.html',error='This email is already registered.')
        conn.close(); return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); conn=db(); user=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
        if user and check_password_hash(user['password_hash'],password): session.clear(); session['user_id']=user['id']; session['user_name']=user['name']; log_activity(user['id'],'login','User signed in'); return redirect(url_for('home'))
        return render_template('login.html',error='Invalid email or password.')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/')
@login_required
def home(): return render_template('index.html',user_name=session.get('user_name'))
@app.route('/history')
@login_required
def history():
    return render_template('history.html', expenses=get_expenses(session['user_id']), user_name=session.get('user_name'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    uid = session['user_id']
    conn = db()
    user = conn.execute('SELECT id, name, email, created_at, password_hash FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        conn.close()
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '')
        current_password = request.form.get('current_password', '')

        if not name or not email:
            conn.close()
            return render_template('profile.html', user=dict(user), error='Name and email are required.')

        existing = conn.execute('SELECT id FROM users WHERE email=? AND id<>?', (email, uid)).fetchone()
        if existing:
            conn.close()
            return render_template('profile.html', user=dict(user), error='This email is already used by another account.')

        if new_password:
            if len(new_password) < 6:
                conn.close()
                return render_template('profile.html', user=dict(user), error='New password must contain at least 6 characters.')
            if not current_password or not check_password_hash(user['password_hash'], current_password):
                conn.close()
                return render_template('profile.html', user=dict(user), error='Current password is incorrect.')
            conn.execute('UPDATE users SET name=?, email=?, password_hash=? WHERE id=?',
                         (name, email, generate_password_hash(new_password), uid))
        else:
            conn.execute('UPDATE users SET name=?, email=? WHERE id=?', (name, email, uid))

        conn.commit()
        updated = conn.execute('SELECT id, name, email, created_at FROM users WHERE id=?', (uid,)).fetchone()
        conn.close()
        session['user_name'] = updated['name']
        log_activity(uid,'profile_updated','Account details updated')
        return render_template('profile.html', user=dict(updated), success='Profile updated successfully.')

    conn.close()
    return render_template('profile.html', user=dict(user))

@app.get('/api/dashboard')
@login_required
def api_dashboard(): return jsonify(dashboard(session['user_id'],request.args.get('month',month_now())))
@app.post('/api/budget')
@login_required
def api_budget():
    data=request.get_json(silent=True) or {}
    month=data.get('month',month_now())
    if not valid_month(month):
        return jsonify({'error':'Month must use YYYY-MM format.'}),400
    numeric=['income','savings_goal','food','transport','education','healthcare']
    try:
        values={k:parse_nonnegative(data.get(k,0), k) for k in numeric}
    except ValueError as exc:
        return jsonify({'error':str(exc)}),400
    uid=session['user_id']; conn=db()
    conn.execute('''INSERT INTO budgets(user_id,month,income,savings_goal,food,transport,education,healthcare) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET income=excluded.income,savings_goal=excluded.savings_goal,food=excluded.food,transport=excluded.transport,education=excluded.education,healthcare=excluded.healthcare''',(uid,month,*[values[k] for k in numeric])); conn.commit(); conn.close(); return jsonify({'ok':True,'dashboard':dashboard(uid,month)})
@app.post('/api/expenses')
@login_required
def add_expense():
    data=request.get_json(silent=True) or {}
    try:
        amount=parse_nonnegative(data.get('amount',0), 'Amount', allow_zero=False)
    except ValueError as exc:
        return jsonify({'error':str(exc)}),400
    category=data.get('category','Other')
    description=str(data.get('description','') or '').strip()
    spent_on=data.get('spent_on') or datetime.now().strftime('%Y-%m-%d')
    if category not in CATEGORIES:return jsonify({'error':'Invalid category.'}),400
    if not valid_date(spent_on):return jsonify({'error':'Date must use YYYY-MM-DD format.'}),400
    conn=db(); cur=conn.execute('INSERT INTO expenses(user_id,amount,category,description,spent_on) VALUES(?,?,?,?,?)',(session['user_id'],amount,category,description,spent_on)); conn.commit(); eid=cur.lastrowid; conn.close(); log_activity(session['user_id'],'expense_added',f'{category}: ₹{amount:.2f}'); return jsonify({'ok':True,'id':eid})
@app.get('/api/expenses')
@login_required
def list_expenses(): return jsonify(get_expenses(session['user_id'],request.args.get('month')))
@app.delete('/api/expenses/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    conn=db(); cur=conn.execute('DELETE FROM expenses WHERE id=? AND user_id=?',(expense_id,session['user_id'])); conn.commit(); deleted=cur.rowcount; conn.close();
    if deleted: log_activity(session['user_id'],'expense_deleted',f'Expense ID {expense_id} deleted');
    return jsonify({'ok':True})

@app.post('/api/afford')
@login_required
def afford():
    d=request.get_json(silent=True) or {}
    try:
        income=parse_nonnegative(d.get('monthly_income',0), 'Monthly income')
        current=parse_nonnegative(d.get('current_month_spend',0), 'Current month spending')
        savings=parse_nonnegative(d.get('savings_goal',0), 'Savings goal')
        price=parse_nonnegative(d.get('price',0), 'Price')
    except ValueError as exc:
        return jsonify({'error':str(exc)}),400
    essential=d.get('essential',False) is True or str(d.get('essential','')).lower() in ('true','1','yes','on')
    available=income-current-savings; after=available-price
    if price<=0: status,score='Enter a valid price.',0
    elif income<=0: status,score='Add your monthly income first.',0
    elif after<0: status,score='Not affordable within the numbers you entered.',25
    elif price>income*.30 and not essential: status,score='Possible, but expensive for a non-essential purchase.',55
    elif after<income*.10: status,score='Possible, but it would leave a small monthly buffer.',65
    else: status,score='Looks affordable within this month’s plan.',90
    return jsonify({'status':status,'score':score,'available_before_purchase':round(available,2),'remaining_after_purchase':round(after,2),'suggestion':'If this is optional, consider waiting 24–48 hours and comparing alternatives.' if not essential else 'Check whether the purchase can be covered without reducing your savings goal.'})
def fallback_advice(message,snapshot):
    total=snapshot.get('total_spent',0); remaining=snapshot.get('remaining',0); top=sorted(snapshot.get('category_spending',{}).items(),key=lambda x:x[1],reverse=True); top_text=', '.join(f'{k}: ₹{v:.0f}' for k,v in top[:3] if v>0) or 'No spending data yet.'
    return f'Here is a student-friendly analysis based on your numbers:\n\n• Total spending this month: ₹{total:.2f}\n• Money remaining against income: ₹{remaining:.2f}\n• Top spending areas: {top_text}\n\nSuggested next steps:\n1. Set a monthly savings target before discretionary spending.\n2. Review your highest category and reduce one realistic expense.\n3. Keep a small buffer for unexpected student expenses.\n\nYour question: {message}\n\nThis is educational guidance, not personalized financial advice.'
def watsonx_chat(message,snapshot):
    api_key=os.getenv('IBM_CLOUD_API_KEY'); project_id=os.getenv('WATSONX_PROJECT_ID'); base=os.getenv('WATSONX_URL','https://us-south.ml.cloud.ibm.com').rstrip('/'); model=os.getenv('WATSONX_MODEL_ID','ibm/granite-3-3-8b-instruct')
    if not api_key or not project_id:return fallback_advice(message,snapshot)
    token=requests.post('https://iam.cloud.ibm.com/identity/token',headers={'Content-Type':'application/x-www-form-urlencoded'},data={'grant_type':'urn:ibm:params:oauth:grant-type:apikey','apikey':api_key},timeout=20); token.raise_for_status(); bearer=token.json()['access_token']
    payload={'model_id':model,'project_id':project_id,'messages':[{'role':'system','content':'You are a student financial literacy assistant. Give clear, conservative educational guidance. Do not request passwords, OTPs, PINs or card numbers.'},{'role':'user','content':f'Student question: {message}\nFinancial snapshot: {json.dumps(snapshot)}\nGive 3-6 actionable points.'}],'parameters':{'max_new_tokens':500,'temperature':0.2}}
    res=requests.post(f'{base}/ml/v1/text/chat?version=2024-10-08',headers={'Authorization':f'Bearer {bearer}','Content-Type':'application/json','Accept':'application/json'},json=payload,timeout=60); res.raise_for_status(); return res.json()['choices'][0]['message']['content']
@app.post('/api/emergency')
@login_required
def emergency_mode():
    data=request.get_json(silent=True) or {}
    month=data.get('month',month_now())
    if not valid_month(month):
        return jsonify({'error':'Month must use YYYY-MM format.'}),400

    snap=dashboard(session['user_id'],month)
    today=datetime.now().date()
    year, month_num=map(int, month.split('-'))
    if today.year == year and today.month == month_num:
        days_in_month=(datetime(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1).date() - datetime(year, month_num, 1).date()).days
        days_left=max(days_in_month - today.day + 1, 1)
        elapsed_days=max(today.day, 1)
    elif (year, month_num) > (today.year, today.month):
        days_in_month=(datetime(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1).date() - datetime(year, month_num, 1).date()).days
        days_left=days_in_month
        elapsed_days=1
    else:
        days_in_month=(datetime(year + (month_num == 12), 1 if month_num == 12 else month_num + 1, 1).date() - datetime(year, month_num, 1).date()).days
        days_left=1
        elapsed_days=days_in_month

    essential_categories={'Food','Transport','Education','Hostel/Rent','Bills','Healthcare'}
    essential_spent=round(sum(e['amount'] for e in snap['expenses'] if e['category'] in essential_categories),2)
    optional_by_category={}
    for e in snap['expenses']:
        if e['category'] not in essential_categories:
            optional_by_category[e['category']]=round(optional_by_category.get(e['category'],0)+e['amount'],2)

    total_spent=snap['total_spent']
    income=snap['budget']['income']
    savings_goal=snap['savings_goal']
    remaining=snap['remaining']
    protected_balance=round(remaining - savings_goal,2)
    emergency_available=max(protected_balance,0)
    essential_daily=round(essential_spent / elapsed_days,2)
    projected_essential=round(essential_daily * days_left,2)
    safe_daily_limit=round(emergency_available / days_left,2) if days_left else 0
    flexible_pool=max(round(emergency_available - projected_essential,2),0)
    flexible_daily=round(flexible_pool / days_left,2) if days_left else 0
    current_daily=round(total_spent / elapsed_days,2) if elapsed_days else 0
    pressure=round((projected_essential / emergency_available) * 100,1) if emergency_available > 0 else 100.0
    pressure=min(max(pressure,0),100)

    if income <= 0:
        status='setup'
        headline='Set your monthly income to activate Emergency Mode.'
        summary='FinMate needs an income figure before it can estimate a safe daily spending limit.'
    elif remaining <= 0:
        status='critical'
        headline='Your recorded spending has used up this month’s income.'
        summary='Pause non-essential spending and review your next unavoidable expense before spending more.'
    elif protected_balance <= 0:
        status='critical'
        headline='Your current balance is at or below your savings goal.'
        summary=f'Protect your ₹{savings_goal:,.0f} savings goal and avoid flexible spending until your balance improves.'
    elif projected_essential > emergency_available:
        status='critical'
        headline='Essential costs may exceed the money available for the rest of the month.'
        summary=f'Your estimated essential needs for the remaining {days_left} day(s) are about ₹{projected_essential:,.0f}, versus ₹{emergency_available:,.0f} available after protecting savings.'
    elif flexible_daily < max(current_daily - essential_daily,0) * 0.75:
        status='tight'
        headline='Your remaining money is manageable, but flexible spending needs a tighter limit.'
        summary=f'Try to keep flexible spending near ₹{flexible_daily:,.0f} per day until the month ends.'
    else:
        status='stable'
        headline='You have a workable emergency buffer.'
        summary=f'Keep essential spending covered and aim to stay within about ₹{safe_daily_limit:,.0f} per day overall.'

    cuts=[]
    for category, amount in sorted(optional_by_category.items(), key=lambda item:item[1], reverse=True):
        if amount > 0:
            cuts.append({'category':category,'spent':amount,'suggestion':f'Reduce {category.lower()} first; it is your highest flexible spending area.' if not cuts else f'Consider pausing or reducing {category.lower()} until the month ends.'})
    actions=[]
    if status in ('critical','tight'):
        actions.append(f'Keep total daily spending at or below about ₹{safe_daily_limit:,.0f}.')
        if flexible_daily <= 0:
            actions.append('Pause non-essential purchases until your emergency buffer is positive again.')
        else:
            actions.append(f'Keep flexible spending near ₹{flexible_daily:,.0f} per day.')
    else:
        actions.append(f'Use ₹{safe_daily_limit:,.0f} per day as your temporary spending ceiling.')
    actions.append('Protect your savings goal before optional spending.')
    actions.append('Review your highest flexible category before making the next non-essential purchase.')
    actions.append('Keep a small amount unspent for unexpected food, travel or health costs.')

    log_activity(session['user_id'],'emergency_mode',f'Emergency Mode viewed for {month}')
    return jsonify({
        'month':month,'status':status,'headline':headline,'summary':summary,
        'income':round(income,2),'total_spent':round(total_spent,2),'remaining':round(remaining,2),
        'savings_goal':round(savings_goal,2),'emergency_available':round(emergency_available,2),
        'days_left':days_left,'essential_spent':essential_spent,'optional_spent':round(sum(optional_by_category.values()),2),
        'essential_daily':essential_daily,'projected_essential':projected_essential,
        'safe_daily_limit':safe_daily_limit,'flexible_daily':flexible_daily,'pressure':pressure,
        'cuts':cuts[:5],'actions':actions
    })

@app.post('/api/advice')
@login_required
def advice():
    d=request.get_json(force=True); message=(d.get('message') or '').strip(); month=d.get('month',month_now())
    if not message:return jsonify({'error':'Please enter a question.'}),400
    snap=dashboard(session['user_id'],month)
    try:
        ai_enabled=bool(os.getenv('IBM_CLOUD_API_KEY'))
        answer=watsonx_chat(message,snap)
        save_conversation(session['user_id'],month,message,answer,ai_enabled)
        log_activity(session['user_id'],'ai_advice','Saved a FinMate AI conversation')
        return jsonify({'answer':answer,'ai_enabled':ai_enabled})
    except Exception:
        answer=fallback_advice(message,snap)
        save_conversation(session['user_id'],month,message,answer,False)
        return jsonify({'answer':answer,'ai_enabled':False,'warning':'IBM watsonx.ai could not be reached; showing the local demo advisor.'})



# Educational loan guidance. This route does not approve, apply for, or rank lenders;
# it gives conservative educational guidance and can use the same FinMate AI model.
@app.post('/api/loan-advice')
@login_required
def loan_advice():
    data=request.get_json(force=True) or {}
    purpose=(data.get('purpose') or '').strip()
    try:
        amount=parse_nonnegative(data.get('amount',0), 'Loan amount', allow_zero=False)
    except ValueError as exc:
        return jsonify({'error':str(exc)}),400
    study_level=(data.get('study_level') or '').strip()
    if not purpose:
        return jsonify({'error':'Please select an educational purpose.'}),400
    if amount <= 0:
        return jsonify({'error':'Enter a valid loan amount.'}),400

    allowed_purposes={
        'Laptop / computer': 'education technology',
        'Course / tuition fee': 'education fees',
        'Books / study materials': 'academic materials',
        'Certification / exam fee': 'academic certification',
        'Other education expense': 'education expense'
    }
    purpose_label=allowed_purposes.get(purpose,'education expense')
    month=month_now()
    snap=dashboard(session['user_id'],month)
    prompt=(
        'Give conservative educational guidance about whether an education loan may be worth considering. '
        f'The student selected purpose: {purpose} ({purpose_label}), amount: ₹{amount:.2f}, '
        f'study level: {study_level or "not specified"}. '
        f'Current financial snapshot: {json.dumps(snap)}. '
        'Do not name a lender as guaranteed, do not promise approval or rates, and do not tell the student to '
        'borrow more than needed. Explain that they should compare total repayment cost, fees, interest/APR, '
        'moratorium, collateral/co-signer requirements, and repayment terms. Mention that scholarships, grants, '
        'institutional aid, savings, or a lower-cost alternative should be checked first when appropriate. '
        'For a laptop, suggest considering refurbished/used or institutional options before borrowing. '
        'Return 4-6 concise bullet points and a short recommendation.'
    )
    try:
        answer=watsonx_chat(prompt,snap)
        ai_enabled=bool(os.getenv('IBM_CLOUD_API_KEY'))
    except Exception:
        remaining=float(snap.get('remaining',0) or 0)
        if purpose == 'Laptop / computer':
            alternative='Before borrowing, compare a lower-cost/refurbished laptop, college/institution support, savings, and scholarships.'
        else:
            alternative='Before borrowing, check scholarships, grants, institutional support, savings, and lower-cost alternatives.'
        answer=(
            f'Education loan guidance for {purpose.lower()} (₹{amount:,.2f}):\n\n'
            f'• Borrow only the amount you genuinely need.\n'
            f'• Compare total repayment cost, interest/APR, fees, moratorium and repayment period.\n'
            f'• Check scholarships, grants and institutional assistance before taking a loan.\n'
            f'• {alternative}\n'
            f'• Your current recorded monthly remaining balance is ₹{remaining:,.2f}; avoid a repayment that would make your regular budget unsustainable.\n\n'
            'This is educational guidance, not a loan recommendation or approval.'
        )
        ai_enabled=False
    log_activity(session['user_id'],'loan_guidance',f'{purpose}: ₹{amount:.2f}')
    return jsonify({'answer':answer,'ai_enabled':ai_enabled})


@app.post('/api/scholarships')
@login_required
def scholarships():
    data=request.get_json(force=True) or {}
    study_level=(data.get('study_level') or '').strip()
    field=(data.get('field') or '').strip()
    need=(data.get('need') or '').strip()
    income=data.get('family_income')
    try:
        income_value=parse_nonnegative(income, 'Annual family income') if income not in (None,'') else None
    except (TypeError,ValueError):
        return jsonify({'error':'Enter a valid annual family income or leave it blank.'}),400

    suggestions=[]
    if need in ('Need-based','Both merit and need') or (income_value is not None and income_value <= 600000):
        suggestions.append({'title':'Need-based scholarships','text':'Look for schemes that use family income, financial need and academic eligibility.'})
    if need in ('Merit-based','Both merit and need'):
        suggestions.append({'title':'Merit scholarships','text':'Check academic-performance scholarships offered by your institution and eligible scholarship providers.'})
    if not suggestions:
        suggestions.append({'title':'Merit and need-based options','text':'Check both academic-performance and financial-need criteria so you do not miss eligible support.'})
    if study_level:
        suggestions.append({'title':f'{study_level} opportunities','text':f'Filter scholarship searches for {study_level} students and verify the eligibility rules for your course.'})
    if field:
        suggestions.append({'title':f'{field} opportunities','text':f'Also search for scholarships or educational grants specifically supporting {field} students.'})
    suggestions.append({'title':'Verify before applying','text':'Use the official scholarship or institution website, check the current deadline, eligibility, required documents and whether the application is free.'})
    log_activity(session['user_id'],'scholarship_guidance','Scholarship guidance viewed')
    return jsonify({'suggestions':suggestions[:5],'note':'This is guidance, not a live list of scholarship openings. Always verify current eligibility and deadlines on the official source.'})

@app.get('/api/conversations')
@login_required
def list_conversations():
    conn=db(); rows=conn.execute('SELECT id,month,user_message,assistant_response,ai_enabled,created_at FROM conversations WHERE user_id=? ORDER BY created_at DESC',(session['user_id'],)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.get('/api/activity')
@login_required
def activity():
    conn=db(); rows=conn.execute('SELECT action,details,created_at FROM activity_logs WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(session['user_id'],)).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

init_db()
if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT','5000')), debug=os.getenv('FLASK_DEBUG','0') == '1')
