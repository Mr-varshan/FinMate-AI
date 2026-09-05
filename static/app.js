const $ = id => document.getElementById(id);
const money = n => '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

const monthEl = $('month');
function currentMonth() { 
    return monthEl ? (monthEl.value || new Date().toISOString().slice(0, 7)) : new Date().toISOString().slice(0, 7); 
}

async function api(url, options = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options
    });
    let data = {};
    try { data = await res.json(); } catch {}
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
}

function showPanel(id) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active-panel'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    const panel = $(id);
    if (panel) panel.classList.add('active-panel');
    const btn = document.querySelector(`.nav-item[data-target="${id}"]`);
    if (btn) btn.classList.add('active');
    const titles = { dashboard: 'Dashboard', budget: 'Budget Planner', expenses: 'Expenses', advisor: 'FinMate AI' };
    if ($('pageTitle') && titles[id]) $('pageTitle').textContent = titles[id];
    document.querySelector('.sidebar')?.classList.remove('open');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => showPanel(btn.dataset.target)));
document.querySelectorAll('[data-target].quick-expense').forEach(btn => btn.addEventListener('click', () => showPanel(btn.dataset.target)));

$('mobileMenu')?.addEventListener('click', () => $('sidebar')?.classList.toggle('open'));

function fillBudget(b) {
    const f = $('budgetForm');
    if (!f) return;
    Object.keys(b).forEach(k => {
        const el = f.elements[k];
        if (el) el.value = b[k] ?? 0;
    });
}

function updateAffordabilitySummary(d) {
    if ($('affordIncome')) $('affordIncome').textContent = money(d.budget.income);
    if ($('affordSpent')) $('affordSpent').textContent = money(d.total_spent);
    if ($('affordSavings')) $('affordSavings').textContent = money(d.savings_goal);
    if ($('affordAvailable')) $('affordAvailable').textContent = money(d.remaining);
}

function renderDashboard(d) {
    if ($('incomeStat')) $('incomeStat').textContent = money(d.budget.income);
    if ($('spentStat')) $('spentStat').textContent = money(d.total_spent);
    if ($('remainingStat')) $('remainingStat').textContent = money(d.remaining);
    if ($('savingStat')) $('savingStat').textContent = money(d.savings_goal);
    
    const cats = Object.entries(d.category_spending).sort((a, b) => b[1] - a[1]);
    const max = Math.max(...cats.map(x => x[1]), 1);
    
    if ($('categoryBars')) {
        $('categoryBars').innerHTML = cats.map(([n, v]) => `
            <div class="bar-row">
                <div class="bar-label"><span>${n}</span><strong>${money(v)}</strong></div>
                <div class="bar-track"><div class="bar" style="width:${(v / max) * 100}%"></div></div>
            </div>`).join('');
    }
    
    const insights = [];
    if (d.budget.income <= 0) insights.push('Set your monthly income or allowance to activate personalised insights.');
    else if (d.remaining < 0) insights.push('Your recorded spending is above the monthly income entered.');
    else insights.push(`You have ${money(d.remaining)} remaining against the income entered.`);
    if (d.planned_expenses > d.budget.income && d.budget.income > 0) insights.push('Your planned category budgets exceed income. Reduce flexible spending.');
    if (d.savings_goal > 0 && d.remaining >= d.savings_goal) insights.push('Your current remaining amount can cover the savings goal.');
    const top = cats[0];
    if (top && top[1] > 0) insights.push(`${top[0]} is currently your highest spending category.`);
    
    if ($('insights')) {
        $('insights').innerHTML = insights.map(x => `<div class="insight">${x}</div>`).join('');
    }
    
    if ($('recentExpenses')) {
        $('recentExpenses').innerHTML = d.expenses.length ? `
            <table><thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Amount</th></tr></thead>
            <tbody>${d.expenses.slice(0, 8).map(e => `<tr><td>${e.spent_on}</td><td>${e.category}</td><td>${e.description || '-'}</td><td>${money(e.amount)}</td></tr>`).join('')}</tbody></table>
        ` : '<p class="muted">No expenses recorded for this month yet.</p>';
    }
}

function renderExpenses(rows) {
    if ($('expenseTable')) {
        $('expenseTable').innerHTML = rows.length ? `
            <table><thead><tr><th>Date</th><th>Category</th><th>Amount</th><th></th></tr></thead>
            <tbody>${rows.map(e => `<tr><td>${e.spent_on}</td><td>${e.category}</td><td>${money(e.amount)}</td><td><button class="delete" onclick="deleteExpense(${e.id})">Delete</button></td></tr>`).join('')}</tbody></table>
        ` : '<p class="muted">No expenses yet.</p>';
    }
}

async function refresh() {
    try {
        const d = await api(`/api/dashboard?month=${encodeURIComponent(currentMonth())}`);
        fillBudget(d.budget);
        updateAffordabilitySummary(d);
        renderDashboard(d);
        renderExpenses(d.expenses);
    } catch (e) {
        console.error(e);
    }
}

window.deleteExpense = async id => {
    if (!confirm('Delete this expense?')) return;
    try {
        await api(`/api/expenses/${id}`, { method: 'DELETE' });
        refresh();
    } catch (e) {
        alert(e.message);
    }
};

if (monthEl) {
    monthEl.value = new Date().toISOString().slice(0, 7);
    monthEl.addEventListener('change', refresh);
}

const budgetForm = $('budgetForm');
if (budgetForm) {
    budgetForm.addEventListener('submit', async e => {
        e.preventDefault();
        try {
            const data = Object.fromEntries(new FormData(e.target).entries());
            data.month = currentMonth();
            await api('/api/budget', { method: 'POST', body: JSON.stringify(data) });
            if ($('budgetMessage')) $('budgetMessage').textContent = 'Budget saved successfully.';
            refresh();
        } catch (err) {
            if ($('budgetMessage')) $('budgetMessage').textContent = err.message;
        }
    });
}

const expenseForm = $('expenseForm');
if (expenseForm) {
    expenseForm.addEventListener('submit', async e => {
        e.preventDefault();
        try {
            const data = Object.fromEntries(new FormData(e.target).entries());
            await api('/api/expenses', { method: 'POST', body: JSON.stringify(data) });
            e.target.reset();
            refresh();
            showPanel('dashboard');
        } catch (err) {
            alert(err.message);
        }
    });
}

const affordForm = $('affordForm');
if (affordForm) {
    affordForm.addEventListener('submit', async e => {
        e.preventDefault();
        try {
            const d = await api(`/api/dashboard?month=${encodeURIComponent(currentMonth())}`);
            const data = Object.fromEntries(new FormData(e.target).entries());
            data.monthly_income = d.budget.income;
            data.current_month_spend = d.total_spent;
            data.savings_goal = d.savings_goal;
            data.essential = e.target.elements.essential.checked;
            const r = await api('/api/afford', { method: 'POST', body: JSON.stringify(data) });
            const cls = r.score >= 80 ? 'result-good' : r.score >= 50 ? 'result-warn' : 'result-bad';
            if ($('affordResult')) {
                $('affordResult').innerHTML = `<div class="${cls}"><h3>${r.status}</h3><p><strong>Available before purchase:</strong> ${money(r.available_before_purchase)}</p><p><strong>Remaining after purchase:</strong> ${money(r.remaining_after_purchase)}</p><p>${r.suggestion}</p></div>`;
            }
        } catch (err) {
            if ($('affordResult')) $('affordResult').textContent = err.message;
        }
    });
}

const advisorForm = $('advisorForm');
if (advisorForm) {
    advisorForm.addEventListener('submit', async e => {
        e.preventDefault();
        const b = e.target.querySelector('button');
        if (b) {
            b.disabled = true;
            b.textContent = 'Thinking...';
        }
        try {
            const data = Object.fromEntries(new FormData(e.target).entries());
            data.month = currentMonth();
            const r = await api('/api/advice', { method: 'POST', body: JSON.stringify(data) });
            if ($('advisorResult')) {
                $('advisorResult').textContent = r.answer + (r.warning ? `\n\nNote: ${r.warning}` : '');
            }
        } catch (err) {
            if ($('advisorResult')) $('advisorResult').textContent = err.message;
        } finally {
            if (b) {
                b.disabled = false;
                b.textContent = '✧ Ask FinMate AI';
            }
        }
    });
}

refresh();
