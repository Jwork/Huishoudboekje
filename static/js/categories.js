document.addEventListener('DOMContentLoaded', () => {
    // Bind toggle buttons
    const toggleButtons = document.querySelectorAll('.toggle-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            const catId = btn.getAttribute('data-cat-id');
            toggleCategory(catId);
        });
    });
    
    // Intercept form submission
    const form = document.getElementById('addCategoryForm');
    if (form) {
        form.addEventListener('submit', handleCategorySubmit);
    }
});

function toggleCategory(catId) {
    const childrenContainer = document.getElementById('category-children-' + catId);
    
    if (childrenContainer) {
        const isHidden = childrenContainer.classList.contains('collapsed');
        childrenContainer.classList.toggle('collapsed');
        
        const toggle = document.querySelector('[data-cat-id="' + catId + '"]');
        if (toggle) {
            toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
        }
    }
}

function setupAddSubcategory(parentId, parentName) {
    // parentName is now passed via getAttribute('data-name') so it's already HTML-safe
    // Set parent in select box
    const select = document.getElementById('parentSelect');
    if (select) {
        select.value = parentId;
        // If the value wasn't found (e.g. if select doesn't have it), default to empty
        if (select.value != parentId) select.value = ""; 
    }
    
    // Focus name input
    const input = document.getElementById('categoryNameInput');
    if (input) {
        input.value = "";
        input.focus();
    }

    // Clear icon input
    const iconInput = document.getElementById('categoryIconInput');
    if (iconInput) {
        iconInput.value = "";
    }
    
    // Scroll to form (top of white box)
    const formContainer = document.querySelector('.bg-white');
    if (formContainer) {
        const top = formContainer.getBoundingClientRect().top + window.scrollY - 20;
        window.scrollTo({ top: top, behavior: 'smooth' });
    }
}

async function handleCategorySubmit(e) {
    e.preventDefault();
    
    const nameInput = document.getElementById('categoryNameInput');
    const iconInput = document.getElementById('categoryIconInput');
    const parentSelect = document.getElementById('parentSelect');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    const name = nameInput.value.trim();
    const icon = iconInput ? iconInput.value.trim() : null;
    const parentId = parentSelect.value;
    
    if (!name) return; 
    
    // Disable button to prevent double submit
    const originalBtnText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Adding...";
    
    try {
        const response = await fetch('/api/categories', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                parent_id: parentId || null,
                icon: icon
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Category "${name}" added!`);
            
            // Add to DOM
            addCategoryToDom(data.category.id, name, parentId, icon);
            
            // Add to Select Dropdown
            addCategoryToSelect(data.category.id, name, parentId);
            
            // Reset Name and Icon only (keep parent selected for quick multi-add)
            nameInput.value = "";
            if (iconInput) iconInput.value = "";
            nameInput.focus();
            
        } else {
            showToast(data.error || "Failed to add category", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Error connecting to server", "error");
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
    }
}

function addCategoryToDom(id, name, parentId, icon) {
    // Determine depth and container
    let depth = 0;
    let parentContainer = document.getElementById('category-tree-root');
    
    if (parentId) {
        const parentNode = document.getElementById(`category-node-${parentId}`);
        if (parentNode) {
            // Get depth from parent
            depth = (parseInt(parentNode.dataset.depth) || 0) + 1;
            
            // Check if children container exists
            let childrenContainer = document.getElementById(`category-children-${parentId}`);
            if (!childrenContainer) {
                // Create children container with category-children class for toggle functionality
                childrenContainer = document.createElement('div');
                childrenContainer.id = `category-children-${parentId}`;
                childrenContainer.className = "category-children ml-4 space-y-1";
                parentNode.appendChild(childrenContainer);
                
                // Update parent to show it has children - add toggle button
                const titleDiv = parentNode.querySelector('.category-title-area');
                if (titleDiv) {
                    // Find the empty span placeholder and replace with toggle button
                    const placeholder = titleDiv.querySelector('span.w-6');
                    if (placeholder && placeholder.textContent.trim() === '') {
                        const toggleBtn = document.createElement('button');
                        toggleBtn.type = 'button';
                        toggleBtn.className = 'text-gray-600 hover:text-gray-800 text-lg leading-none expand-toggle w-6 toggle-btn';
                        toggleBtn.setAttribute('data-cat-id', parentId);
                        toggleBtn.setAttribute('title', 'Toggle');
                        toggleBtn.textContent = '▼';
                        toggleBtn.addEventListener('click', (event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            toggleCategory(parentId);
                        });
                        placeholder.replaceWith(toggleBtn);
                    }
                }
                
                // Update parent icon to folder if no custom icon
                const iconSpan = parentNode.querySelector('.category-icon');
                if (iconSpan && iconSpan.textContent.trim() === '📄') {
                     iconSpan.textContent = "📁";
                }
            }
            parentContainer = childrenContainer;
        }
    }
    
    // Style configurations matching the Jinja template
    const indentColors = ['bg-white border', 'bg-gray-50', 'bg-gray-100', 'bg-gray-200'];
    const textSizes = ['text-lg font-bold', 'font-medium text-gray-700', 'text-gray-600 text-sm', 'text-gray-500 text-xs'];
    const deleteColors = ['text-red-500 hover:text-red-700', 'text-red-400 hover:text-red-600', 'text-red-300 hover:text-red-500', 'text-red-300 hover:text-red-500'];
    
    const safeDepth = Math.min(depth, 3);
    
    const newNode = document.createElement('div');
    newNode.className = `${indentColors[safeDepth]} rounded-lg p-${safeDepth < 3 ? 4 - safeDepth : 2} ${depth > 0 ? 'mt-2' : ''}`;
    newNode.id = `category-node-${id}`;
    newNode.dataset.depth = depth;
    
    // Determine icon to display
    const displayIcon = icon ? icon : '📄';
    
    // Inner HTML - matches template structure with toggle button placeholder
    newNode.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 ${textSizes[safeDepth]} category-title-area">
                <span class="w-6"></span>
                <span class="category-icon">${displayIcon}</span> ${name}
                <button type="button" onclick="setupAddSubcategory(${id}, this.getAttribute('data-name'))" data-name="${name.replace(/"/g, '&quot;')}" 
                        class="text-blue-500 hover:text-blue-700 ml-2 text-xs opacity-50 hover:opacity-100 transition-opacity" title="Add Subcategory">
                    ➕
                </button>
            </div>
            <form method="post" action="/categories/${id}/delete" 
                  onsubmit="return confirm('⚠️ Delete \\"${name}\\"?');">
                <button type="submit" class="${deleteColors[safeDepth]} text-xs px-2 py-0.5 hover:bg-red-50 rounded" title="Delete">
                    🗑️${depth === 0 ? ' Delete' : ''}
                </button>
            </form>
        </div>
    `;
    
    parentContainer.appendChild(newNode);
}

function addCategoryToSelect(id, name, parentId) {
    const select = document.getElementById('parentSelect');
    if (!select) return;

    let depth = 0;
    if (parentId) {
        const parentOption = select.querySelector(`option[value="${parentId}"]`);
        if (parentOption) {
            const match = parentOption.text.match(/^(—*)\s/);
            if (match) {
                depth = match[1].length + 1;
            } else {
                depth = 1;
            }
        }
    }
    
    const option = document.createElement('option');
    option.value = id;
    option.text = '—'.repeat(depth) + ' ' + name;
    
    // Append to end
    select.appendChild(option);
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${type === 'error' ? 'bg-red-500' : 'bg-green-500'} text-white transition-opacity duration-300`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Fade in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
    });

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== Inline Rename =====
function startRename(catId, spanEl) {
    // Prevent double-activation
    if (spanEl.querySelector('input')) return;
    
    const currentName = spanEl.textContent.trim();
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'px-2 py-0.5 border border-blue-400 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none';
    input.style.minWidth = '120px';
    
    spanEl.textContent = '';
    spanEl.appendChild(input);
    input.focus();
    input.select();
    
    const commit = () => saveRename(catId, spanEl, input, currentName);
    
    input.addEventListener('blur', commit, { once: true });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            input.removeEventListener('blur', commit);
            spanEl.textContent = currentName;
        }
    });
}

async function saveRename(catId, spanEl, input, oldName) {
    const newName = input.value.trim();
    
    // No change or empty — revert
    if (!newName || newName === oldName) {
        spanEl.textContent = oldName;
        return;
    }
    
    // Optimistic update
    spanEl.textContent = newName;
    
    try {
        const resp = await fetch(`/api/categories/${catId}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        const data = await resp.json();
        
        if (data.success) {
            showToast(`Renamed to "${newName}"`);
            // Update the add-subcategory button's data-name
            const addBtn = spanEl.closest('.category-title-area')?.querySelector('[data-name]');
            if (addBtn) addBtn.setAttribute('data-name', newName);
            // Update the select dropdown option text
            const option = document.querySelector(`#parentSelect option[value="${catId}"]`);
            if (option) {
                const prefix = option.text.match(/^(—*\s*)/)?.[1] || '';
                option.text = prefix + newName;
            }
        } else {
            spanEl.textContent = oldName;
            showToast(data.error || 'Rename failed', 'error');
        }
    } catch (err) {
        spanEl.textContent = oldName;
        showToast('Error connecting to server', 'error');
    }
}

// ===== Inline Rename =====
function startRename(catId, spanEl) {
    // Prevent double-activation
    if (spanEl.querySelector('input')) return;
    
    const currentName = spanEl.textContent.trim();
    const originalHTML = spanEl.innerHTML;
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'px-2 py-0.5 border border-blue-400 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none';
    input.style.minWidth = '120px';
    
    spanEl.textContent = '';
    spanEl.appendChild(input);
    input.focus();
    input.select();
    
    const commit = () => saveRename(catId, spanEl, input, currentName);
    
    input.addEventListener('blur', commit, { once: true });
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            input.blur();  // triggers the blur→commit
        } else if (e.key === 'Escape') {
            e.preventDefault();
            input.removeEventListener('blur', commit);
            spanEl.textContent = currentName;
        }
    });
}

async function saveRename(catId, spanEl, input, oldName) {
    const newName = input.value.trim();
    
    // No change or empty → revert
    if (!newName || newName === oldName) {
        spanEl.textContent = oldName;
        return;
    }
    
    // Optimistic update
    spanEl.textContent = newName;
    
    try {
        const resp = await fetch(`/api/categories/${catId}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        const data = await resp.json();
        
        if (data.success) {
            showToast(`Renamed to "${newName}"`);
            // Update the add-subcategory button's data-name attribute
            const addBtn = spanEl.closest('.category-title-area')?.querySelector('[data-name]');
            if (addBtn) addBtn.setAttribute('data-name', newName);
            // Update the select dropdown option text
            const option = document.querySelector(`#parentSelect option[value="${catId}"]`);
            if (option) {
                const prefix = option.text.match(/^(—*\s*)/)?.[1] || '';
                option.text = prefix + newName;
            }
        } else {
            spanEl.textContent = oldName;
            showToast(data.error || 'Rename failed', 'error');
        }
    } catch (err) {
        spanEl.textContent = oldName;
        showToast('Error connecting to server', 'error');
    }
}