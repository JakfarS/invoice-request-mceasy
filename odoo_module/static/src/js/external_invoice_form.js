/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import dom from "@web/legacy/js/core/dom";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExternalInvoiceForm extends Component {
    static template = "odoo_module.ExternalInvoiceForm";

    setup() {
        this.rootRef = useRef("root");
        this.rpc = useService("rpc");
        
        this.state = useState({
            loading: false,
            message: '',
            messageType: 'info',
            error: false,
            success: false,
        });

        onMounted(() => {
            const selectEl = this.rootRef.el.querySelector('#sale_order');
            if (selectEl) {
                const handler = () => this.refreshSaleOrderOptions();
                selectEl.addEventListener('focus', handler);
                selectEl.addEventListener('click', handler);
            }
        });
    }

    async onClickSubmit() {
        const form = this.rootRef.el.querySelector('#invoice-request-form');
        const formData = new FormData(form);
        const saleOrderId = formData.get('sale_order_id');
        
        if (!saleOrderId) {
            this.state.error = 'Please select a sale order.';
            return;
        }

        const button = this.rootRef.el.querySelector('.o_invoice_request_submit');
        const icon = button.removeChild(button.firstChild);
        const restoreBtnLoading = dom.addButtonLoadingEffect(button);

        try {
            const data = await this.rpc('/external/sale-invoice/' + this.props.token + '/request', { 
                sale_order_id: saleOrderId 
            });
            
            if (data.force_refresh) {
                restoreBtnLoading();
                button.prepend(icon);
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    window.location.reload();
                }
                return new Promise(() => {});
            }
            
            this.state.error = data.error || false;
            this.state.success = !data.error && {
                message: data.message,
                redirectUrl: data.redirect_url,
                redirectMessage: data.redirect_message,
            };
            
            if (data.success) {
                form.reset();
                setTimeout(() => window.location.reload(), 1500);
            }
        } catch (error) {
            this.state.error = 'Network error. Please try again.';
        } finally {
            restoreBtnLoading();
            button.prepend(icon);
        }
    }

    async refreshSaleOrderOptions() {
        if (!this.props.token) {
            return;
        }
        try {
            const data = await this.rpc('/external/sale-invoice/' + this.props.token + '/available_sos', {});
            if (!data || !data.success) {
                this.state.error = (data && data.error) || _t('Failed to refresh sale orders.');
                return;
            }
            const selectEl = this.rootRef.el.querySelector('#sale_order');
            if (!selectEl) return;
            const currentVal = selectEl.value;
            // Rebuild options
            selectEl.innerHTML = '';
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = _t('Choose a sale order...');
            selectEl.appendChild(placeholder);
            for (const so of (data.sale_orders || [])) {
                const opt = document.createElement('option');
                opt.value = String(so.id);
                opt.textContent = (so.name || '') + ' - ' + (so.amount_total != null ? so.amount_total : 0);
                selectEl.appendChild(opt);
            }
            // If previous value still exists, keep it; else clear selection
            if (currentVal && Array.from(selectEl.options).some(o => o.value === currentVal)) {
                selectEl.value = currentVal;
            } else {
                selectEl.value = '';
            }
        } catch (e) {
            this.state.error = _t('Network error during refresh.');
        }
    }
}

registry.category("public_components").add("odoo_module.external_invoice_form", ExternalInvoiceForm);
