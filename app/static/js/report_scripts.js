// app/static/js/report_scripts.js

/**
 * Handles all backend communication for reports
 */
class ReportAPIAdapter {
    constructor(csrfToken) {
        this.csrfToken = csrfToken;
    }

    async saveReport(actionUrl, payload) {
        try {
            const response = await fetch(actionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                window.location.reload();
            } else {
                alert('儲存失敗：' + result.message);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('儲存時發生網路錯誤，請稍後再試。');
        }
    }
}

/**
 * Manages DOM interactions, rendering, and localized formatting for the report interface
 */
class ReportUIManager {
    constructor(tableContainer, reportType, allCategories) {
        this.tableContainer = tableContainer;
        this.reportType = reportType;
        this.allCategories = allCategories;
        
        this.categoryTypeMap = this.allCategories.reduce((map, c) => {
            map[c.id] = c.category_type;
            return map;
        }, {});

        this.editBtn = document.querySelector('.edit-button');
        this.saveBtn = document.querySelector('.save-button');
        this.cancelBtn = document.querySelector('.cancel-button');
    }

    getCleanNumber(str) {
        if (typeof str !== 'string') return str || 0;
        return parseFloat(str.replace(/[^0-9.-]/g, '')) || 0;
    }

    formatAsCurrency(number) {
        return `$${new Intl.NumberFormat('en-US').format(Math.round(number))}`;
    }

    formatAsNumber(number) {
        return Math.round(number).toLocaleString('en-US');
    }
    
    getNumericValue(element) {
        if (!element) return 0;
        const text = element.innerText.replace(/[^0-9.-]/g, '');
        return parseFloat(text) || 0;
    }

    toggleEditMode(isEditing) {
        const isEditableReport = ['daily_summary', 'daily_cash_check', 'transaction_log'].includes(this.reportType);
        
        if (this.editBtn) this.editBtn.style.display = (isEditableReport && !isEditing) ? 'inline-block' : 'none';
        if (this.saveBtn) this.saveBtn.style.display = isEditing ? 'inline-block' : 'none';
        if (this.cancelBtn) this.cancelBtn.style.display = isEditing ? 'inline-block' : 'none';
        
        if (this.tableContainer) {
            this.tableContainer.classList.toggle('editing', isEditing);
        }
    }

    // --- Row Update Domain Logic ---

    updateDailySummaryRow(row) {
        const openingCashInput = row.querySelector('[data-field="opening_cash"] .editable-input');
        if (!openingCashInput) return;
        const openingCash = this.getCleanNumber(openingCashInput.value);
        const totalSales = this.getNumericValue(row.querySelector('[data-field="total_sales"]'));
        const closingCash = this.getNumericValue(row.querySelector('[data-field="closing_cash"]'));
        
        const expectedCash = openingCash + totalSales;
        const cashDiff = closingCash - expectedCash;
        
        const expCell = row.querySelector('[data-field="expected_cash"]');
        if (expCell) expCell.innerText = this.formatAsCurrency(expectedCash);
        
        const cashDiffCell = row.querySelector('[data-field="cash_diff"]');
        if (cashDiffCell) {
            cashDiffCell.innerText = this.formatAsCurrency(cashDiff);
            cashDiffCell.classList.toggle('text-danger', cashDiff < 0);
        }
    }
    
    updateTransactionLogRow(row) {
        const transactionRows = this.tableContainer.querySelectorAll(`tr[data-id="${row.dataset.id}"]`);
        let newTransactionAmount = 0;
        transactionRows.forEach(transRow => {
            const itemPriceInput = transRow.querySelector('[data-item-id] .editable-input');
            if (itemPriceInput) {
                newTransactionAmount += this.getCleanNumber(itemPriceInput.value);
            }
        });

        const transactionAmountCell = row.querySelector('[data-field="amount"]');
        if (transactionAmountCell) {
            transactionAmountCell.innerText = this.formatAsCurrency(newTransactionAmount);
        }

        if (transactionRows.length > 0) {
            const firstRow = transactionRows[0];
            const cashReceivedInput = firstRow.querySelector('[data-field="cash_received"] .editable-input');
            if (cashReceivedInput) {
                const cashReceived = this.getCleanNumber(cashReceivedInput.value);
                const changeGiven = cashReceived - newTransactionAmount;
                const changeGivenCell = firstRow.querySelector('[data-field="change_given"]');
                if (changeGivenCell) {
                    changeGivenCell.innerText = this.formatAsCurrency(changeGiven);
                }
            }
        }
    }

    updateDailyCashCheckRow(row) {
        let closingCash = 0;
        row.querySelectorAll('.cash-breakdown-input').forEach(input => {
            const denom = this.getCleanNumber(input.dataset.denom);
            const count = this.getCleanNumber(input.value);
            closingCash += denom * count;
        });
        
        const closingCashDisplay = row.querySelector('.closing_cash_display');
        if (closingCashDisplay) {
            closingCashDisplay.innerText = `NT$ ${this.formatAsNumber(closingCash)}`;
        }
        
        const grandTotalRow = document.querySelector('.fw-bold.table-secondary');
        if (grandTotalRow) {
            let grandClosingCash = 0;
            this.tableContainer.querySelectorAll('tr[data-id]').forEach(dataRow => {
                const dataRowClosingCash = this.getCleanNumber(dataRow.querySelector('.closing_cash_display').innerText);
                grandClosingCash += dataRowClosingCash;
            });
            
            const grandTotalClosingCashCell = grandTotalRow.querySelector('td.closing_cash_display');
            if (grandTotalClosingCashCell) {
                grandTotalClosingCashCell.innerText = `NT$ ${this.formatAsNumber(grandClosingCash)}`;
            }
            
            this.tableContainer.querySelectorAll('.cash-breakdown-input').forEach(input => {
                const denom = input.dataset.denom;
                let denomTotal = 0;
                this.tableContainer.querySelectorAll(`tr[data-id] .cash-breakdown-input[data-denom="${denom}"]`).forEach(denomInput => {
                    denomTotal += this.getCleanNumber(denomInput.value);
                });
                const totalCell = grandTotalRow.querySelector(`[data-denom-total="${denom}"]`);
                if (totalCell) {
                    totalCell.innerText = this.formatAsNumber(denomTotal);
                }
            });
        }
    }

    updateRowByType(row) {
        if (this.reportType === 'daily_summary') this.updateDailySummaryRow(row);
        if (this.reportType === 'transaction_log') this.updateTransactionLogRow(row);
        if (this.reportType === 'daily_cash_check') this.updateDailyCashCheckRow(row);
    }
}

/**
 * Controller orchestrating interaction between the UI Manager, API Adapter, and raw Data state
 */
class ReportController {
    constructor() {
        this.tableContainer = document.querySelector('.table-responsive');
        if (!this.tableContainer) return;

        this.reportType = this.tableContainer.dataset.reportType;
        const allCategoriesJson = document.querySelector('script[type="application/json"]#all-categories-data');
        this.allCategories = allCategoriesJson ? JSON.parse(allCategoriesJson.textContent) : [];

        const tokenNode = document.querySelector('[name="csrf_token"]');
        this.api = new ReportAPIAdapter(tokenNode ? tokenNode.value : '');
        this.ui = new ReportUIManager(this.tableContainer, this.reportType, this.allCategories);
        
        this.editableForm = document.getElementById(`editable-form-${this.reportType}`);

        this.bindEvents();
        this.ui.toggleEditMode(false);
        console.log(`[ReportController] Object-Oriented Report System Initialized for: ${this.reportType}`);
    }

    bindEvents() {
        if (this.ui.editBtn) {
            this.ui.editBtn.addEventListener('click', () => this.handleEdit());
        }

        if (this.ui.cancelBtn) {
            this.ui.cancelBtn.addEventListener('click', () => this.handleCancel());
        }

        if (this.editableForm) {
            this.editableForm.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        this.tableContainer.addEventListener('input', (e) => this.handleInput(e));
        this.tableContainer.addEventListener('change', (e) => this.handleChange(e));
    }

    handleEdit() {
        const originalData = {};
        this.tableContainer.querySelectorAll('tr[data-id]').forEach(row => {
            const rowId = row.dataset.id;
            
            if (!originalData[rowId]) {
                originalData[rowId] = { id: rowId, items: [] };
            }

            if (this.reportType === 'transaction_log') {
                const cashReceivedElement = row.querySelector('[data-field="cash_received"] .display-value');
                const changeGivenElement = row.querySelector('[data-field="change_given"] .display-value');
                if (cashReceivedElement) originalData[rowId].cash_received = this.ui.getCleanNumber(cashReceivedElement.innerText);
                if (changeGivenElement) originalData[rowId].change_given = this.ui.getCleanNumber(changeGivenElement.innerText);
                
                const itemPriceCell = row.querySelector('[data-field="item_price"]');
                const categoryCell = row.querySelector('[data-field="category"]');
                if (itemPriceCell && categoryCell) {
                    originalData[rowId].items.push({
                        id: itemPriceCell.dataset.itemId,
                        price: this.ui.getCleanNumber(itemPriceCell.querySelector('.display-value').innerText),
                        category_id: categoryCell.dataset.categoryId
                    });
                }
            } else if (this.reportType === 'daily_summary') {
                const openingCashCell = row.querySelector('[data-field="opening_cash"]');
                if (openingCashCell) {
                    originalData[rowId].opening_cash = this.ui.getCleanNumber(openingCashCell.querySelector('.display-value').innerText);
                }
            } else if (this.reportType === 'daily_cash_check') {
                if (!originalData[rowId].cash_breakdown) originalData[rowId].cash_breakdown = {};
                row.querySelectorAll('.cash-breakdown-input').forEach(input => {
                    originalData[rowId].cash_breakdown[input.dataset.denom] = this.ui.getCleanNumber(input.value);
                });
            }
        });

        this.tableContainer.dataset.originalData = JSON.stringify(originalData);

        this.tableContainer.querySelectorAll('.editable-cell').forEach(cell => {
            const displayValueElement = cell.querySelector('.display-value');
            const editableElement = cell.querySelector('.editable-input, .editable-select');
            if (editableElement && displayValueElement) {
                if (editableElement.tagName === 'SELECT') {
                    editableElement.value = cell.dataset.categoryId;
                } else {
                    let rawValue = displayValueElement.innerText.replace('NT$','').replace('$','');
                    editableElement.value = this.ui.getCleanNumber(rawValue);
                }
            }
        });
        this.ui.toggleEditMode(true);
    }

    handleCancel() {
        const originalDataStr = this.tableContainer.dataset.originalData;
        if (!originalDataStr) return;
        
        const originalData = JSON.parse(originalDataStr);
        
        this.tableContainer.querySelectorAll('tr[data-id]').forEach(row => {
            const rowId = row.dataset.id;
            const originalTransactionData = originalData[rowId];
            if (!originalTransactionData) return;

            if (this.reportType === 'transaction_log') {
                const cashRecvCell = row.querySelector('[data-field="cash_received"]');
                if (cashRecvCell) {
                    cashRecvCell.querySelector('.editable-input').value = originalTransactionData.cash_received;
                    cashRecvCell.querySelector('.display-value').innerText = this.ui.formatAsCurrency(originalTransactionData.cash_received);
                }
                const changeCell = row.querySelector('[data-field="change_given"]');
                if (changeCell) changeCell.innerText = this.ui.formatAsCurrency(originalTransactionData.change_given);

                const itemPriceCell = row.querySelector('[data-item-id]');
                const categoryCell = row.querySelector('[data-field="category"]');
                if (itemPriceCell && categoryCell) {
                    const itemId = itemPriceCell.dataset.itemId;
                    const originalItemData = originalTransactionData.items.find(item => item.id == itemId);
                    if (originalItemData) {
                        itemPriceCell.querySelector('.editable-input').value = originalItemData.price;
                        itemPriceCell.querySelector('.display-value').innerText = this.ui.formatAsCurrency(originalItemData.price);

                        const select = categoryCell.querySelector('.editable-select');
                        select.value = originalItemData.category_id;
                        const catName = this.allCategories.find(c => c.id == originalItemData.category_id)?.name || '手動輸入';
                        categoryCell.querySelector('.display-value').innerText = catName;
                        categoryCell.dataset.categoryId = originalItemData.category_id;

                        const itemTypeCell = categoryCell.closest('tr').querySelector('td:nth-child(4) .badge');
                        const itemType = this.ui.categoryTypeMap[originalItemData.category_id];
                        if (itemTypeCell && itemType) {
                            if (itemType.includes('discount')) {
                                itemTypeCell.className = "badge bg-danger rounded-pill";
                                itemTypeCell.innerText = '折扣';
                            } else {
                                itemTypeCell.className = "badge bg-success rounded-pill";
                                itemTypeCell.innerText = '商品';
                            }
                        }
                    }
                }
            } else if (this.reportType === 'daily_summary') {
                const cell = row.querySelector('[data-field="opening_cash"]');
                if (cell) {
                    cell.querySelector('.editable-input').value = originalTransactionData.opening_cash;
                    cell.querySelector('.display-value').innerText = this.ui.formatAsCurrency(originalTransactionData.opening_cash);
                }
            } else if (this.reportType === 'daily_cash_check') {
                row.querySelectorAll('.cash-breakdown-input').forEach(input => {
                    const originalValue = originalTransactionData.cash_breakdown[input.dataset.denom];
                    if (originalValue !== undefined) {
                        input.value = originalValue;
                        input.closest('.editable-cell').querySelector('.display-value').innerText = originalValue;
                    }
                });
            }
            this.ui.updateRowByType(row);
        });
        this.ui.toggleEditMode(false);
    }

    handleInput(e) {
        if (e.target.classList.contains('editable-input')) {
            this.ui.updateRowByType(e.target.closest('tr'));
        }
    }

    handleChange(e) {
        const select = e.target;
        if (select.classList.contains('editable-select')) {
            const displayValueSpan = select.closest('.editable-cell').querySelector('.display-value');
            displayValueSpan.innerText = select.options[select.selectedIndex].text;
            select.closest('.editable-cell').dataset.categoryId = select.value;
            
            const itemType = select.options[select.selectedIndex].dataset.type;
            const itemTypeBadge = select.closest('tr').querySelector('td .badge');

            if (itemTypeBadge && itemType) {
                if (itemType.includes('discount')) {
                    itemTypeBadge.className = "badge bg-danger rounded-pill";
                    itemTypeBadge.innerText = '折扣';
                } else {
                    itemTypeBadge.className = "badge bg-success rounded-pill";
                    itemTypeBadge.innerText = '商品';
                }
            }
            if (this.reportType === 'transaction_log') {
                this.ui.updateRowByType(select.closest('tr'));
            }
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        let payload = [];

        if (this.reportType === 'daily_summary') {
            this.tableContainer.querySelectorAll('tbody tr[data-id]').forEach(row => {
                payload.push({
                    id: row.dataset.id,
                    opening_cash: this.ui.getCleanNumber(row.querySelector('[data-field="opening_cash"] .editable-input').value)
                });
            });
        } else if (this.reportType === 'daily_cash_check') {
            this.tableContainer.querySelectorAll('tbody tr[data-id]').forEach(row => {
                const rowData = { id: row.dataset.id, cash_breakdown: {} };
                row.querySelectorAll('.cash-breakdown-input').forEach(input => {
                    rowData.cash_breakdown[input.dataset.denom] = this.ui.getCleanNumber(input.value);
                });
                payload.push(rowData);
            });
        } else if (this.reportType === 'transaction_log') {
            const updatedData = {};
            this.tableContainer.querySelectorAll('tbody tr[data-id]').forEach(row => {
                const rowId = row.dataset.id;
                if (!updatedData[rowId]) {
                    updatedData[rowId] = { id: rowId, items: [] };
                    const cell = row.querySelector('[data-field="cash_received"]');
                    if (cell) updatedData[rowId].cash_received = this.ui.getCleanNumber(cell.querySelector('.editable-input').value);
                }
                const itemCell = row.querySelector('[data-item-id]');
                const categoryCell = row.querySelector('[data-field="category"]');
                if (itemCell && categoryCell) {
                    updatedData[rowId].items.push({
                        id: itemCell.dataset.itemId,
                        price: this.ui.getCleanNumber(itemCell.querySelector('.editable-input').value),
                        category_id: categoryCell.querySelector('.editable-select').value
                    });
                }
            });
            payload = Object.values(updatedData);
        }
        
        await this.api.saveReport(this.editableForm.action, payload);
    }
}

// Global instantiation to prevent dual firing and decouple dependencies
window.reportApp = null;
document.addEventListener('DOMContentLoaded', () => {
    window.reportApp = new ReportController();
});