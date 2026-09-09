const $ = id => document.getElementById(id);

const money = n =>
    '₹' + Number(n || 0).toLocaleString('en-IN', {
        maximumFractionDigits: 2
    });

const monthEl = $('month');

function currentMonth() {
    return monthEl.value || new Date().toISOString().slice(0, 7);
}

async function api(url, options = {}) {
    const res = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        },
        ...options
    });

    let data = {};

    try {
        data = await res.json();
    } catch {}

    if (!res.ok) {
        throw new Error(data.error || 'Request failed');
    }

    return data;
}

function showPanel(id) {

    document
        .querySelectorAll('.panel')
        .forEach(p => p.classList.remove('active-panel'));

    document
        .querySelectorAll('.nav-item')
        .forEach(b => b.classList.remove('active'));

    const panel = $(id);

    if (panel) {
        panel.classList.add('active-panel');
    }

    const btn = document.querySelector(
        `.nav-item[data-target="${id}"]`
    );

    if (btn) {
        btn.classList.add('active');
    }

    const titles = {
        dashboard: 'Dashboard',
        budget: 'Budget Planner',
        expenses: 'Expenses',
        loans: 'Education Loans',
        scholarships: 'Scholarships',
        advisor: 'FinMate AI'
    };

    if ($('pageTitle') && titles[id]) {
        $('pageTitle').textContent = titles[id];
    }

    document
        .querySelector('.sidebar')
        ?.classList.remove('open');

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

document
    .querySelectorAll('.nav-item')
    .forEach(btn => {

        btn.addEventListener('click', () => {
            showPanel(btn.dataset.target);
        });

    });

document
    .querySelectorAll('[data-target].quick-expense')
    .forEach(btn => {

        btn.addEventListener('click', () => {
            showPanel(btn.dataset.target);
        });

    });

$('mobileMenu')?.addEventListener('click', () => {

    $('sidebar').classList.toggle('open');

});

// Sidebar open/close button
$('sidebarToggle')?.addEventListener('click', () => {
    const sidebar = $('sidebar');
    if (!sidebar) return;

    if (window.innerWidth <= 760) {
        sidebar.classList.toggle('open');
        return;
    }

    const collapsed = sidebar.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed', collapsed);

    const toggle = $('sidebarToggle');
    if (toggle) {
        toggle.textContent = collapsed ? '›' : '‹';
        toggle.setAttribute('aria-label', collapsed ? 'Open sidebar' : 'Collapse sidebar');
        toggle.setAttribute('title', collapsed ? 'Open sidebar' : 'Collapse sidebar');
    }
});

window.addEventListener('resize', () => {
    const sidebar = $('sidebar');
    if (!sidebar) return;

    if (window.innerWidth > 760) {
        sidebar.classList.remove('open');
    } else {
        document.body.classList.remove('sidebar-collapsed');
    }
});

function fillBudget(b) {

    const f = $('budgetForm');

    if (!f) return;

    Object.keys(b).forEach(k => {

        const el = f.elements[k];

        if (el) {
            el.value = b[k] ?? 0;
        }

    });
}

function updateAffordabilitySummary(d) {

    $('affordIncome').textContent =
        money(d.budget.income);

    $('affordSpent').textContent =
        money(d.total_spent);

    $('affordSavings').textContent =
        money(d.savings_goal);

    $('affordAvailable').textContent =
        money(d.remaining);
}

function renderDashboard(d) {

    $('incomeStat').textContent =
        money(d.budget.income);

    $('spentStat').textContent =
        money(d.total_spent);

    $('remainingStat').textContent =
        money(d.remaining);

    $('savingStat').textContent =
        money(d.savings_goal);

    const categoryOrder = [
        'Food',
        'Education',
        'Hostel/Rent',
        'Healthcare',
        'Shopping',
        'Entertainment',
        'Subscriptions',
        'Other'
    ];

    const cats = categoryOrder.map(category => [

        category,

        d.category_spending?.[category] || 0

    ]);

    const max = Math.max(
        ...cats.map(x => x[1]),
        1
    );

    $('categoryBars').innerHTML = cats
        .map(([n, v]) => `

            <div class="bar-row">

                <div class="bar-label">

                    <span>${escapeHtml(n)}</span>

                    <strong>${money(v)}</strong>

                </div>

                <div class="bar-track">

                    <div
                        class="bar"
                        style="width:${(v / max) * 100}%"
                    ></div>

                </div>

            </div>

        `)
        .join('');

    const insights = [];


    if (d.budget.income <= 0) {

        insights.push(
            'Set your monthly income or allowance to activate personalised insights.'
        );

    } else if (d.remaining < 0) {

        insights.push(
            'Your recorded spending is above the monthly income entered.'
        );

    } else {

        insights.push(
            `You have ${money(d.remaining)} remaining against the income entered.`
        );

    }


    if (
        d.planned_expenses > d.budget.income &&
        d.budget.income > 0
    ) {

        insights.push(
            'Your planned category budgets exceed income. Reduce flexible spending.'
        );

    }


    if (
        d.savings_goal > 0 &&
        d.remaining >= d.savings_goal
    ) {

        insights.push(
            'Your current remaining amount can cover the savings goal.'
        );

    }

    const top = cats
        .filter(x => x[1] > 0)
        .sort((a, b) => b[1] - a[1])[0];


    if (top) {

        insights.push(
            `${top[0]} is currently your highest spending category.`
        );

    }


    $('insights').innerHTML = insights
        .map(x => `

            <div class="insight">
                ${escapeHtml(x)}
            </div>

        `)
        .join('');


    $('recentExpenses').innerHTML = d.expenses.length

        ? `

            <table>

                <thead>

                    <tr>

                        <th>Date</th>

                        <th>Category</th>

                        <th>Description</th>

                        <th>Amount</th>

                    </tr>

                </thead>

                <tbody>

                    ${d.expenses
                        .slice(0, 8)
                        .map(e => `

                            <tr>

                                <td>
                                    ${escapeHtml(e.spent_on)}
                                </td>

                                <td>
                                    ${escapeHtml(e.category)}
                                </td>

                                <td>
                                    ${escapeHtml(e.description || '-')}
                                </td>

                                <td>
                                    ${money(e.amount)}
                                </td>

                            </tr>

                        `)
                        .join('')}

                </tbody>

            </table>

        `

        : `

            <p class="muted">
                No expenses recorded for this month yet.
            </p>

        `;
}

function renderExpenses(rows) {

    $('expenseTable').innerHTML = rows.length

        ? `

            <table>

                <thead>

                    <tr>

                        <th>Date</th>

                        <th>Category</th>

                        <th>Amount</th>

                        <th></th>

                    </tr>

                </thead>

                <tbody>

                    ${rows
                        .map(e => `

                            <tr>

                                <td>
                                    ${escapeHtml(e.spent_on)}
                                </td>

                                <td>
                                    ${escapeHtml(e.category)}
                                </td>

                                <td>
                                    ${money(e.amount)}
                                </td>

                                <td>

                                    <button
                                        class="delete"
                                        onclick="deleteExpense(${e.id})"
                                    >
                                        Delete
                                    </button>

                                </td>

                            </tr>

                        `)
                        .join('')}

                </tbody>

            </table>

        `

        : `

            <p class="muted">
                No expenses yet.
            </p>

        `;
}

function renderEmergency(d) {
    const statusLabels = {
        setup: 'Setup needed',
        critical: 'Critical',
        tight: 'Tight budget',
        stable: 'Emergency buffer available'
    };
    const status = $('emergencyStatus');
    if (status) {
        status.textContent = statusLabels[d.status] || 'Financial safety check';
        status.className = `emergency-status emergency-${d.status || 'stable'}`;
    }
    $('emergencyHeadline').textContent = d.headline || 'Your emergency plan is ready.';
    $('emergencySummary').textContent = d.summary || '';
    $('emergencyAvailable').textContent = money(d.emergency_available);
    $('emergencyDays').textContent = d.days_left;
    $('emergencyEssential').textContent = money(d.essential_spent);
    $('emergencyOptional').textContent = money(d.optional_spent);
    $('emergencyDailyLimit').textContent = money(d.safe_daily_limit);
    $('emergencyEssentialDaily').textContent = money(d.essential_daily);
    $('emergencyFlexibleDaily').textContent = money(d.flexible_daily);
    $('emergencyPressure').textContent = `${Math.round(d.pressure || 0)}%`;
    $('emergencyPressureBar').style.width = `${Math.min(Math.max(d.pressure || 0, 0), 100)}%`;

    const cuts = d.cuts || [];
    $('emergencyCuts').innerHTML = cuts.length ? cuts.map((item, index) => `
        <div class="emergency-cut">
            <div class="emergency-cut-rank">${index + 1}</div>
            <div><strong>${escapeHtml(item.category)}</strong><span>${money(item.spent)} recorded</span><p>${escapeHtml(item.suggestion)}</p></div>
        </div>
    `).join('') : '<p class="muted">No flexible spending is recorded for this month. Keep it that way while you are in Emergency Mode.</p>';

    const actions = d.actions || [];
    $('emergencyActions').innerHTML = actions.map((item, index) => `
        <div class="emergency-action"><span>${index + 1}</span><p>${escapeHtml(item)}</p></div>
    `).join('');
}

async function loadEmergency() {
    try {
        const r = await api('/api/emergency', {
            method: 'POST',
            body: JSON.stringify({ month: currentMonth() })
        });
        renderEmergency(r);
    } catch (e) {
        if ($('emergencySummary')) $('emergencySummary').textContent = e.message;
    }
}

async function refresh() {

    try {

        const d = await api(
            `/api/dashboard?month=${encodeURIComponent(currentMonth())}`
        );

        fillBudget(d.budget);

        updateAffordabilitySummary(d);

        renderDashboard(d);

        renderExpenses(d.expenses);
        loadEmergency();

    } catch (e) {

        console.error(e);

    }
}

window.deleteExpense = async id => {

    if (!confirm('Delete this expense?')) {
        return;
    }

    try {

        await api(
            `/api/expenses/${id}`,
            {
                method: 'DELETE'
            }
        );

        refresh();

    } catch (e) {

        alert(e.message);

    }
};

if (monthEl) {

    monthEl.value =
        new Date().toISOString().slice(0, 7);

    monthEl.addEventListener(
        'change',
        refresh
    );

}

$('budgetForm')?.addEventListener(
    'submit',
    async e => {

        e.preventDefault();

        try {

            const data =
                Object.fromEntries(
                    new FormData(e.target).entries()
                );

            data.month = currentMonth();

            await api(
                '/api/budget',
                {
                    method: 'POST',

                    body: JSON.stringify(data)
                }
            );

            $('budgetMessage').textContent =
                'Budget saved successfully.';

            refresh();

        } catch (err) {

            $('budgetMessage').textContent =
                err.message;

        }

    }
);

$('expenseForm')?.addEventListener(
    'submit',
    async e => {

        e.preventDefault();

        try {

            const data =
                Object.fromEntries(
                    new FormData(e.target).entries()
                );

            await api(
                '/api/expenses',
                {
                    method: 'POST',

                    body: JSON.stringify(data)
                }
            );

            e.target.reset();

            refresh();

            showPanel('dashboard');

        } catch (err) {

            alert(err.message);

        }

    }
);

$('affordForm')?.addEventListener(
    'submit',
    async e => {

        e.preventDefault();

        try {

            const d = await api(
                `/api/dashboard?month=${encodeURIComponent(currentMonth())}`
            );

            const data =
                Object.fromEntries(
                    new FormData(e.target).entries()
                );

            data.monthly_income =
                d.budget.income;

            data.current_month_spend =
                d.total_spent;

            data.savings_goal =
                d.savings_goal;

            data.essential =
                e.target.elements.essential.checked;


            const r = await api(
                '/api/afford',
                {
                    method: 'POST',

                    body: JSON.stringify(data)
                }
            );


            const cls =
                r.score >= 80
                    ? 'result-good'
                    : r.score >= 50
                        ? 'result-warn'
                        : 'result-bad';


            $('affordResult').innerHTML = `

                <div class="${cls}">

                    <h3>
                        ${escapeHtml(r.status)}
                    </h3>

                    <p>
                        <strong>
                            Available before purchase:
                        </strong>

                        ${money(r.available_before_purchase)}
                    </p>

                    <p>
                        <strong>
                            Remaining after purchase:
                        </strong>

                        ${money(r.remaining_after_purchase)}
                    </p>

                    <p>
                        ${escapeHtml(r.suggestion)}
                    </p>

                </div>

            `;

        } catch (err) {

            $('affordResult').textContent =
                err.message;

        }

    }
);

$('advisorForm')?.addEventListener(
    'submit',
    async e => {

        e.preventDefault();

        const b =
            e.target.querySelector('button');

        b.disabled = true;

        b.textContent = 'Thinking...';


        try {

            const data =
                Object.fromEntries(
                    new FormData(e.target).entries()
                );

            data.month = currentMonth();


            const r = await api(
                '/api/advice',
                {
                    method: 'POST',

                    body: JSON.stringify(data)
                }
            );


            $('advisorResult').textContent =
                r.answer +
                (
                    r.warning
                        ? `\n\nNote: ${r.warning}`
                        : ''
                );


        } catch (err) {

            $('advisorResult').textContent =
                err.message;


        } finally {

            b.disabled = false;

            b.textContent =
                '✧ Ask FinMate AI';

        }

    }
);

$('emergencyRefresh')?.addEventListener('click', loadEmergency);

function escapeHtml(value) {

    return String(value ?? '')

        .replace(/&/g, '&amp;')

        .replace(/</g, '&lt;')

        .replace(/>/g, '&gt;')

        .replace(/"/g, '&quot;')

        .replace(/'/g, '&#039;');

}

refresh();
