// ===== Category Tree Rendering =====
function renderCategoryTree() {
    if (typeof categoryTreeData === 'undefined') return;
    const container = document.getElementById('categoryTreeContent');
    if (!container) return;

    container.innerHTML = categoryTreeData.map(node => 
        `<div class="category-main mb-3" data-name="${node.name.toLowerCase()}">${renderNode(node, 0)}</div>`
    ).join('');
    
    container.querySelectorAll('.category-option').forEach(el => {
        el.addEventListener('click', () => {
            const catId = el.dataset.id;
            const catPath = el.dataset.path;
            if (catId) handleCategorySelection(catId, catPath);
        });
    });
}

function renderNode(node, depth) {
    const bgColors = ['bg-gray-100', 'bg-gray-50', 'bg-white', 'bg-white'];
    const textClasses = ['font-bold text-gray-800', 'font-medium text-gray-700', 'text-gray-600', 'text-gray-500 text-sm'];
    const safeDepth = Math.min(depth, 3);
    const paddingLeft = 12 + depth * 16;
    const hasChildren = node.children && node.children.length > 0;
    const icon = hasChildren ? '📂' : '<span class="text-gray-400">•</span>';
    const roundedClass = depth === 0 ? 'rounded-t-lg' : '';
    
    let html = `<div class="category-node" data-name="${node.name.toLowerCase()}" data-depth="${depth}">
        <div class="py-1.5 px-3 ${bgColors[safeDepth]} flex items-center gap-2 hover:bg-blue-100 cursor-pointer category-option ${roundedClass}" 
             style="padding-left: ${paddingLeft}px;" data-id="${node.id}" data-path="${node.fullPath}">
            ${icon} <span class="${textClasses[safeDepth]}">${node.name}</span>
        </div>`;
    if (hasChildren) {
        html += `<div class="border-l-2 border-gray-200 ml-4">${node.children.map(child => renderNode(child, depth + 1)).join('')}</div>`;
    }
    return html + '</div>';
}

document.addEventListener('DOMContentLoaded', renderCategoryTree);

// ===== Category Modal =====
function openCategoryModal() {
    document.getElementById('categoryModal').classList.remove('hidden');
    document.getElementById('categoryModal').classList.add('flex');
    document.getElementById('newCategoryName').focus();
}

function closeCategoryModal() {
    document.getElementById('categoryModal').classList.add('hidden');
    document.getElementById('categoryModal').classList.remove('flex');
    document.getElementById('newCategoryName').value = '';
    document.getElementById('parentCategory').value = '';
    document.getElementById('categoryError').classList.add('hidden');
}

async function submitCategory(e) {
    e.preventDefault();
    const name = document.getElementById('newCategoryName').value.trim();
    const parentId = document.getElementById('parentCategory').value;
    const errorDiv = document.getElementById('categoryError');
    
    if (!name) { errorDiv.textContent = 'Please enter a category name'; errorDiv.classList.remove('hidden'); return; }
    
    try {
        const response = await fetch('/api/categories', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, parent_id: parentId || null})
        });
        const data = await response.json();
        if (data.success) {
            const newOption = `<option value="${data.category.id}">${data.category.name}</option>`;
            document.querySelectorAll('.category-select').forEach(select => select.insertAdjacentHTML('beforeend', newOption));
            document.getElementById('parentCategory').insertAdjacentHTML('beforeend', newOption);
            closeCategoryModal();
            showToast(`Category "${data.category.name}" added!`);
        } else {
            errorDiv.textContent = data.error || 'Failed to add category'; errorDiv.classList.remove('hidden');
        }
    } catch (err) { errorDiv.textContent = 'Error adding category.'; errorDiv.classList.remove('hidden'); }
}

// ===== Category Picker =====
let currentTransactionId = null;
let bulkPickerMode = false;

function openCategoryPicker(transId, merchant) {
    currentTransactionId = transId;
    bulkPickerMode = false;
    document.getElementById('pickerMerchant').textContent = merchant || '';
    document.getElementById('categorySearch').value = '';
    document.getElementById('categoryPickerModal').classList.remove('hidden');
    document.getElementById('categoryPickerModal').classList.add('flex');
    filterCategories();
    loadRecentCategories();
    document.getElementById('categorySearch').focus();
}

function openBulkCategoryPicker() {
    bulkPickerMode = true;
    currentTransactionId = null;
    const count = document.getElementById('selectedCount')?.textContent || '0';
    document.getElementById('pickerMerchant').textContent = window.isUncategorizedPage 
        ? `For ${count} selected transactions` 
        : 'Bulk categorization';
    document.getElementById('categorySearch').value = '';
    document.getElementById('categoryPickerModal').classList.remove('hidden');
    document.getElementById('categoryPickerModal').classList.add('flex');
    filterCategories();
    loadRecentCategories();
    document.getElementById('categorySearch').focus();
}

function closeCategoryPicker() {
    document.getElementById('categoryPickerModal').classList.add('hidden');
    document.getElementById('categoryPickerModal').classList.remove('flex');
    currentTransactionId = null;
}

function filterCategories() {
    const search = document.getElementById('categorySearch').value.toLowerCase().trim();
    const container = document.getElementById('categoryTreeContent');
    let anyVisible = false;
    
    function checkNodeVisibility(node) {
        const name = node.dataset.name || '';
        const children = node.querySelectorAll(':scope > .border-l-2 > .category-node');
        let childrenVisible = false;
        children.forEach(child => { if (checkNodeVisibility(child)) childrenVisible = true; });
        const selfMatches = !search || name.includes(search);
        const visible = selfMatches || childrenVisible;
        node.style.display = visible ? '' : 'none';
        if (visible) anyVisible = true;
        return visible;
    }
    
    container.querySelectorAll(':scope > .category-main').forEach(main => {
        const mainNode = main.querySelector(':scope > .category-node');
        if (mainNode) { const visible = checkNodeVisibility(mainNode); main.style.display = visible ? '' : 'none'; }
    });
    document.getElementById('noResults').style.display = anyVisible ? 'none' : 'block';
}

function handleCategorySelection(categoryId, categoryPath) {
    addRecentCategory(categoryId, categoryPath);
    if (bulkPickerMode) {
        document.getElementById('bulkCategoryId').value = categoryId;
        document.getElementById('bulkCategoryLabel').textContent = categoryPath;
        closeCategoryPicker();
        bulkPickerMode = false;
    } else if (currentTransactionId) {
        selectCategory(currentTransactionId, categoryId, categoryPath);
    }
}

async function selectCategory(transId, categoryId, categoryPath) {
    const createRule = document.getElementById(`rule_${transId}`)?.checked || false;
    try {
        const formData = new FormData();
        formData.append('category_id', categoryId);
        if (createRule) formData.append('create_rule', 'on');
        
        const response = await fetch(`/transactions/${transId}/categorize`, { method: 'POST', body: formData });
        if (response.ok) {
            const row = document.querySelector(`.transaction-row[data-id="${transId}"]`);
            if (window.isUncategorizedPage) {
                // On uncategorized page: remove row with animation
                if (row) {
                    row.style.transition = 'opacity 0.3s, transform 0.3s';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(20px)';
                    setTimeout(() => { row.remove(); updateUncategorizedCounts(); }, 300);
                }
            } else {
                // On transactions page: update category button in-place
                if (row) {
                    const catCell = row.querySelector('.category-btn') || row.querySelector('td:nth-child(7) button');
                    if (catCell) {
                        catCell.textContent = categoryPath.length > 20 ? categoryPath.substring(0, 20) + '...' : categoryPath;
                        catCell.classList.remove('border-yellow-300', 'bg-yellow-50', 'hover:bg-yellow-100');
                        catCell.classList.add('border-gray-300', 'bg-white', 'hover:bg-gray-50');
                    }
                }
            }
            closeCategoryPicker();
            showToast(`Categorized as "${categoryPath}"`);
        } else { showToast('Failed to categorize', 'error'); }
    } catch (err) { showToast('Error categorizing transaction', 'error'); }
}

// ===== Recent Categories =====
function loadRecentCategories() {
    const recent = JSON.parse(localStorage.getItem('recentCategories') || '[]');
    const container = document.getElementById('recentCategoriesList');
    const section = document.getElementById('recentCategories');
    if (recent.length === 0) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');
    container.innerHTML = recent.slice(0, 6).map(cat => 
        `<button type="button" onclick="handleCategorySelection('${cat.id}', '${cat.path.replace(/'/g, "\\'")}')" 
                 class="px-3 py-1 bg-blue-50 border border-blue-200 rounded-full text-sm hover:bg-blue-100">${cat.path.split(' → ').pop()}</button>`
    ).join('');
}

function addRecentCategory(id, path) {
    let recent = JSON.parse(localStorage.getItem('recentCategories') || '[]');
    recent = recent.filter(c => c.id !== id);
    recent.unshift({ id, path });
    localStorage.setItem('recentCategories', JSON.stringify(recent.slice(0, 10)));
}

// ===== Selection Handling =====
function toggleSelectAll() {
    const checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.row-checkbox').forEach(cb => {
        if (cb.closest('tr').style.display !== 'none') cb.checked = checked;
    });
    updateSelection();
}

function updateSelection() {
    const selected = document.querySelectorAll('.row-checkbox:checked').length;
    document.getElementById('selectedCount').textContent = selected;
    document.getElementById('bulkSelectedPanel').classList.toggle('hidden', selected === 0);
    const allVisible = document.querySelectorAll('.transaction-row:not([style*="display: none"]) .row-checkbox');
    const allChecked = allVisible.length > 0 && Array.from(allVisible).every(cb => cb.checked);
    document.getElementById('selectAll').checked = allChecked;
}

function clearSelection() {
    document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('selectAll').checked = false;
    document.getElementById('bulkCategoryId').value = '';
    document.getElementById('bulkCategoryLabel').textContent = 'Select Category';
    updateSelection();
}

async function bulkCategorizeSelected() {
    const categoryId = document.getElementById('bulkCategoryId').value;
    const categoryLabel = document.getElementById('bulkCategoryLabel').textContent;
    const createRule = document.getElementById('bulkCreateRule').checked;
    if (!categoryId || categoryLabel === 'Select Category') { showToast('Please select a category first', 'error'); return; }
    
    const selectedIds = Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) { showToast('No transactions selected', 'error'); return; }
    
    try {
        const response = await fetch('/bulk-categorize-selected', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ transaction_ids: selectedIds, category_id: categoryId, create_rule: createRule })
        });
        const data = await response.json();
        if (data.success) {
            if (window.isUncategorizedPage) {
                // Remove rows with animation on uncategorized page
                selectedIds.forEach(id => {
                    const row = document.querySelector(`.transaction-row[data-id="${id}"]`);
                    if (row) {
                        row.style.transition = 'opacity 0.3s';
                        row.style.opacity = '0';
                        setTimeout(() => row.remove(), 300);
                    }
                });
                setTimeout(() => { clearSelection(); updateUncategorizedCounts(); }, 350);
            } else {
                // Update buttons in-place on transactions page
                selectedIds.forEach(id => {
                    const row = document.querySelector(`.transaction-row[data-id="${id}"]`);
                    if (row) {
                        const catCell = row.querySelector('.category-btn') || row.querySelector('td:nth-child(7) button');
                        if (catCell) {
                            catCell.textContent = categoryLabel.length > 20 ? categoryLabel.substring(0, 20) + '...' : categoryLabel;
                            catCell.classList.remove('border-yellow-300', 'bg-yellow-50', 'hover:bg-yellow-100');
                            catCell.classList.add('border-gray-300', 'bg-white', 'hover:bg-gray-50');
                        }
                    }
                });
                clearSelection();
            }
            showToast(`Categorized ${data.count} transactions as "${categoryLabel}"`);
        } else { showToast(data.error || 'Failed to categorize', 'error'); }
    } catch (err) { showToast('Error categorizing transactions', 'error'); }
}

// ===== Uncategorized Page Helpers =====
function updateUncategorizedCounts() {
    const remaining = document.querySelectorAll('.transaction-row').length;
    const header = document.querySelector('h2 + p');
    if (header) {
        if (remaining === 0) {
            header.textContent = 'All transactions are categorized! 🎉';
            setTimeout(() => location.reload(), 1000);
        } else {
            header.textContent = `${remaining} transaction(s) need categorization`;
        }
    }
}

// ===== Notes Editing =====
function editNotes(span) {
    const cell = span.closest('.notes-cell');
    const input = cell.querySelector('.notes-input');
    input.dataset.original = input.value;
    span.classList.add('hidden');
    input.classList.remove('hidden');
    input.focus();
    input.select();
}

async function saveNotes(input) {
    const cell = input.closest('.notes-cell');
    const span = cell.querySelector('.notes-display');
    const id = cell.dataset.id;
    const notes = input.value.trim();
    input.classList.add('hidden');
    span.classList.remove('hidden');
    span.textContent = notes ? (notes.length > 15 ? notes.substring(0, 15) + '...' : notes) : '📝';
    try {
        const formData = new FormData();
        formData.append('notes', notes);
        await fetch(`/transactions/${id}/notes`, { method: 'POST', body: formData });
    } catch (err) { span.textContent = input.dataset.original || '📝'; input.value = input.dataset.original || ''; }
}

// ===== Transaction Type Cycling =====
async function cycleTransactionType(transId, btn) {
    const types = ['Debit', 'Credit'];
    const typeValues = { 'Debit': 'debit', 'Credit': 'credit' };
    const colors = { 'Debit': ['bg-red-100', 'text-red-700'], 'Credit': ['bg-green-100', 'text-green-700'] };
    const currentType = btn.textContent.trim();
    const newType = types[(types.indexOf(currentType) + 1) % types.length];
    
    try {
        const response = await fetch(`/transactions/${transId}/type`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ type: typeValues[newType] })
        });
        const data = await response.json();
        if (data.success) {
            btn.textContent = newType;
            btn.classList.remove(...Object.values(colors).flat());
            btn.classList.add(...colors[newType]);
            const row = btn.closest('tr');
            const amountCell = row.querySelector('td:last-child');
            amountCell.classList.remove('text-green-600', 'text-red-600');
            amountCell.classList.add(newType === 'Credit' ? 'text-green-600' : 'text-red-600');
            showToast(`Direction changed to ${newType}`, 'success');
        } else { showToast('Failed to update direction', 'error'); }
    } catch (err) { showToast('Failed to update direction', 'error'); }
}

// ===== Toggle Transfer =====
async function toggleTransfer(transId, checkbox) {
    if (checkbox.disabled) return;
    checkbox.disabled = true;
    const wantTransfer = checkbox.checked;
    try {
        const response = await fetch(`/transactions/${transId}/toggle-transfer`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ is_transfer: wantTransfer })
        });
        const data = await response.json();
        if (data.success) {
            checkbox.checked = !!data.is_transfer;
            showToast(data.is_transfer ? 'Marked as transfer' : 'Unmarked as transfer', 'success');
        } else {
            checkbox.checked = !checkbox.checked;
            showToast('Failed to toggle transfer status', 'error');
        }
    } catch (err) {
        checkbox.checked = !checkbox.checked;
        showToast('Failed to toggle transfer status', 'error');
    } finally {
        checkbox.disabled = false;
    }
}

// ===== Toggle Incidental =====
async function toggleIncidental(transId, checkbox) {
    const isIncidental = checkbox.checked ? 1 : 0;
    try {
        const response = await fetch(`/transactions/${transId}/toggle_incidental`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ is_incidental: isIncidental })
        });
        const data = await response.json();
        if (!data.success) {
            checkbox.checked = !checkbox.checked;
            showToast(data.error || 'Failed to update status', 'error');
        }
    } catch (err) {
        checkbox.checked = !checkbox.checked;
        showToast('Error connecting to server', 'error');
    }
}

// ===== Toast Notification =====
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${type === 'error' ? 'bg-red-500' : 'bg-green-500'} text-white`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ===== Event Listeners =====
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeCategoryModal(); closeCategoryPicker(); } });
document.getElementById('categoryModal')?.addEventListener('click', e => { if (e.target.id === 'categoryModal') closeCategoryModal(); });
document.getElementById('categoryPickerModal')?.addEventListener('click', e => { if (e.target.id === 'categoryPickerModal') closeCategoryPicker(); });
