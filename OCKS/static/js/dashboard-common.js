// Shared dashboard/common JS utilities
(function(){
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // expose globally
    window.getCookie = getCookie;
    window.csrftoken = getCookie('csrftoken');

    if (window.jQuery) {
        $.ajaxSetup({ headers: { 'X-CSRFToken': window.csrftoken } });
    }

    // Flag to prevent form submission during bfcache restore
    let isRestoringFromCache = false;
    // One-step guard to absorb an immediate Back press after printing.
    let hasPrintBackGuard = false;

    // Store the initial filter state based on the URL query params
    let initialFilterState = {};
    function captureFilterStateFromURL() {
        try {
            const params = new URLSearchParams(window.location.search);
            initialFilterState = {
                status: params.get('status') || '',
                payment: params.get('payment_status') || '',
                search: params.get('search') || ''
            };
        } catch (e) { /* ignore */ }
    }

    // Restore filters to match the URL query params (what the server rendered)
    function restoreFilterStateFromURL() {
        try {
            const params = new URLSearchParams(window.location.search);
            const filterForm = document.querySelector('.filter-form');
            if (filterForm) {
                isRestoringFromCache = true;
                
                const statusSelect = filterForm.querySelector('#status-filter');
                const paymentSelect = filterForm.querySelector('#payment-filter');
                const searchInput = filterForm.querySelector('#search-orders');
                
                // Restore to what the URL says, overriding any browser-cached values
                const statusValue = params.get('status') || '';
                const paymentValue = params.get('payment_status') || '';
                const searchValue = params.get('search') || '';
                
                if (statusSelect) statusSelect.value = statusValue;
                if (paymentSelect) paymentSelect.value = paymentValue;
                if (searchInput) searchInput.value = searchValue;

                // Keep the guard active briefly in case browser emits delayed restore events.
                setTimeout(function () {
                    isRestoringFromCache = false;
                }, 250);
            }
        } catch (e) { /* ignore */ }
    }

    // Admin: attach handlers if dashboard elements are present
    function initAdminHandlers() {
        // Prevent filter form submission during bfcache restore
        const filterForm = document.querySelector('.filter-form');
        if (filterForm) {
            function navigateFiltersWithReplace() {
                const action = filterForm.getAttribute('action') || window.location.pathname;
                const params = new URLSearchParams(new FormData(filterForm));

                // Keep URLs clean: drop empty params.
                Array.from(params.keys()).forEach(function (key) {
                    if ((params.get(key) || '').trim() === '') {
                        params.delete(key);
                    }
                });

                const query = params.toString();
                const nextUrl = query ? (action + '?' + query) : action;
                window.location.replace(nextUrl);
            }

            filterForm.addEventListener('submit', function(e) {
                if (isRestoringFromCache) {
                    e.preventDefault();
                    return false;
                }

                // Navigate with replace so prior filter states don't remain in history.
                e.preventDefault();
                try {
                    navigateFiltersWithReplace();
                } catch (err) {
                    // Fallback if URL APIs are unavailable.
                    filterForm.submit();
                }

                return false;
            });

            // Auto-apply select filters through replace-based navigation.
            const statusFilter = filterForm.querySelector('#status-filter');
            const paymentFilter = filterForm.querySelector('#payment-filter');
            [statusFilter, paymentFilter].forEach(function (el) {
                if (!el) return;
                el.addEventListener('change', function () {
                    if (isRestoringFromCache) return;
                    navigateFiltersWithReplace();
                });
            });

            const clearLink = document.querySelector('.clear-filters-link');
            if (clearLink) {
                clearLink.addEventListener('click', function (e) {
                    e.preventDefault();
                    const clearUrl = clearLink.getAttribute('href') || window.location.pathname;
                    window.location.replace(clearUrl);
                });
            }
        }

        // status change
        const statusSelects = document.querySelectorAll('.status-select');
        if (statusSelects.length && window.updateOrderUrl) {
            statusSelects.forEach(select => {
                select.addEventListener('change', function() {
                    const orderId = this.dataset.orderId;
                    const newStatus = this.value;
                    fetch(window.updateOrderUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.csrftoken
                        },
                        body: JSON.stringify({ order_id: orderId, status: newStatus })
                    }).then(res => res.json()).then(data => {
                        if (data.success) {
                            const row = document.querySelector(`tr[data-order-id="${orderId}"]`);
                            if (row) {
                                row.classList.add('updated');
                                setTimeout(() => row.classList.remove('updated'), 2000);
                            }
                        }
                    }).catch(console.error);
                });
            });
        }

        // payment status
        const paymentSelects = document.querySelectorAll('.payment-status-select');
        if (paymentSelects.length && window.updatePaymentUrl) {
            paymentSelects.forEach(select => {
                select.addEventListener('change', function() {
                    const orderId = this.dataset.orderId;
                    const newPaymentStatus = this.value;
                    fetch(window.updatePaymentUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.csrftoken
                        },
                        body: JSON.stringify({ order_id: orderId, payment_status: newPaymentStatus })
                    }).then(res => res.json()).then(data => {
                        if (data.success) {
                            const row = document.querySelector(`tr[data-order-id="${orderId}"]`);
                            if (row) {
                                const badge = row.querySelector('td:nth-child(7) .badge');
                                if (badge) {
                                    badge.classList.remove('bg-warning','bg-success');
                                    if (newPaymentStatus.toLowerCase() === 'pending') badge.classList.add('bg-warning');
                                    else badge.classList.add('bg-success');
                                }
                                row.classList.add('updated');
                                setTimeout(() => row.classList.remove('updated'), 2000);
                            }
                        }
                    }).catch(console.error);
                });
            });
        }

        // view-order and view-items modal behavior
        const viewOrderBtns = document.querySelectorAll('.view-order');
        if (viewOrderBtns.length) {
            viewOrderBtns.forEach(btn => btn.addEventListener('click', function() {
                const orderId = this.dataset.orderId;
                const row = document.querySelector(`tr[data-order-id="${orderId}"]`);
                if (!row) return;
                const queueNum = row.querySelector('td:first-child').textContent.trim();
                const orderType = row.querySelector('td:nth-child(3) .badge').textContent;
                const total = row.querySelector('td:nth-child(5)').textContent;
                const status = row.querySelector('td:nth-child(6) .status-select').value;
                const paymentStatus = row.querySelector('td:nth-child(7) .payment-status-select').value;
                const time = row.querySelector('td:nth-child(8)').textContent;
                const customerName = row.dataset.customerName || '';
                const customerPhone = row.dataset.customerPhone || '';
                const modal = document.getElementById('orderModal');
                const modalBody = document.getElementById('orderModalBody');
                modalBody.innerHTML = `
                    <div class="order-detail-info">
                        <div class="customer-detail-block">
                            <h6 class="mb-2">Customer Details</h6>
                            <p class="mb-1"><strong>Name:</strong> ${customerName || 'Guest'}</p>
                            <p class="mb-0"><strong>Phone:</strong> ${customerPhone || 'N/A'}</p>
                        </div>
                        <p><strong>Queue Number:</strong> ${queueNum}</p>
                        <p><strong>Order Type:</strong> ${orderType}</p>
                        <p><strong>Total:</strong> ${total}</p>
                        <p><strong>Status:</strong> ${status}</p>
                        <p><strong>Payment:</strong> ${paymentStatus}</p>
                        <p><strong>Time:</strong> ${time}</p>
                    </div>`;
                if (window.jQuery) $(modal).modal('show');
            }));
        }

        // view-items button
        const viewItemsBtns = document.querySelectorAll('.view-items-btn');
        if (viewItemsBtns.length) {
            viewItemsBtns.forEach(btn => btn.addEventListener('click', function() {
                const orderId = this.dataset.orderId;
                const row = document.querySelector(`tr[data-order-id="${orderId}"]`);
                if (!row) return;
                const queueNum = row.querySelector('td:first-child').textContent.trim();
                const orderType = row.querySelector('td:nth-child(3) .badge').textContent;
                const total = row.querySelector('td:nth-child(5)').textContent;
                const modal = document.getElementById('orderModal');
                const modalBody = document.getElementById('orderModalBody');
                const modalTitle = modal.querySelector('.modal-title');
                const itemsSource = row.querySelector('.order-items-source');
                modalTitle.textContent = `Order Items - ${queueNum}`;
                modalBody.innerHTML = `
                    <div class="order-detail-info mb-3">
                        <p><strong>Queue Number:</strong> ${queueNum}</p>
                        <p><strong>Order Type:</strong> ${orderType}</p>
                        <p><strong>Total:</strong> ${total}</p>
                    </div>`;
                if (itemsSource) modalBody.innerHTML += itemsSource.innerHTML;
                if (window.jQuery) $(modal).modal('show');
            }));
        }

        // print-order (ticket receipt printing)
        const printBtns = document.querySelectorAll('.print-order');
        if (printBtns.length) {
            printBtns.forEach(btn => btn.addEventListener('click', function() {
                const row = this.closest('tr');
                if (!row) return;

                const queueNum = row.querySelector('td:nth-child(1)').textContent.trim();
                const orderId = row.querySelector('td:nth-child(2)').textContent.trim().replace('#', '');
                const orderType = row.querySelector('.order-type-badge') ? row.querySelector('.order-type-badge').textContent.trim() : row.querySelector('td:nth-child(3)').textContent.trim();
                const totalPrice = row.querySelector('td:nth-child(5)').textContent.trim();
                const orderTime = row.querySelector('td:nth-child(8) small') ? row.querySelector('td:nth-child(8) small').textContent.trim() : '';
                const customerName = row.dataset.customerName || 'Guest';
                const customerPhone = row.dataset.customerPhone || 'N/A';

                const itemsSource = row.querySelector('.order-items-source');
                let itemsHTML = '';
                if (itemsSource) {
                    const rows = itemsSource.querySelectorAll('.view-items-row');
                    rows.forEach(itemRow => {
                        const name = itemRow.querySelector('.item-name').textContent.trim();
                        const qty = itemRow.querySelector('.item-qty').textContent.trim();
                        const subtotal = itemRow.querySelector('.item-subtotal').textContent.trim();
                        
                        const isCustomization = itemRow.classList.contains('text-muted');
                        
                        if (isCustomization) {
                            itemsHTML += `
                                <tr>
                                    <td colspan="3" style="font-size: 0.8rem; color: #555; padding-left: 10px; font-style: italic;">
                                        &nbsp;&nbsp;${name}
                                    </td>
                                </tr>`;
                        } else {
                            itemsHTML += `
                                <tr style="border-bottom: 1px dashed #eee;">
                                    <td style="padding: 4px 0; max-width: 180px; word-wrap: break-word;">${name}</td>
                                    <td style="text-align: center; padding: 4px 0;">${qty}</td>
                                    <td style="text-align: right; padding: 4px 0;">${subtotal}</td>
                                </tr>`;
                        }
                    });
                }

                // Create or reuse print section in body
                let printSection = document.getElementById('print-receipt-section');
                if (!printSection) {
                    printSection = document.createElement('div');
                    printSection.id = 'print-receipt-section';
                    document.body.appendChild(printSection);
                }
                printSection.innerHTML = `
                    <div class="print-ticket" style="font-family: 'Courier New', Courier, monospace; width: 300px; margin: 0 auto; padding: 10px; color: #000; background: #fff;">
                        <div style="text-align: center; border-bottom: 1px dashed #000; padding-bottom: 10px; margin-bottom: 10px;">
                            <h3 style="margin: 0; font-size: 1.25rem; font-weight: bold; letter-spacing: 1px;">SWIFT SERVE KIOSK</h3>
                            <p style="margin: 5px 0 0; font-size: 0.85rem; text-transform: uppercase;">Order Ticket</p>
                        </div>
                        <div style="font-size: 0.85rem; line-height: 1.4; border-bottom: 1px dashed #000; padding-bottom: 10px; margin-bottom: 10px;">
                            <p style="margin: 0;"><strong>Date:</strong> ${new Date().toLocaleDateString()} | ${orderTime}</p>
                            <p style="margin: 0;"><strong>Order ID:</strong> #${orderId}</p>
                            <p style="margin: 0;"><strong>Queue Num:</strong> <span style="font-size: 1.15rem; font-weight: bold;">${queueNum}</span></p>
                            <p style="margin: 0;"><strong>Order Type:</strong> ${orderType.toUpperCase()}</p>
                            <p style="margin: 0;"><strong>Customer:</strong> ${customerName} (${customerPhone || 'N/A'})</p>
                        </div>
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 10px;">
                            <thead>
                                <tr style="border-bottom: 1px solid #000;">
                                    <th style="text-align: left; padding-bottom: 5px;">Item</th>
                                    <th style="text-align: center; padding-bottom: 5px; width: 40px;">Qty</th>
                                    <th style="text-align: right; padding-bottom: 5px; width: 80px;">Price</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${itemsHTML || '<tr><td colspan="3" style="text-align:center;">No items found</td></tr>'}
                            </tbody>
                        </table>
                        <div style="border-top: 1px dashed #000; padding-top: 10px; text-align: right; font-size: 1rem; font-weight: bold;">
                            TOTAL: ${totalPrice}
                        </div>
                    </div>`;

                try {
                    if (!hasPrintBackGuard && window.history && window.history.pushState) {
                        window.history.pushState({ printBackGuard: true }, '', window.location.href);
                        hasPrintBackGuard = true;
                    }
                } catch (e) { /* ignore */ }

                window.print();
            }));
        }

        // auto-refresh guard
        function isInteractingWithDashboard() {
            const active = document.activeElement;
            const formFocused = active && (
                active.tagName === 'INPUT' || active.tagName === 'SELECT' || active.tagName === 'TEXTAREA' || active.isContentEditable
            );
            const modalOpen = document.querySelector('.modal.show') !== null;
            return formFocused || modalOpen;
        }

        if (document.querySelector('.admin-container')) {
            setInterval(function() {
                if (!isInteractingWithDashboard()) location.reload();
            }, 10000);
        }
    }

    // initialize when DOM ready
    function onReady() {
        captureFilterStateFromURL();
        initAdminHandlers();
        restoreFilterStateFromURL();
    }
    
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', onReady);
    else onReady();

    // Keep filter controls synced to URL on all pageshow events (normal load + bfcache)
    window.addEventListener('pageshow', function (event) {
        restoreFilterStateFromURL();
        
        // Ensure layout recomputes
        try {
            const searchFieldWrapper = document.querySelector('.filter-search-field');
            if (searchFieldWrapper) {
                searchFieldWrapper.style.justifySelf = 'stretch';
                const input = searchFieldWrapper.querySelector('.form-control');
                if (input) {
                    input.style.width = '';
                    // force reflow
                    void input.offsetWidth;
                }
            }
        } catch (e) { /* ignore */ }
        
        // Dispatch a resize to help browsers recalc grid/flex sizing
        setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 50);
    });

    // If user presses Back immediately after print, consume the guard and stay on dashboard.
    window.addEventListener('popstate', function () {
        if (hasPrintBackGuard) {
            hasPrintBackGuard = false;
        }
    });
})();
