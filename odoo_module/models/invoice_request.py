# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import uuid


class InvoiceRequest(models.Model):
    _name = 'invoice.request'
    _description = 'Invoice Request'
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade'
    )
    sale_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade'
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ], string='Status', default='pending', required=True)
    
    # Additional fields for better tracking
    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        readonly=True
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    notes = fields.Text(string='Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('invoice.request') or _('New')
        return super(InvoiceRequest, self).create(vals)

    def approval_request(self):
        """Approve the invoice request and create invoice"""
        for record in self:
            if record.state != 'pending':
                raise UserError(_('Only pending requests can be approved.'))
            
            if not record.sale_id:
                raise UserError(_('Sale Order is required to create invoice.'))
            
            # Check if sale order is in correct state
            if record.sale_id.state != 'sale':
                raise UserError(_('Sale Order must be in "Sale" state to create invoice.'))
            
            if record.sale_id.invoice_status != 'to invoice':
                raise UserError(_('Sale Order must have "To Invoice" status to create invoice.'))
            
            # Create invoice from sale order
            invoice_vals = {
                'partner_id': record.partner_id.id,
                'move_type': 'out_invoice',
                'invoice_origin': record.sale_id.name,
                'invoice_line_ids': [],
            }
            
            # Create invoice lines from sale order lines
            for line in record.sale_id.order_line:
                if line.product_id.invoice_policy == 'order':
                    invoice_line_vals = {
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'name': line.name,
                        'product_uom_id': line.product_uom.id,
                    }
                    invoice_vals['invoice_line_ids'].append((0, 0, invoice_line_vals))
            
            # Create the invoice
            invoice = self.env['account.move'].create(invoice_vals)
            
            # Post the invoice
            invoice.action_post()
            
            # Update the request
            record.write({
                'state': 'approved',
                'invoice_id': invoice.id,
                'approval_date': fields.Datetime.now(),
                'approved_by': self.env.user.id,
            })
            
            # Update sale order invoice status
            record.sale_id._compute_invoice_status()
        
        return True


    def action_reset_to_pending(self):
        """Reset request to pending state"""
        for record in self:
            if record.state not in ['approved', 'rejected']:
                raise UserError(_('Only approved or rejected requests can be reset.'))
            record.write({
                'state': 'pending',
                'approval_date': False,
                'approved_by': False,
            })
        return True

    @api.constrains('partner_id', 'sale_id')
    def _check_partner_sale_consistency(self):
        """Ensure the sale order belongs to the partner"""
        for record in self:
            if record.partner_id and record.sale_id:
                if record.sale_id.partner_id != record.partner_id:
                    raise ValidationError(_('The sale order must belong to the selected partner.'))
                # Prevent selecting SO that is not invoiceable anymore
                if record.sale_id.state != 'sale' or record.sale_id.invoice_status != 'to invoice':
                    raise ValidationError(_('The sale order is no longer available for invoicing.'))
                # Prevent duplicate requests on the same SO in pending/approved
                existing = self.env['invoice.request'].search([
                    ('id', '!=', record.id),
                    ('partner_id', '=', record.partner_id.id),
                    ('sale_id', '=', record.sale_id.id),
                    ('state', 'in', ['pending', 'approved'])
                ], limit=1)
                if existing:
                    raise ValidationError(_('A request already exists for this sale order.'))

    def get_available_sale_orders(self, partner_id):
        """Get sale orders available for invoicing for a partner"""
        return self.env['sale.order'].search([
            ('partner_id', '=', partner_id),
            ('state', '=', 'sale'),
            ('invoice_status', '=', 'to invoice')
        ])
