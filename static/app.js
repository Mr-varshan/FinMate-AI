const $ = (id) => document.getElementById(id);
const money = n => "₹" + Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits:2});

function currentMonth() {
  return $("month").value || new Date().toISOString().slice(0,7);
}

async function api(url, options={}) {
  const res = await fetch(url, {
    headers: {"Content-Type":"application/json"},
    ...options
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

function activateTabs() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active-panel"));
      btn.classList.add("active");
      $(btn.dataset.target).classList.add("active-panel");
    });
  });
}

function fillBudget(b) {
  const form = $("budgetForm");
  Object.keys(b).forEach(k => {
    const el = form.elements[k];
    if (el) el.value = b[k] ?? 0;
  });
}

function renderDashboard(d) {
  $("incomeStat").textContent = money(d.budget.income);
  $("spentStat").textContent = money(d.total_spent);
  $("remainingStat").textContent = money(d.remaining);
  $("savingStat").textContent = money(d.savings_goal);

  const cats = Object.entries(d.category_spending).sort((a,b)=>b[1]-a[1]);
  const max = Math.max(...cats.map(x=>x[1]), 1);
  $("categoryBars").innerHTML = cats.map(([name,val]) => `
    <div class="bar-row">
      <div class="bar-label"><span>${name}</span><strong>${money(val)}</strong></div>
      <div class="bar-track"><div class="bar" style="width:${(val/max)*100}%"></div></div>
    </div>
  `).join("");

  const planned = d.planned_expenses;
  const insights = [];
  if (d.budget.income <= 0) insights.push("Set your monthly income or allowance to activate the budget insights.");
  else if (d.remaining < 0) insights.push("Your recorded spending is above the monthly income entered.");
  else insights.push(`You have ${money(d.remaining)} remaining against the income entered.`);
  if (planned > d.budget.income && d.budget.income > 0) insights.push("Your planned categories exceed income. Consider reducing flexible categories.");
  if (d.savings_goal > 0 && d.remaining >= d.savings_goal) insights.push("Your current remaining amount can cover the savings goal.");
  const top = cats[0];
  if (top && top[1] > 0) insights.push(`${top[0]} is currently your highest spending category.`);
  $("insights").innerHTML = insights.map(x => `<div class="insight">${x}</div>`).join("");

  $("recentExpenses").innerHTML = d.expenses.length ? `
    <table><thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Amount</th></tr></thead>
    <tbody>${d.expenses.slice(0,8).map(e=>`
      <tr><td>${e.spent_on}</td><td>${e.category}</td><td>${e.description || "-"}</td><td>${money(e.amount)}</td></tr>
    `).join("")}</tbody></table>
  ` : `<p class="muted">No expenses recorded for this month yet.</p>`;
}

async function refresh() {
  const d = await api(`/api/dashboard?month=${encodeURIComponent(currentMonth())}`);
  fillBudget(d.budget);
  renderDashboard(d);
  renderExpenses(d.expenses);
}

function renderExpenses(rows) {
  $("expenseTable").innerHTML = rows.length ? `
    <table><thead><tr><th>Date</th><th>Category</th><th>Amount</th><th></th></tr></thead>
    <tbody>${rows.map(e=>`
      <tr><td>${e.spent_on}</td><td>${e.category}</td><td>${money(e.amount)}</td>
      <td><button class="delete" onclick="deleteExpense(${e.id})">Delete</button></td></tr>
    `).join("")}</tbody></table>
  ` : `<p class="muted">No expenses yet.</p>`;
}

async function deleteExpense(id) {
  if (!confirm("Delete this expense?")) return;
  await api(`/api/expenses/${id}`, {method:"DELETE"});
  refresh();
}

async function loadScholarships() {
  const rows = await api("/api/scholarships");
  $("scholarshipList").innerHTML = rows.map(s => `
    <div class="scholarship">
      <span class="tag">${s.type}</span>
      <h3>${s.name}</h3>
      <p>${s.description}</p>
      <p><strong>Typical eligibility:</strong> ${s.eligibility}</p>
      <p><strong>Deadline:</strong> ${s.deadline}</p>
      <p class="muted">${s.note}</p>
    </div>
  `).join("");
}

$("month").value = new Date().toISOString().slice(0,7);
$("month").addEventListener("change", refresh);

$("budgetForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.month = currentMonth();
  await api("/api/budget", {method:"POST", body:JSON.stringify(data)});
  $("budgetMessage").textContent = "Budget saved successfully.";
  refresh();
});

$("expenseForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  await api("/api/expenses", {method:"POST", body:JSON.stringify(data)});
  e.target.reset();
  refresh();
});

$("affordForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.essential = e.target.elements.essential.checked;
  const r = await api("/api/afford", {method:"POST", body:JSON.stringify(data)});
  const cls = r.score >= 80 ? "result-good" : r.score >= 50 ? "result-warn" : "result-bad";
  $("affordResult").innerHTML = `
    <div class="${cls}">
      <h3>${r.status}</h3>
      <p><strong>Available before purchase:</strong> ${money(r.available_before_purchase)}</p>
      <p><strong>Remaining after purchase:</strong> ${money(r.remaining_after_purchase)}</p>
      <p>${r.suggestion}</p>
    </div>`;
});

$("loanForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  const r = await api("/api/loan", {method:"POST", body:JSON.stringify(data)});
  $("loanResult").innerHTML = `
    <h2>Loan result</h2>
    <div class="insight"><strong>Estimated EMI:</strong> ${money(r.emi)} / month</div>
    <div class="insight"><strong>Total payment:</strong> ${money(r.total_payment)}</div>
    <div class="insight"><strong>Total interest:</strong> ${money(r.total_interest)}</div>
    <p>${r.explanation}</p>`;
});

$("advisorForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = e.target.querySelector("button");
  button.disabled = true;
  button.textContent = "Thinking...";
  try {
    const data = Object.fromEntries(new FormData(e.target).entries());
    data.month = currentMonth();
    const r = await api("/api/advice", {method:"POST", body:JSON.stringify(data)});
    $("advisorResult").textContent = r.answer + (r.warning ? `\n\nNote: ${r.warning}` : "");
  } catch (err) {
    $("advisorResult").textContent = err.message;
  } finally {
    button.disabled = false;
    button.textContent = "Ask AI";
  }
});

activateTabs();
loadScholarships();
refresh();
