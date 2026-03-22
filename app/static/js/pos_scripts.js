// app/static/js/pos_scripts.js

function safeCalculate(exprStr) {
    try {
        let s = String(exprStr).replace(/[^0-9.+\-*/()\s]/g, '').trim();
        if (['+', '-', '*', '/'].includes(s.slice(-1))) s = s.slice(0, -1).trim();
        if (s === '') return 0;
        
        if (/^-?\d+(\.\d+)?$/.test(s)) return parseFloat(s);

        let tokens = s.match(/(^-?\d+\.?\d*)|(\d+\.?\d*)|[+\-*/]/g) || [];
        if (!tokens.length) return 0;

        for (let i = 1; i < tokens.length - 1; i += 2) {
            if (tokens[i] === '*' || tokens[i] === '/') {
                let a = parseFloat(tokens[i-1]), b = parseFloat(tokens[i+1]);
                let res = tokens[i] === '*' ? a * b : (b !== 0 ? a / b : 0);
                tokens.splice(i-1, 3, res.toString());
                i -= 2;
            }
        }

        let result = parseFloat(tokens[0]) || 0;
        for (let i = 1; i < tokens.length - 1; i += 2) {
            let op = tokens[i], b = parseFloat(tokens[i+1]) || 0;
            if (op === '+') result += b; else if (op === '-') result -= b;
        }
        return result;
    } catch (e) { return 0; }
}

class POSTransaction {
    constructor() { Object.assign(this, this.getDefaults()); }
    getDefaults() {
        return {
            expression: [], currentInput: '0', items: [],
            isReadyForNewInput: false, inPaymentMode: false,
            activeDiscountMode: null, finalTotalForPayment: 0, isComplete: false
        };
    }
    reset() { Object.assign(this, this.getDefaults()); }

    get currentItemsTotal() { return this.items.reduce((sum, i) => sum + i.price, 0); }
    getCurrentTotal() {
        if (this.activeDiscountMode || this.inPaymentMode) return this.currentItemsTotal;
        let exprStr = [...this.expression, this.currentInput].join(' ');
        if (['+', '-', '*', '/'].includes(exprStr.trim().slice(-1))) exprStr = exprStr.slice(0, -1).trim();
        return this.currentItemsTotal + safeCalculate(exprStr);
    }
}

class POSUIManager {
    constructor() {
        ['displayExpression', 'displayMain', 'displaySub', 'receiptDetails', 'equalsBtn', 'checkoutBtn']
            .forEach(id => this[id] = document.getElementById(id.replace(/[A-Z]/g, m => "-" + m.toLowerCase())));
        this.equalsBtn = document.getElementById("equals-btn");
        this.checkoutBtn = document.getElementById("checkout-btn");
    }

    updateDashboardTotals(tSales, tTrans, tItems, donTotal, otherTotal) {
        const el = id => document.getElementById(id);
        const fmt = n => `$ ${Math.round(n).toLocaleString()}`;
        if (el("total-sales")) el("total-sales").innerText = fmt(tSales);
        if (el("total-transactions")) el("total-transactions").innerText = tTrans;
        if (el("total-items")) el("total-items").innerText = tItems;
        if (el("donation-total")) el("donation-total").innerText = fmt(donTotal);
        if (el("other-total")) el("other-total").innerText = fmt(otherTotal);
        if (el("other-income-total")) el("other-income-total").innerText = fmt(donTotal + otherTotal);
    }

    updateDisplay(tx, subText = null) {
        const mainVal = parseFloat(tx.currentInput) || 0;
        if (this.displayMain) this.displayMain.innerText = mainVal.toLocaleString('en-US', { maximumFractionDigits: 2 });
        if (this.displayExpression) {
            if (tx.inPaymentMode || tx.activeDiscountMode) {
                this.displayExpression.innerText = `小計: ${tx.getCurrentTotal().toLocaleString('en-US')}`;
            } else {
                const itemsText = tx.items.map(i => i.displayText).join(' + ');
                const curExpr = [...tx.expression, (tx.currentInput !== '0' || tx.expression.length > 0) ? tx.currentInput : ''].join(' ');
                const fullText = [itemsText, curExpr].filter(Boolean).join(' + ').replace(/\+ -/g, '- ');
                this.displayExpression.innerText = fullText;
            }
        }
        if (this.displaySub) {
            if (subText) this.displaySub.innerText = subText;
            else if (tx.activeDiscountMode) this.displaySub.innerText = `請輸入折扣 (例如 9折 輸入 9)`;
            else if (tx.inPaymentMode) this.displaySub.innerText = `應收: ${tx.finalTotalForPayment.toLocaleString()} / 實收: ${mainVal.toLocaleString()}`;
            else this.displaySub.innerText = `小計: ${tx.getCurrentTotal().toLocaleString('en-US')}`;
        }
    }

    updateReceipt(tx, promptText = null) {
        if (!this.receiptDetails) return;
        this.receiptDetails.className = '';
        if (!tx.items.length && !promptText) {
            this.receiptDetails.className = 'd-flex justify-content-center align-items-center h-100';
            this.receiptDetails.innerHTML = '<span class="text-muted">暫無商品</span>';
            return;
        }
        const isOther = tx.items.length && tx.items[0].category_type === 'other_income';
        const hdr = `<div class="receipt-line receipt-header"><div class="flex-grow-1">${isOther ? '項目' : '商品'}</div><div style="width:50px" class="text-center">數量</div><div style="width:70px" class="text-end">單價</div><div style="width:80px" class="text-end">金額</div></div>`;
        const itemsHtml = tx.items.map(item => {
            const isProd = item.category_type === 'product' && item.quantity > 0;
            return `<div class="receipt-line ${item.price < 0 ? 'text-danger' : ''}"><div class="flex-grow-1">${item.categoryName}</div>${isProd ? `<div style="width:50px" class="text-center">${item.quantity}</div><div style="width:70px" class="text-end">${item.unitPrice.toLocaleString()}</div>` : `<div style="width:120px"></div>`}<div style="width:80px" class="text-end fw-bold">${item.price.toLocaleString()}</div></div>`;
        }).join('');
        this.receiptDetails.innerHTML = `<div>${hdr}<div class="item-list">${itemsHtml}</div></div>${promptText ? `<div class="receipt-prompt">${promptText}</div>` : ''}`;
        this.receiptDetails.scrollTop = this.receiptDetails.scrollHeight;
    }

    updateReceiptForCheckout(tx, amountPaid) {
        if (!this.receiptDetails) return;
        const total = tx.finalTotalForPayment;
        const pos = tx.items.filter(i => i.price > 0).reduce((s, i) => s + i.price, 0);
        const discHtml = tx.items.filter(i => i.price < 0).map(d => `<div class="receipt-line"><span>${d.categoryName}</span><span class="text-danger">${d.price.toLocaleString()}</span></div>`).join('');
        this.receiptDetails.className = 'd-flex flex-column h-100';
        this.receiptDetails.innerHTML = `<div><div class="receipt-line"><span>商品總計</span><span class="fw-bold">${pos.toLocaleString()}</span></div></div><div class="flex-grow-1"></div><div class="pt-2">${discHtml}<hr class="my-1"><div class="receipt-line fw-bold"><span>應收金額</span><span>${total.toLocaleString()}</span></div><div class="receipt-line"><span>實收現金</span><span>${amountPaid.toLocaleString()}</span></div><div class="receipt-line"><span>找零</span><span>${(amountPaid - total).toLocaleString()}</span></div></div>`;
    }

    updateReceiptForOther(amount, title) {
        if (!this.receiptDetails) return;
        this.receiptDetails.className = 'd-flex justify-content-center align-items-center h-100';
        this.receiptDetails.innerHTML = `<div class="text-center p-3"><h4 class="fw-bold mb-2">${title}</h4><p class="text-muted small mb-3">您的每一份支持，都是改變的力量</p><hr class="my-2"><div class="d-flex justify-content-center align-items-center fs-4 mt-3 px-3"><span class="text-success fw-bold me-2">NT$</span><span class="fw-bold">${amount.toLocaleString()}</span></div></div>`;
    }

    setCheckoutMode(isCheckout) {
        if (this.equalsBtn) this.equalsBtn.style.display = isCheckout ? 'none' : 'block';
        if (this.checkoutBtn) this.checkoutBtn.style.display = isCheckout ? 'block' : 'none';
        document.querySelectorAll(".category-btn").forEach(btn => btn.disabled = isCheckout);
    }

    setCategoryButtonsState(disabledPercent) {
        document.querySelectorAll(".category-btn").forEach(btn => btn.disabled = btn.dataset.type === 'discount_percent' ? disabledPercent : false);
        document.querySelectorAll(".calc-btn").forEach(btn => btn.disabled = false);
    }
}

class POSDiscountEngine {
    constructor(tx) {
        this.tx = tx;
        this.autoDiscounts = window.AUTOMATED_DISCOUNTS || [];
    }

    evaluate() {
        if (!this.autoDiscounts.length || this.tx.inPaymentMode) return;
        this.tx.items = this.tx.items.filter(i => !['buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even', 'product_discount_percent'].includes(i.category_type));
        this.autoDiscounts.forEach(d => {
            if (d.type === 'buy_n_get_m') this._applyBuyN(d.id, d.name, d.rules);
            else if (d.type === 'buy_x_get_x_minus_1') this._applyBuyX(d.id, d.name, d.rules);
            else if (d.type === 'buy_odd_even') this._applyBuyOddEven(d.id, d.name, d.rules);
            else if (d.type === 'product_discount_percent') this._applyProductPercent(d.id, d.name, d.rules);
        });
    }

    _calc(items, count) {
        const all = [];
        items.forEach(i => { for(let j=0; j<i.quantity; j++) all.push(i.unitPrice); });
        all.sort((a, b) => a - b);
        return all.slice(0, count).reduce((s, a) => s + a, 0);
    }

    _filterEligible(targetId) {
        return this.tx.items.filter(i => i.price > 0 && (targetId == 0 ? i.category_type === 'product' : i.category_id == targetId));
    }

    _applyBuyN(cid, cname, r) {
        if (!r.buy_n || !r.get_m_free) return;
        const e = this._filterEligible(r.target_category_id);
        const t = e.reduce((s, i) => s + i.quantity, 0);
        if (t < r.buy_n) return;
        const amt = this._calc(e, Math.floor(t / r.buy_n) * r.get_m_free);
        if (amt > 0) this.tx.items.push({price: -amt, unitPrice: -amt, quantity: 1, category_id: cid, category_type: 'buy_n_get_m', categoryName: `${cname} (買 ${r.buy_n} 送 ${r.get_m_free})`, displayText: `-${amt}`});
    }

    _applyBuyX(cid, cname, r) {
        const e = this._filterEligible(r.target_category_id), t = e.reduce((s, i) => s + i.quantity, 0);
        if (t < 2) return;
        const amt = this._calc(e, t - 1);
        if (amt > 0) this.tx.items.push({price: -amt, unitPrice: -amt, quantity: 1, category_id: cid, category_type: 'buy_x_get_x_minus_1', categoryName: `${cname} (買 ${t} 送 ${t - 1})`, displayText: `-${amt}`});
    }

    _applyBuyOddEven(cid, cname, r) {
        const e = this._filterEligible(r.target_category_id), t = e.reduce((s, i) => s + i.quantity, 0);
        if (t < 1) return;
        const freeCount = Math.floor((t - 1) / 2);
        const paidCount = t - freeCount;
        const amt = this._calc(e, freeCount);
        if (amt > 0) this.tx.items.push({price: -amt, unitPrice: -amt, quantity: 1, category_id: cid, category_type: 'buy_odd_even', categoryName: `${cname} (買 ${paidCount} 折 ${freeCount})`, displayText: `-${amt}`});
    }

    _applyProductPercent(cid, cname, r) {
        if (!r.percent) return;
        const e = this._filterEligible(r.target_category_id);
        const t = e.reduce((s, i) => s + i.quantity, 0);
        if (t < 1) return;
        const mult = (r.percent < 10 && r.percent >= 1) ? r.percent / 10 : r.percent / 100;
        const totalPrice = e.reduce((s, i) => s + (i.price), 0);
        const discountAmt = Math.round(totalPrice * (1 - mult));
        if (discountAmt > 0) {
            this.tx.items.push({
                price: -discountAmt, unitPrice: -discountAmt, quantity: 1, 
                category_id: cid, category_type: 'product_discount_percent', 
                categoryName: `${cname} (${r.percent}折)`, displayText: `-${discountAmt}`
            });
        }
    }

    getHint(pid) {
        let match = this.autoDiscounts.filter(d => d.rules.target_category_id == 0 || d.rules.target_category_id == pid);
        if (!match.length) return null;
        let hints = [];
        match.forEach(d => {
            const e = this._filterEligible(d.rules.target_category_id);
            const t = e.reduce((s, i) => s + i.quantity, 0);
            if (d.type === 'buy_n_get_m') {
                const req = d.rules.buy_n;
                const rem = t % req;
                if (t === 0 || rem > 0) hints.push(`${d.name}：再買 ${req - rem} 件即享買 ${req} 送 ${d.rules.get_m_free}`);
                else hints.push(`已滿件：${d.name} (買 ${req} 送 ${d.rules.get_m_free})`);
            } else if (d.type === 'buy_x_get_x_minus_1') {
                if (t < 2) hints.push(`${d.name}：再買 1 件即可享優惠`);
                else hints.push(`已套用：${d.name} (買 ${t} 送 ${t - 1})`);
            } else if (d.type === 'buy_odd_even') {
                const freeCount = Math.floor((t - 1) / 2);
                const paidCount = t - freeCount;
                if (t % 2 !== 0 && t >= 3) {
                    hints.push(`已滿件：${d.name} (買 ${paidCount} 折 ${freeCount})`);
                } else {
                    let nextTarget = 3;
                    if (t > 0) nextTarget = (t % 2 === 0) ? t + 1 : t + 2;
                    const diff = nextTarget - t;
                    const nextFree = Math.floor((nextTarget - 1) / 2);
                    const nextPaid = nextTarget - nextFree;
                    if (t === 0) hints.push(`${d.name}：享有買 ${nextPaid} 折 ${nextFree} 優惠`);
                    else hints.push(`${d.name}：再買 ${diff} 件，即可買 ${nextPaid} 折 ${nextFree}`);
                }
            } else if (d.type === 'product_discount_percent') {
                if (t > 0) hints.push(`已自動套用：${d.name} (${d.rules.percent}折)`);
                else hints.push(`${d.name}：隨意搭配即享 ${d.rules.percent}折`);
            }
        });
        return hints.length ? hints.join('，') : null;
    }
}

class POSController {
    constructor() {
        this.tx = new POSTransaction();
        this.ui = new POSUIManager();
        this.discountEngine = new POSDiscountEngine(this.tx);
        document.querySelectorAll('.category-btn').forEach(b => b.addEventListener('click', () => this.handleCategoryClick(b)));
        const dBtn = document.getElementById("donation-btn"), oBtn = document.getElementById("other-income-btn");
        if (dBtn) dBtn.addEventListener('click', () => this.handleCategoryClick({ dataset: { id: dBtn.dataset.id, name: dBtn.dataset.name, type: 'other_income', rules: '{}' } }));
        if (oBtn) oBtn.addEventListener('click', () => this.handleCategoryClick({ dataset: { id: oBtn.dataset.id, name: oBtn.dataset.name, type: 'other_income', rules: '{}' } }));
        this.reset();
        console.log("[POS] Object-Oriented App Initialized.");
    }

    reset() {
        this.tx.reset();
        this.ui.setCategoryButtonsState(true);
        this.ui.setCheckoutMode(false);
        this.ui.updateReceipt(this.tx);
        this.ui.updateDisplay(this.tx);
    }

    _chkReset() { if (this.tx.isComplete) { this.reset(); return true; } return false; }

    handleNumber(v) {
        if (this._chkReset()) { this.handleNumber(v); return; }
        if (this.tx.isReadyForNewInput) { this.tx.currentInput = v === '.' ? '0.' : v; this.tx.isReadyForNewInput = false; }
        else {
            if (this.tx.currentInput === '0' && v !== '.' && v !== '00') this.tx.currentInput = v;
            else if (v === '.' && this.tx.currentInput.includes('.')) return;
            else if (this.tx.currentInput.length < 14) this.tx.currentInput += v;
        }
        this.ui.updateDisplay(this.tx);
    }

    handleOperator(op) {
        if (this._chkReset() || this.tx.inPaymentMode || this.tx.activeDiscountMode) return;
        this.tx.expression.push(this.tx.currentInput);
        this.tx.expression.push(op);
        this.tx.currentInput = '0';
        this.tx.isReadyForNewInput = true;
        this.ui.updateDisplay(this.tx);
    }

    handleBackspace() {
        this.tx.currentInput = this.tx.currentInput.length > 1 ? this.tx.currentInput.slice(0, -1) : '0';
        this.ui.updateDisplay(this.tx);
    }

    handleUndo() {
        if (this.tx.inPaymentMode || this.tx.activeDiscountMode) return;
        if (this.tx.currentInput !== '0' || this.tx.expression.length > 0) Object.assign(this.tx, {currentInput: '0', expression: []});
        else if (this.tx.items.length > 0) { this.tx.items.pop(); this.discountEngine.evaluate(); }
        this.ui.setCheckoutMode(false);
        this.ui.updateReceipt(this.tx);
        this.ui.updateDisplay(this.tx);
    }

    handleEquals() {
        if (this._chkReset()) return;
        if (this.tx.activeDiscountMode) {
            this._applyPercent(); this.discountEngine.evaluate();
        } else if (!this.tx.inPaymentMode) {
            const val = safeCalculate([...this.tx.expression, this.tx.currentInput].join(' '));
            if (val > 0) this.tx.items.push({price: val, unitPrice: val, quantity: 1, category_id: null, category_type: 'product', categoryName: "手動輸入", displayText: val.toString()});
            Object.assign(this.tx, {expression: [], currentInput: '0', finalTotalForPayment: this.tx.getCurrentTotal(), inPaymentMode: true, isReadyForNewInput: true});
            this.ui.setCheckoutMode(true);
            this.ui.updateDisplay(this.tx);
            this.ui.updateReceipt(this.tx);
        } else this.handleCheckout();
    }

    handleCategoryClick(btn) {
        if (this._chkReset()) { this.handleCategoryClick(btn); return; }
        const cId = btn.dataset.id, cName = btn.dataset.name, cType = btn.dataset.type, raw = btn.dataset.rules;
        const r = (() => { try { return JSON.parse(!raw || raw === 'None' || raw === 'undefined' ? '{}' : raw); } catch(e){ return {}; } })();
        if (cType === 'discount_percent') { this.tx.activeDiscountMode = { id: cId, name: cName, rules: r }; this.tx.currentInput = '0'; this.tx.isReadyForNewInput = true; this.ui.updateDisplay(this.tx); return; }
        if (this.tx.inPaymentMode) return;
        if (cType === 'other_income') { this._applyOther(cId, cName); return; }
        if (cType === 'product') this._applyProduct(cId, cName);
        else if (cType === 'discount_fixed') this._applyFixed(cId, cName);
    }

    _applyProduct(cId, cName) {
        const val = safeCalculate([...this.tx.expression, this.tx.currentInput].join(' '));
        if (val <= 0) { this.ui.updateDisplay(this.tx, "請先輸入金額"); return; }
        let qty = 1, uPrice = val, dText = val.toString(), exprStr = [...this.tx.expression, this.tx.currentInput].join('');
        if (exprStr.includes('*') && !exprStr.match(/[+\-\/]/)) {
            const p = exprStr.split('*'); qty = parseInt(safeCalculate(p[0])) || 1; uPrice = safeCalculate(p[1]); dText = `${qty}*${uPrice}`;
        }
        this.tx.items.push({price: qty * uPrice, unitPrice: uPrice, quantity: qty, category_id: cId, category_type: 'product', categoryName: cName, displayText: dText});
        Object.assign(this.tx, {expression: [], currentInput: '0'});
        this.ui.setCategoryButtonsState(false); this.ui.setCheckoutMode(false);
        this.discountEngine.evaluate();
        const hint = this.discountEngine.getHint(cId);
        this.ui.updateReceipt(this.tx, hint);
        this.ui.updateDisplay(this.tx, hint);
    }

    _applyFixed(cId, cName) {
        const val = safeCalculate([...this.tx.expression, this.tx.currentInput].join(' '));
        if (val <= 0) return;
        this.tx.items.push({price: -val, unitPrice: -val, quantity: 1, category_id: cId, category_type: 'discount_fixed', categoryName: `${cName} -${val}`, displayText: `-${val}`});
        Object.assign(this.tx, {expression: [], currentInput: '0'}); this.discountEngine.evaluate();
        this.ui.updateReceipt(this.tx); this.ui.updateDisplay(this.tx);
    }

    _applyPercent() {
        if (!this.tx.activeDiscountMode) return;
        const dVal = parseFloat(this.tx.currentInput);
        if (isNaN(dVal) || dVal <= 0 || dVal >= 10) { this.ui.updateDisplay(this.tx, "折扣值需介於 0 和 10 之間"); this.tx.activeDiscountMode = null; this.tx.currentInput = '0'; return; }
        const { id, name } = this.tx.activeDiscountMode;
        const tot = this.tx.items.reduce((s, i) => s + (i.price > 0 ? i.price : 0), 0), dAmt = -(tot * (1 - dVal / 10));
        this.tx.items = this.tx.items.filter(i => i.category_id !== id);
        if (dAmt < 0) this.tx.items.push({price: dAmt, unitPrice: dAmt, quantity: 1, category_id: id, category_type: 'discount_percent', categoryName: `${name} ${dVal}折`, displayText: `${dAmt.toFixed(0)}`});
        Object.assign(this.tx, {activeDiscountMode: null, currentInput: '0', inPaymentMode: false});
        this.ui.setCheckoutMode(false); this.ui.updateReceipt(this.tx); this.ui.updateDisplay(this.tx);
    }

    async _applyOther(cId, cName) {
        const val = safeCalculate([...this.tx.expression, this.tx.currentInput].join(' '));
        if (val <= 0) { this.ui.updateDisplay(this.tx, "金額必須大於 0"); return; }
        const i = [{price: val, unitPrice: val, quantity: 1, category_id: cId, category_type: 'other_income', categoryName: cName, displayText: val.toString()}];
        const ok = await this._sendTrans(i, val, 0);
        if (ok) { this.ui.updateReceiptForOther(val, cName); this._finalize(true, val, 0); } else this._finalize(false, null, null);
    }

    async handleCheckout(pAmnt = null) {
        const p = (pAmnt !== null && pAmnt !== undefined) ? pAmnt : parseFloat(this.tx.currentInput);
        if (isNaN(p) || p < this.tx.finalTotalForPayment) { this.ui.updateDisplay(this.tx, `金額不足，應收: ${this.tx.finalTotalForPayment.toLocaleString()}`); return; }
        const chg = p - this.tx.finalTotalForPayment, ok = await this._sendTrans(this.tx.items, p, chg);
        if (ok) { this.ui.updateReceiptForCheckout(this.tx, p); this._finalize(true, p, chg); } else this._finalize(false, null, null);
    }

    _finalize(ok, pAmnt, chg) {
        this.tx.isComplete = ok;
        if (ok) { this.tx.currentInput = pAmnt !== null ? pAmnt.toString() : '0'; this.ui.updateDisplay(this.tx, chg !== null ? `找零: ${chg.toLocaleString()}` : ''); }
        else this.ui.updateDisplay(this.tx, "交易失敗");
        if (this.tx.isComplete) setTimeout(() => this.reset(), 1500);
    }

    async _sendTrans(items, paidAmount, chgRec) {
        const exp = []; items.forEach(it => { for (let i = 0; i < it.quantity; i++) exp.push({ price: it.unitPrice, category_id: it.category_id }); });
        try {
            const resp = await fetch("/cashier/record_transaction", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ location_slug: typeof POS_LOCATION_SLUG !== 'undefined' ? POS_LOCATION_SLUG : '', items: exp, cash_received: paidAmount, change_given: chgRec }) });
            if (!resp.ok) throw new Error("Network response was not ok");
            const res = await resp.json();
            if (res.success) { this.ui.updateDashboardTotals(res.total_sales, res.total_transactions, res.total_items, res.donation_total, res.other_total); return true; }
            else { this.ui.updateDisplay(this.tx, `傳送失敗: ${res.error}`); return false; }
        } catch (e) { console.error("[POS] Checkout error:", e); this.ui.updateDisplay(this.tx, "傳送失敗"); return false; }
    }
}

window.posApp = null;
document.addEventListener("DOMContentLoaded", () => {
    window.posApp = new POSController();
    window.posNum   = (v) => window.posApp.handleNumber(v);
    window.posOp    = (v) => window.posApp.handleOperator(v);
    window.posClear = () => window.posApp.tx.isComplete ? window.posApp.reset() : window.posApp.reset();
    window.posUndo  = () => window.posApp.handleUndo();
    window.posBack  = () => window.posApp.handleBackspace();
    window.posEquals   = () => window.posApp.handleEquals();
    window.posCheckout = () => window.posApp.handleCheckout();
});