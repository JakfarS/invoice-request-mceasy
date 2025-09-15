# -*- coding: utf-8 -*-
{
    'name': 'External Invoice Request',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'External Invoice Request System',
    'description': """
        This module provides an external invoice request system that allows partners
        to request invoices for their sale orders without logging into Odoo. This module is for McEasy Technical Test.
        
        Features:
        - External token-based access for partners
        - External form for invoice requests
        - Invoice approval workflow
        - PDF invoice download functionality
    """,
    'author': 'Jakfar Siddiq',
    # 'website': 'https://www.odoo.com',
    'depends': [
        'base',
        'sale',
        'account',
        'web',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/invoice_request_views.xml',
        'views/partner_views.xml',
        'templates/external_invoice_request.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # 'odoo_module/static/src/xml/external_invoice_form.xml',
            # 'odoo_module/static/src/js/external_invoice_form.js',
            'odoo_module/static/src/css/external_invoice_form.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': '_generate_partner_token',
}
