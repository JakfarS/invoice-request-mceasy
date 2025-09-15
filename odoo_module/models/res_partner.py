# -*- coding: utf-8 -*-

from odoo import models, fields, api
import uuid


class ResPartner(models.Model):
    _inherit = 'res.partner'

    external_token = fields.Char(
        string='External Token',
        help='Token for external access to invoice request system',
        copy=False,
        index=True
    )
    invoice_request_ids = fields.One2many(
        'invoice.request',
        'partner_id',
        string='Invoice Requests'
    )
    invoice_request_count = fields.Integer(
        string='Invoice Requests Count',
        compute='_compute_invoice_request_count'
    )

    @api.depends('invoice_request_ids')
    def _compute_invoice_request_count(self):
        for partner in self:
            partner.invoice_request_count = len(partner.invoice_request_ids)

    def generate_external_token(self):
        """Generate a unique external token for the partner"""
        for partner in self:
            if not partner.external_token:
                partner.external_token = str(uuid.uuid4())
        return True

    def action_view_invoice_requests(self):
        """Action to view invoice requests for this partner"""
        action = self.env['ir.actions.act_window']._for_xml_id('odoo_module.action_invoice_request')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
