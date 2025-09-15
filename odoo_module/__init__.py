# -*- coding: utf-8 -*-

def _generate_partner_token(env):
    """Post-installation hook to generate external tokens for existing partners"""
    # Generate external tokens for all existing partners that don't have one
    partners_without_token = env['res.partner'].search([
        ('external_token', '=', False)
    ])
    
    if partners_without_token:
        partners_without_token.generate_external_token()
        env.cr.commit()
        print(f"Generated external tokens for {len(partners_without_token)} partners")

from . import models
from . import controllers