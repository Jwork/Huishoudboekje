/**
 * Dashboard JS — shared time selector, chart rendering, and drilldown logic
 * Used by both dashboard_overview.html and dashboard_categories.html
 */

// ==================== State ====================

let currentPreset = 'last6m';
let currentMonth = null;
let currentYear = null;
let currentDirection = 'debit';
let currentPage = null; // 'overview' or 'categories'

// Chart instances (destroyed before re-render)
let chartMonthlyTrend = null;
let chartSavingsFlow = null;
let chartCategoryDonut = null;
let chartCatDonut = null;
let chartCatBar = null;
let chartSubDonut = null;
let chartCatTrend = null;

// ==================== Initialization ====================

function initDashboard(page) {
    currentPage = page;
    populateYearPicker();
    highlightPreset('last6m');
    loadData();
}

// ==================== Currency Formatting ====================

function formatCurrency(amount) {
    return new Intl.NumberFormat('nl-NL', {
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 2
    }).format(amount);
}

function formatMonth(year, month) {
    const names = ['', 'Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'];
    return names[month] + ' ' + year;
}

// ==================== Time Selector ====================

function populateYearPicker() {
    const sel = document.getElementById('yearPicker');
    if (!sel) return;
    const currentYear = new Date().getFullYear();
    for (let y = currentYear; y >= currentYear - 5; y--) {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = y;
        sel.appendChild(opt);
    }
}

function setPreset(preset) {
    currentPreset = preset;
    currentMonth = null;
    currentYear = null;
    // Clear month/year pickers
    const mp = document.getElementById('monthPicker');
    const yp = document.getElementById('yearPicker');
    if (mp) mp.value = '';
    if (yp) yp.value = '';
    highlightPreset(preset);
    loadData();
}

function setMonthPicker() {
    const mp = document.getElementById('monthPicker');
    const yp = document.getElementById('yearPicker');
    if (!mp || !yp) return;
    const m = parseInt(mp.value);
    const y = parseInt(yp.value);
    if (m && y) {
        currentMonth = m;
        currentYear = y;
        currentPreset = null;
        highlightPreset(null);
        loadData();
    }
}

function setDirection(dir) {
    currentDirection = dir;
    // Update button styles
    const btnDebit = document.getElementById('btnDebit');
    const btnCredit = document.getElementById('btnCredit');
    if (btnDebit && btnCredit) {
        if (dir === 'debit') {
            btnDebit.className = 'direction-btn px-4 py-2 rounded font-medium text-sm border transition-colors bg-red-100 text-red-700 border-red-300';
            btnCredit.className = 'direction-btn px-4 py-2 rounded font-medium text-sm border transition-colors bg-white text-gray-600 border-gray-300 hover:bg-green-50';
        } else {
            btnDebit.className = 'direction-btn px-4 py-2 rounded font-medium text-sm border transition-colors bg-white text-gray-600 border-gray-300 hover:bg-red-50';
            btnCredit.className = 'direction-btn px-4 py-2 rounded font-medium text-sm border transition-colors bg-green-100 text-green-700 border-green-300';
        }
    }
    closeDrilldown();
    loadData();
}

function highlightPreset(preset) {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        if (btn.dataset.preset === preset) {
            btn.className = 'preset-btn px-3 py-1.5 rounded text-sm font-medium border border-blue-500 bg-blue-500 text-white transition-colors';
        } else {
            btn.className = 'preset-btn px-3 py-1.5 rounded text-sm font-medium border border-gray-300 hover:bg-blue-50 transition-colors';
        }
    });
}

function buildQueryParams(extra) {
    const params = new URLSearchParams();
    if (currentPreset) {
        params.set('preset', currentPreset);
    } else if (currentMonth && currentYear) {
        params.set('month', currentMonth);
        params.set('year', currentYear);
    }
    if (extra) {
        Object.entries(extra).forEach(([k, v]) => {
            if (v !== null && v !== undefined) params.set(k, v);
        });
    }
    return params.toString();
}

// ==================== Data Loading ====================

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

function loadData() {
    if (currentPage === 'overview') {
        loadOverview();
    } else if (currentPage === 'categories') {
        loadCategories();
    } else if (currentPage === 'budget') {
        if (typeof loadBudget === 'function') loadBudget();
    }
}

async function loadOverview() {
    try {
        const qs = buildQueryParams();
        const [overview, catData] = await Promise.all([
            fetchJSON('/dashboard/api/overview?' + qs),
            fetchJSON('/dashboard/api/category-breakdown?' + qs + '&direction=debit')
        ]);

        updateKPIs(overview.stats, overview.savings_total);
        updateDateDisplay(overview.start_date, overview.end_date);
        renderMonthlyTrend(overview.trend);
        renderSavingsFlow(overview.savings);
        renderOverviewDonut(catData.breakdown);
    } catch (err) {
        console.error('Failed to load overview:', err);
    }
}

async function loadCategories() {
    try {
        const qs = buildQueryParams({ direction: currentDirection });
        const data = await fetchJSON('/dashboard/api/category-breakdown?' + qs);

        updateDateDisplay(null, null);
        renderCatDonut(data.breakdown);
        renderCatBar(data.breakdown);
        renderCatTable(data.breakdown);
    } catch (err) {
        console.error('Failed to load categories:', err);
    }
}

// ==================== KPI Cards ====================

function updateKPIs(stats, savings) {
    const el = (id) => document.getElementById(id);
    if (el('kpiIncome'))   el('kpiIncome').textContent   = formatCurrency(stats.total_income || 0);
    if (el('kpiExpenses')) el('kpiExpenses').textContent = formatCurrency(stats.total_expenses || 0);

    const netEl = el('kpiNet');
    if (netEl) {
        const net = stats.net || 0;
        netEl.textContent = formatCurrency(net);
        netEl.className = 'text-2xl font-bold ' + (net >= 0 ? 'text-blue-600' : 'text-orange-600');
    }

    const savEl = el('kpiSavings');
    if (savEl && savings) {
        savEl.textContent = formatCurrency(savings.net_savings || 0);
        savEl.className = 'text-2xl font-bold ' + ((savings.net_savings || 0) >= 0 ? 'text-purple-600' : 'text-orange-600');
    }
    const detEl = el('kpiSavingsDetail');
    if (detEl && savings) {
        detEl.textContent = `In: ${formatCurrency(savings.savings_in || 0)} — Uit: ${formatCurrency(savings.savings_out || 0)}`;
    }
}

function updateDateDisplay(startDate, endDate) {
    const el = document.getElementById('dateRangeDisplay');
    if (!el) return;
    if (startDate && endDate) {
        el.textContent = `${startDate} t/m ${endDate}`;
    } else if (startDate) {
        el.textContent = `Vanaf ${startDate}`;
    } else {
        el.textContent = 'Alle data';
    }
}

// ==================== Chart: Monthly Trend ====================

function renderMonthlyTrend(trend) {
    const container = document.getElementById('monthlyTrendChart');
    const empty = document.getElementById('monthlyTrendEmpty');
    if (!container) return;

    if (!trend || trend.length === 0) {
        container.style.display = 'none';
        if (empty) empty.classList.remove('hidden');
        return;
    }
    container.style.display = '';
    if (empty) empty.classList.add('hidden');

    if (chartMonthlyTrend) chartMonthlyTrend.destroy();

    const labels = trend.map(d => formatMonth(d.year, d.month));

    chartMonthlyTrend = new ApexCharts(container, {
        chart: { type: 'bar', height: 350, toolbar: { show: false },
                 fontFamily: 'inherit' },
        series: [
            { name: 'Inkomsten', type: 'bar', data: trend.map(d => d.income) },
            { name: 'Uitgaven',  type: 'bar', data: trend.map(d => d.expenses) },
            { name: 'Netto',     type: 'line', data: trend.map(d => d.net) }
        ],
        colors: ['#22c55e', '#ef4444', '#3b82f6'],
        xaxis: { categories: labels },
        yaxis: {
            labels: { formatter: v => formatCurrency(v) }
        },
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        plotOptions: {
            bar: { columnWidth: '60%', borderRadius: 3 }
        },
        stroke: { width: [0, 0, 3] },
        legend: { position: 'top' },
        dataLabels: { enabled: false }
    });
    chartMonthlyTrend.render();
}

// ==================== Chart: Savings Flow ====================

function renderSavingsFlow(savings) {
    const container = document.getElementById('savingsFlowChart');
    const empty = document.getElementById('savingsFlowEmpty');
    if (!container) return;

    if (!savings || savings.length === 0) {
        container.style.display = 'none';
        if (empty) empty.classList.remove('hidden');
        return;
    }
    container.style.display = '';
    if (empty) empty.classList.add('hidden');

    if (chartSavingsFlow) chartSavingsFlow.destroy();

    const labels = savings.map(d => formatMonth(d.year, d.month));

    chartSavingsFlow = new ApexCharts(container, {
        chart: { type: 'bar', height: 300, stacked: true, toolbar: { show: false },
                 fontFamily: 'inherit' },
        series: [
            { name: 'Naar sparen', type: 'bar', data: savings.map(d => d.savings_in) },
            { name: 'Uit sparen',  type: 'bar', data: savings.map(d => -d.savings_out) },
            { name: 'Netto',       type: 'line', data: savings.map(d => d.net_savings) }
        ],
        colors: ['#a855f7', '#f97316', '#6366f1'],
        xaxis: { categories: labels },
        yaxis: {
            labels: { formatter: v => formatCurrency(v) }
        },
        tooltip: {
            y: { formatter: v => formatCurrency(Math.abs(v)) }
        },
        plotOptions: {
            bar: { columnWidth: '65%', borderRadius: 2 }
        },
        stroke: { width: [0, 0, 3] },
        legend: { position: 'top' },
        dataLabels: { enabled: false }
    });
    chartSavingsFlow.render();
}

// ==================== Chart: Overview Category Donut ====================

function renderOverviewDonut(breakdown) {
    const container = document.getElementById('categoryDonutChart');
    const empty = document.getElementById('categoryDonutEmpty');
    if (!container) return;

    if (!breakdown || breakdown.length === 0) {
        container.style.display = 'none';
        if (empty) empty.classList.remove('hidden');
        return;
    }
    container.style.display = '';
    if (empty) empty.classList.add('hidden');

    if (chartCategoryDonut) chartCategoryDonut.destroy();

    chartCategoryDonut = new ApexCharts(container, {
        chart: { type: 'donut', height: 300, fontFamily: 'inherit',
                 events: {
                     dataPointSelection: function(e, chart, opts) {
                         const cat = breakdown[opts.dataPointIndex];
                         if (cat && cat.category_id) {
                             window.location.href = '/dashboard/categories?direction=debit&preset=' + (currentPreset || '');
                         }
                     }
                 }
        },
        series: breakdown.map(d => d.total),
        labels: breakdown.map(d => d.name),
        colors: breakdown.map(d => d.color),
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        legend: { position: 'bottom', fontSize: '12px' },
        dataLabels: { enabled: false },
        plotOptions: {
            pie: { donut: { size: '55%' } }
        }
    });
    chartCategoryDonut.render();
}

// ==================== Chart: Category Analysis Donut ====================

function renderCatDonut(breakdown) {
    const container = document.getElementById('catDonutChart');
    const empty = document.getElementById('catDonutEmpty');
    if (!container) return;

    if (!breakdown || breakdown.length === 0) {
        container.style.display = 'none';
        if (empty) empty.classList.remove('hidden');
        return;
    }
    container.style.display = '';
    if (empty) empty.classList.add('hidden');

    if (chartCatDonut) chartCatDonut.destroy();

    chartCatDonut = new ApexCharts(container, {
        chart: { type: 'donut', height: 350, fontFamily: 'inherit',
                 events: {
                     dataPointSelection: function(e, chart, opts) {
                         const cat = breakdown[opts.dataPointIndex];
                         if (cat && cat.category_id) {
                             openDrilldown(cat.category_id, cat.name);
                         }
                     }
                 }
        },
        series: breakdown.map(d => d.total),
        labels: breakdown.map(d => d.name),
        colors: breakdown.map(d => d.color),
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        legend: { position: 'bottom', fontSize: '12px' },
        dataLabels: { enabled: false },
        plotOptions: {
            pie: { donut: { size: '55%' } }
        }
    });
    chartCatDonut.render();
}

// ==================== Chart: Category Bar ====================

function renderCatBar(breakdown) {
    const container = document.getElementById('catBarChart');
    const empty = document.getElementById('catBarEmpty');
    if (!container) return;

    if (!breakdown || breakdown.length === 0) {
        container.style.display = 'none';
        if (empty) empty.classList.remove('hidden');
        return;
    }
    container.style.display = '';
    if (empty) empty.classList.add('hidden');

    if (chartCatBar) chartCatBar.destroy();

    chartCatBar = new ApexCharts(container, {
        chart: { type: 'bar', height: 350, toolbar: { show: false },
                 fontFamily: 'inherit',
                 events: {
                     dataPointSelection: function(e, chart, opts) {
                         const cat = breakdown[opts.dataPointIndex];
                         if (cat && cat.category_id) {
                             openDrilldown(cat.category_id, cat.name);
                         }
                     }
                 }
        },
        series: [{ name: 'Totaal', data: breakdown.map(d => d.total) }],
        xaxis: {
            categories: breakdown.map(d => d.name),
            labels: {
                formatter: v => formatCurrency(v),
                style: { fontSize: '11px' }
            }
        },
        yaxis: {
            labels: { style: { fontSize: '11px' } }
        },
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        plotOptions: {
            bar: {
                horizontal: true,
                borderRadius: 3,
                distributed: true
            }
        },
        colors: breakdown.map(d => d.color),
        legend: { show: false },
        dataLabels: { enabled: false }
    });
    chartCatBar.render();
}

// ==================== Category Table ====================

function renderCatTable(breakdown) {
    const tbody = document.getElementById('catTableBody');
    if (!tbody) return;

    if (!breakdown || breakdown.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-gray-400 py-8">Geen data voor deze periode</td></tr>';
        return;
    }

    // Estimate months in period for avg calculation
    const monthCount = Math.max(1, estimateMonths());

    tbody.innerHTML = breakdown.map(cat => `
        <tr class="hover:bg-gray-50 cursor-pointer" onclick="openDrilldown(${cat.category_id}, '${cat.name.replace(/'/g, "\\'")}')">
            <td class="px-4 py-3">
                <span class="inline-block w-3 h-3 rounded-full mr-2" style="background-color: ${cat.color}"></span>
                ${cat.icon ? cat.icon + ' ' : ''}${cat.name}
            </td>
            <td class="text-right px-4 py-3 font-medium">${formatCurrency(cat.total)}</td>
            <td class="text-right px-4 py-3 text-gray-500">${cat.percentage}%</td>
            <td class="text-right px-4 py-3 text-gray-500">${formatCurrency(cat.total / monthCount)}</td>
        </tr>
    `).join('');
}

function estimateMonths() {
    if (currentPreset === 'thismonth') return 1;
    if (currentPreset === 'last3m') return 3;
    if (currentPreset === 'last6m') return 6;
    if (currentPreset === 'last12m') return 12;
    if (currentPreset === 'ytd') {
        return new Date().getMonth() + 1;
    }
    if (currentMonth && currentYear) return 1;
    return 6; // fallback for 'all' — rough estimate
}

// ==================== Drilldown ====================

async function openDrilldown(categoryId, categoryName) {
    const panel = document.getElementById('drilldownPanel');
    const title = document.getElementById('drilldownTitle');
    if (!panel) return;

    panel.classList.remove('hidden');
    if (title) title.textContent = categoryName + ' — Subcategorieën';

    // Scroll into view
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const qs = buildQueryParams({ direction: currentDirection });
        const [subData, trendData] = await Promise.all([
            fetchJSON(`/dashboard/api/subcategory-breakdown/${categoryId}?${qs}`),
            fetchJSON(`/dashboard/api/category-trend/${categoryId}?${qs}`)
        ]);

        renderSubDonut(subData.breakdown);
        renderCatTrendLine(trendData.trend);
    } catch (err) {
        console.error('Failed to load drilldown:', err);
    }
}

function closeDrilldown() {
    const panel = document.getElementById('drilldownPanel');
    if (panel) panel.classList.add('hidden');
    if (chartSubDonut) { chartSubDonut.destroy(); chartSubDonut = null; }
    if (chartCatTrend) { chartCatTrend.destroy(); chartCatTrend = null; }
}

function renderSubDonut(breakdown) {
    const container = document.getElementById('subDonutChart');
    if (!container) return;

    if (chartSubDonut) chartSubDonut.destroy();

    if (!breakdown || breakdown.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400 py-8">Geen subcategorieën</div>';
        return;
    }

    chartSubDonut = new ApexCharts(container, {
        chart: { type: 'donut', height: 300, fontFamily: 'inherit' },
        series: breakdown.map(d => d.total),
        labels: breakdown.map(d => d.name),
        colors: breakdown.map(d => d.color),
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        legend: { position: 'bottom', fontSize: '11px' },
        dataLabels: { enabled: false },
        plotOptions: {
            pie: { donut: { size: '50%' } }
        }
    });
    chartSubDonut.render();
}

function renderCatTrendLine(trend) {
    const container = document.getElementById('catTrendChart');
    if (!container) return;

    if (chartCatTrend) chartCatTrend.destroy();

    if (!trend || trend.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400 py-8">Geen trend data</div>';
        return;
    }

    const labels = trend.map(d => formatMonth(d.year, d.month));

    chartCatTrend = new ApexCharts(container, {
        chart: { type: 'area', height: 300, toolbar: { show: false },
                 fontFamily: 'inherit' },
        series: [{ name: 'Bedrag', data: trend.map(d => d.total) }],
        xaxis: { categories: labels },
        yaxis: {
            labels: { formatter: v => formatCurrency(v) }
        },
        tooltip: {
            y: { formatter: v => formatCurrency(v) }
        },
        colors: ['#6366f1'],
        stroke: { curve: 'smooth', width: 2 },
        fill: {
            type: 'gradient',
            gradient: { opacityFrom: 0.4, opacityTo: 0.05 }
        },
        dataLabels: { enabled: false }
    });
    chartCatTrend.render();
}
