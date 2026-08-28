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
app.config['SECRET_KEY']=os.getenv('SECRET_KEY','dev-only-change-this-secret')
CATEGORIES=['Food','Transport','Education','Hostel/Rent','Bills','Shopping','Entertainment','Healthcare','Subscriptions','Other']

def db():
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row; return conn

def init_db():
    conn=db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS budgets (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,month TEXT NOT NULL,income REAL NOT NULL DEFAULT 0,savings_goal REAL NOT NULL DEFAULT 0,food REAL NOT NULL DEFAULT 0,transport REAL NOT NULL DEFAULT 0,education REAL NOT NULL DEFAULT 0,hostel REAL NOT NULL DEFAULT 0,bills REAL NOT NULL DEFAULT 0,shopping REAL NOT NULL DEFAULT 0,entertainment REAL NOT NULL DEFAULT 0,healthcare REAL NOT NULL DEFAULT 0,subscriptions REAL NOT NULL DEFAULT 0,other REAL NOT NULL DEFAULT 0,UNIQUE(user_id,month),FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,amount REAL NOT NULL,category TEXT NOT NULL,description TEXT,spent_on TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
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
def empty_budget(month):
    return {'id':None,'month':month,'income':0,'savings_goal':0,'food':0,'transport':0,'education':0,'hostel':0,'bills':0,'shopping':0,'entertainment':0,'healthcare':0,'subscriptions':0,'other':0}
def get_budget(user_id,month):
    conn=db(); row=conn.execute('SELECT * FROM budgets WHERE user_id=? AND month=?',(user_id,month)).fetchone(); conn.close(); return dict(row) if row else empty_budget(month)
def get_expenses(user_id,month=None):
    conn=db()
    if month: rows=conn.execute('SELECT * FROM expenses WHERE user_id=? AND substr(spent_on,1,7)=? ORDER BY spent_on DESC,id DESC',(user_id,month)).fetchall()
    else: rows=conn.execute('SELECT * FROM expenses WHERE user_id=? ORDER BY spent_on DESC,id DESC',(user_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]
def dashboard(user_id,month):
    budget=get_budget(user_id,month); expenses=get_expenses(user_id,month); totals={c:0 for c in CATEGORIES}; total=0
    for e in expenses: totals[e['category']]=totals.get(e['category'],0)+e['amount']; total+=e['amount']
    bm={'Food':budget['food'],'Transport':budget['transport'],'Education':budget['education'],'Hostel/Rent':budget['hostel'],'Bills':budget['bills'],'Shopping':budget['shopping'],'Entertainment':budget['entertainment'],'Healthcare':budget['healthcare'],'Subscriptions':budget['subscriptions'],'Other':budget['other']}
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
        if user and check_password_hash(user['password_hash'],password): session.clear(); session['user_id']=user['id']; session['user_name']=user['name']; return redirect(url_for('home'))
        return render_template('login.html',error='Invalid email or password.')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/')
@login_required
def home(): return render_template('index.html',user_name=session.get('user_name'))
@app.route('/history')
@login_required
def history(): return render_template('history.html',expenses=get_expenses(session['user_id']),user_name=session.get('user_name'))

@app.get('/api/dashboard')
@login_required
def api_dashboard(): return jsonify(dashboard(session['user_id'],request.args.get('month',month_now())))
@app.post('/api/budget')
@login_required
def api_budget():
    data=request.get_json(force=True); month=data.get('month',month_now()); numeric=['income','savings_goal','food','transport','education','hostel','bills','shopping','entertainment','healthcare','subscriptions','other']; values={k:float(data.get(k,0) or 0) for k in numeric}; uid=session['user_id']; conn=db()
    conn.execute('''INSERT INTO budgets(user_id,month,income,savings_goal,food,transport,education,hostel,bills,shopping,entertainment,healthcare,subscriptions,other) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET income=excluded.income,savings_goal=excluded.savings_goal,food=excluded.food,transport=excluded.transport,education=excluded.education,hostel=excluded.hostel,bills=excluded.bills,shopping=excluded.shopping,entertainment=excluded.entertainment,healthcare=excluded.healthcare,subscriptions=excluded.subscriptions,other=excluded.other''',(uid,month,*[values[k] for k in numeric])); conn.commit(); conn.close(); return jsonify({'ok':True,'dashboard':dashboard(uid,month)})
@app.post('/api/expenses')
@login_required
def add_expense():
    data=request.get_json(force=True); amount=float(data.get('amount',0)); category=data.get('category','Other'); description=data.get('description','').strip(); spent_on=data.get('spent_on') or datetime.now().strftime('%Y-%m-%d')
    if amount<=0:return jsonify({'error':'Amount must be greater than zero.'}),400
    if category not in CATEGORIES:return jsonify({'error':'Invalid category.'}),400
    conn=db(); cur=conn.execute('INSERT INTO expenses(user_id,amount,category,description,spent_on) VALUES(?,?,?,?,?)',(session['user_id'],amount,category,description,spent_on)); conn.commit(); eid=cur.lastrowid; conn.close(); return jsonify({'ok':True,'id':eid})
@app.get('/api/expenses')
@login_required
def list_expenses(): return jsonify(get_expenses(session['user_id'],request.args.get('month')))
@app.delete('/api/expenses/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    conn=db(); conn.execute('DELETE FROM expenses WHERE id=? AND user_id=?',(expense_id,session['user_id'])); conn.commit(); conn.close(); return jsonify({'ok':True})

@app.post('/api/afford')
@login_required
def afford():
    d=request.get_json(force=True); income=float(d.get('monthly_income',0)); current=float(d.get('current_month_spend',0)); savings=float(d.get('savings_goal',0)); price=float(d.get('price',0)); essential=bool(d.get('essential',False)); available=income-current-savings; after=available-price
    if price<=0: status,score='Enter a valid price.',0
    elif income<=0: status,score='Add your monthly income first.',0
    elif after<0: status,score='Not affordable within the numbers you entered.',25
    elif price>income*.30 and not essential: status,score='Possible, but expensive for a non-essential purchase.',55
    elif after<income*.10: status,score='Possible, but it would leave a small monthly buffer.',65
    else: status,score='Looks affordable within this month’s plan.',90
    return jsonify({'status':status,'score':score,'available_before_purchase':round(available,2),'remaining_after_purchase':round(after,2),'suggestion':'If this is optional, consider waiting 24–48 hours and comparing alternatives.' if not essential else 'Check whether the purchase can be covered without reducing your savings goal.'})
@app.post('/api/loan')
@login_required
def loan():
    d=request.get_json(force=True); p=float(d.get('principal',0)); r=float(d.get('annual_rate',0)); years=float(d.get('years',0))
    if p<=0 or years<=0:return jsonify({'error':'Principal and years must be greater than zero.'}),400
    n=years*12; mr=r/100/12; emi=p/n if mr==0 else p*mr*pow(1+mr,n)/(pow(1+mr,n)-1); total=emi*n
    return jsonify({'emi':round(emi,2),'total_payment':round(total,2),'total_interest':round(total-p,2),'months':int(n),'explanation':'EMI is the regular monthly payment. Compare actual lender terms, fees and penalties.'})
@app.get('/api/scholarships')
@login_required
def scholarships():
    with open(os.path.join(BASE_DIR,'data','scholarships.json'),encoding='utf-8') as f:return jsonify(json.load(f))
def fallback_advice(message,snapshot):
    total=snapshot.get('total_spent',0); remaining=snapshot.get('remaining',0); top=sorted(snapshot.get('category_spending',{}).items(),key=lambda x:x[1],reverse=True); top_text=', '.join(f'{k}: ₹{v:.0f}' for k,v in top[:3] if v>0) or 'No spending data yet.'
    return f'Here is a student-friendly analysis based on your numbers:\n\n• Total spending this month: ₹{total:.2f}\n• Money remaining against income: ₹{remaining:.2f}\n• Top spending areas: {top_text}\n\nSuggested next steps:\n1. Set a monthly savings target before discretionary spending.\n2. Review your highest category and reduce one realistic expense.\n3. Keep a small buffer for unexpected student expenses.\n\nYour question: {message}\n\nThis is educational guidance, not personalized financial advice.'
def watsonx_chat(message,snapshot):
    api_key=os.getenv('IBM_CLOUD_API_KEY'); project_id=os.getenv('WATSONX_PROJECT_ID'); base=os.getenv('WATSONX_URL','https://us-south.ml.cloud.ibm.com').rstrip('/'); model=os.getenv('WATSONX_MODEL_ID','ibm/granite-3-3-8b-instruct')
    if not api_key or not project_id:return fallback_advice(message,snapshot)
    token=requests.post('https://iam.cloud.ibm.com/identity/token',headers={'Content-Type':'application/x-www-form-urlencoded'},data={'grant_type':'urn:ibm:params:oauth:grant-type:apikey','apikey':api_key},timeout=20); token.raise_for_status(); bearer=token.json()['access_token']
    payload={'model_id':model,'project_id':project_id,'messages':[{'role':'system','content':'You are a student financial literacy assistant. Give clear, conservative educational guidance. Do not request passwords, OTPs, PINs or card numbers.'},{'role':'user','content':f'Student question: {message}\nFinancial snapshot: {json.dumps(snapshot)}\nGive 3-6 actionable points.'}],'parameters':{'max_new_tokens':500,'temperature':0.2}}
    res=requests.post(f'{base}/ml/v1/text/chat?version=2024-10-08',headers={'Authorization':f'Bearer {bearer}','Content-Type':'application/json','Accept':'application/json'},json=payload,timeout=60); res.raise_for_status(); return res.json()['choices'][0]['message']['content']
@app.post('/api/advice')
@login_required
def advice():
    d=request.get_json(force=True); message=(d.get('message') or '').strip(); month=d.get('month',month_now())
    if not message:return jsonify({'error':'Please enter a question.'}),400
    snap=dashboard(session['user_id'],month)
    try:return jsonify({'answer':watsonx_chat(message,snap),'ai_enabled':bool(os.getenv('IBM_CLOUD_API_KEY'))})
    except Exception:return jsonify({'answer':fallback_advice(message,snap),'ai_enabled':False,'warning':'IBM watsonx.ai could not be reached; showing the local demo advisor.'})

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=True)
