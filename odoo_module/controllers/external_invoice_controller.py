# -*- coding: utf-8 -*-

import json
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError, ValidationError


class ExternalInvoiceController(http.Controller):

    @http.route('/external/sale-invoice/<string:token>', type='http', auth='public', website=True, csrf=False)
    def external_invoice_form(self, token, **kwargs):
        """External invoice request form accessible without login"""
        partner = request.env['res.partner'].sudo().search([('external_token', '=', token)], limit=1)
        
        if not partner:
            return request.render('odoo_module.token_not_found', {
                'message': 'Invalid or expired token. Please contact your administrator.'
            })
        
        # Get sale orders available for this partner excluding those already requested (pending/approved)
        requested_sale_ids = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id),
            ('sale_id', '!=', False),
            ('state', 'in', ['pending', 'approved'])
        ]).mapped('sale_id').ids

        sale_orders = request.env['sale.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sale'),
            ('invoice_status', '=', 'to invoice'),
            ('id', 'not in', requested_sale_ids),
        ])
        
        # Get pending invoice requests
        pending_requests = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'pending')
        ])
        
        # Get approved requests with invoices
        approved_requests = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'approved'),
            ('invoice_id', '!=', False)
        ])
        
        # Build JSON-friendly props for OWL component
        props = {
            'partner': {
                'id': partner.id,
                'name': partner.name or '',
                'email': partner.email or '',
            },
            'sale_orders': [
                {
                    'id': so.id,
                    'name': so.name or '',
                    'amount_total': so.amount_total,
                }
                for so in sale_orders
            ],
            'pending_requests': [
                {
                    'id': req.id,
                    'name': req.name or '',
                }
                for req in pending_requests
            ],
            'approved_requests': [
                {
                    'id': req.id,
                    'name': req.name or '',
                }
                for req in approved_requests
            ],
            'token': token,
        }

        return request.render('odoo_module.external_invoice_form', {
            'partner': partner,
            'sale_orders': sale_orders,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
            'token': token,
            'external_invoice_form_props_json': json.dumps(props),
        })

    @http.route('/external/sale-invoice/<string:token>/available_sos', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def get_available_sale_orders(self, token, **kwargs):
        """Return currently available sale orders for a partner token.
        Used by the client to refresh the dropdown without full page reload.
        """
        partner = request.env['res.partner'].sudo().search([('external_token', '=', token)], limit=1)

        if not partner:
            return json.dumps({'success': False, 'error': 'Invalid or expired token'})

        requested_sale_ids = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id),
            ('sale_id', '!=', False),
            ('state', 'in', ['pending', 'approved'])
        ]).mapped('sale_id').ids

        sale_orders = request.env['sale.order'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'sale'),
            ('invoice_status', '=', 'to invoice'),
            ('id', 'not in', requested_sale_ids),
        ])

        data = [{
            'id': so.id,
            'name': so.name or '',
            'amount_total': so.amount_total,
        } for so in sale_orders]

        return json.dumps({'success': True, 'sale_orders': data})

    @http.route('/external/sale-invoice/<string:token>/request', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def create_invoice_request(self, token, **kwargs):
        """Create a new invoice request"""
        partner = request.env['res.partner'].sudo().search([('external_token', '=', token)], limit=1)
        
        if not partner:
            return json.dumps({'success': False, 'message': 'Invalid token'})
        
        sale_order_id = kwargs.get('sale_order_id')
        if not sale_order_id:
            return json.dumps({'success': False, 'message': 'Sale order is required'})
        
        try:
            # Verify the sale order belongs to the partner
            sale_order = request.env['sale.order'].sudo().browse(int(sale_order_id))
            if sale_order.partner_id != partner:
                return json.dumps({'success': False, 'message': 'Invalid sale order'})
            
            # Check if there's already a request (pending/approved) for this sale order
            existing_request = request.env['invoice.request'].sudo().search([
                ('partner_id', '=', partner.id),
                ('sale_id', '=', sale_order_id),
                ('state', 'in', ['pending', 'approved'])
            ], limit=1)
            
            if existing_request:
                return json.dumps({'success': False, 'message': 'A pending request already exists for this sale order'})

            # Validate SO is still available (to invoice and in sale state)
            if sale_order.state != 'sale' or sale_order.invoice_status != 'to invoice':
                return json.dumps({'success': False, 'message': 'Selected sale order is no longer available for invoicing'})
            
            # Create the invoice request
            invoice_request = request.env['invoice.request'].sudo().create({
                'partner_id': partner.id,
                'sale_id': sale_order_id,
                'state': 'pending',
            })
            
            return json.dumps({
                'success': True, 
                'message': 'Invoice request created successfully',
                'request_id': invoice_request.id
            })
            
        except Exception as e:
            return json.dumps({'success': False, 'message': str(e)})

    @http.route('/external/sale-invoice/<string:token>/download/<int:invoice_id>', type='http', auth='public', website=True, csrf=False)
    def download_invoice_pdf(self, token, invoice_id, **kwargs):
        """Download invoice PDF"""
        partner = request.env['res.partner'].sudo().search([('external_token', '=', token)], limit=1)
        
        if not partner:
            return request.not_found()
        
        # Verify the invoice belongs to a request from this partner
        invoice_request = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id),
            ('invoice_id', '=', invoice_id),
            ('state', '=', 'approved')
        ], limit=1)
        
        if not invoice_request:
            return request.not_found()
        
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        if not invoice.exists():
            return request.not_found()
        
        # Generate PDF report
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf('account.report_invoice', [invoice_id])
        
        if not report or not report[0]:
            return request.not_found()
        
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(report[0])),
            ('Content-Disposition', 'attachment; filename="Invoice_%s.pdf"' % invoice.name)
        ]
        
        return request.make_response(report[0], headers=pdfhttpheaders)

    @http.route('/external/sale-invoice/<string:token>/status', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def get_request_status(self, token, **kwargs):
        """Get current status of invoice requests for AJAX updates"""
        partner = request.env['res.partner'].sudo().search([('external_token', '=', token)], limit=1)
        
        if not partner:
            return json.dumps({'success': False, 'message': 'Invalid token'})
        
        # Return separated lists for pending and approved
        pending_reqs = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id), ('state', '=', 'pending')
        ])
        approved_reqs = request.env['invoice.request'].sudo().search([
            ('partner_id', '=', partner.id), ('state', '=', 'approved')
        ])

        def _serialize(recs):
            res = []
            for req in recs:
                res.append({
                    'id': req.id,
                    'name': req.name or '',
                    'sale_order': req.sale_id.name,
                    'state': req.state,
                    'request_date': req.request_date.strftime('%Y-%m-%d %H:%M') if req.request_date else '',
                    'approval_date': req.approval_date.strftime('%Y-%m-%d %H:%M') if req.approval_date else '',
                    'invoice_id': req.invoice_id.id if req.invoice_id else None,
                    'invoice_name': req.invoice_id.name if req.invoice_id else None,
                })
            return res

        return json.dumps({
            'success': True,
            'pending_requests': _serialize(pending_reqs),
            'approved_requests': _serialize(approved_reqs),
        })
