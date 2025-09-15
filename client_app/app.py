#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import xmlrpc.client
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Odoo connection configuration
ODOO_URL = os.getenv('ODOO_URL', 'http://localhost:8017')
ODOO_DB = os.getenv('ODOO_DB', 'odoo17')
ODOO_USERNAME = os.getenv('ODOO_USERNAME', 'admin')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD', 'a')

class OdooXMLRPCClient:
    """XML-RPC client for Odoo operations"""
    
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = None
        self.models = None
        
    def authenticate(self):
        """Authenticate with Odoo and get user ID"""
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            
            if not self.uid:
                raise Exception("Authentication failed")
                
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            logger.info(f"Successfully authenticated as user {self.uid}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise e
    
    def execute(self, model, method, *args):
        """Execute a method on a model"""
        try:
            if not self.uid:
                self.authenticate()
                
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, method, args[0] if args else [],
                args[1] if len(args) > 1 else {}
            )
        except Exception as e:
            logger.error(f"XML-RPC execution error: {str(e)}")
            raise e

# Initialize Odoo client
odoo_client = OdooXMLRPCClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)

def initialize_odoo():
    """Initialize Odoo connection on startup"""
    try:
        odoo_client.authenticate()
        logger.info("Odoo client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Odoo client: {str(e)}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Odoo XML-RPC Client',
        'odoo_connected': odoo_client.uid is not None
    })

@app.route('/api/sale-orders', methods=['GET'])
def get_sale_orders():
    """Get list of sale orders"""
    try:
        # Parse query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        domain = request.args.get('domain', '[]')
        
        # Parse domain if provided as JSON string
        try:
            domain_list = json.loads(domain) if domain != '[]' else []
        except json.JSONDecodeError:
            domain_list = []
        
        # Search and read sale orders
        sale_orders = odoo_client.execute(
            'sale.order',
            'search_read',
            domain_list,
            {
                'fields': [
                    'id', 'name', 'partner_id', 'state', 'invoice_status',
                    'amount_total', 'currency_id', 'date_order', 'user_id'
                ],
                'limit': limit,
                'offset': offset,
                'order': 'id desc'
            }
        )
        
        return jsonify({
            'success': True,
            'data': sale_orders,
            'count': len(sale_orders)
        })
        
    except Exception as e:
        logger.error(f"Error getting sale orders: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sale-orders/<int:order_id>', methods=['GET'])
def get_sale_order_detail(order_id):
    """Get detailed information about a specific sale order"""
    try:
        sale_order = odoo_client.execute(
            'sale.order',
            'read',
            [order_id],
            {
                'fields': [
                    'id', 'name', 'partner_id', 'state', 'invoice_status',
                    'amount_total', 'currency_id', 'date_order', 'user_id',
                    'order_line', 'note', 'payment_term_id', 'fiscal_position_id'
                ]
            }
        )
        
        if not sale_order:
            return jsonify({
                'success': False,
                'error': 'Sale order not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': sale_order[0]
        })
        
    except Exception as e:
        logger.error(f"Error getting sale order detail: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sale-orders', methods=['POST'])
def create_sale_order():
    """Create a new sale order"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['partner_id', 'order_line']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Create sale order
        order_id = odoo_client.execute(
            'sale.order',
            'create',
            [data]
        )
        
        return jsonify({
            'success': True,
            'data': {
                'id': order_id,
                'message': 'Sale order created successfully'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sale-orders/<int:order_id>', methods=['PUT'])
def update_sale_order(order_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # FIX → bungkus order_id dalam list
        result = odoo_client.execute(
            'sale.order',
            'write',
            [[order_id], data]
        )

        return jsonify({
            'success': True,
            'data': {
                'id': order_id,
                'updated': result,
                'message': 'Sale order updated successfully'
            }
        })

    except Exception as e:
        logger.error(f"Error updating sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

        
    except Exception as e:
        logger.error(f"Error updating sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sale-orders/<int:order_id>/confirm', methods=['POST'])
def confirm_sale_order(order_id):
    """Confirm a sale order"""
    try:
        result = odoo_client.execute(
            'sale.order',
            'action_confirm',
            [order_id]
        )
        
        return jsonify({
            'success': True,
            'data': {
                'id': order_id,
                'confirmed': result,
                'message': 'Sale order confirmed successfully'
            }
        })
        
    except Exception as e:
        logger.error(f"Error confirming sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sale-orders/<int:order_id>/cancel', methods=['POST'])
def cancel_sale_order(order_id):
    """Cancel a sale order"""
    try:
        # FIX → bungkus id di list
        result = odoo_client.execute(
            'sale.order',
            'write',
            [[order_id], {'state': 'cancel'}]
        )
        
        return jsonify({
            'success': True,
            'data': {
                'id': order_id,
                'cancelled': result,
                'message': 'Sale order cancelled successfully'
            }
        })
        
    except Exception as e:
        logger.error(f"Error cancelling sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sale-orders/<int:order_id>/reset', methods=['POST'])
def reset_sale_order(order_id):
    """Reset a sale order to draft"""
    try:
        # FIX: bungkus di list of list
        result = odoo_client.execute(
            'sale.order',
            'action_draft',
            [[order_id]]
        )
        
        return jsonify({
            'success': True,
            'data': {
                'id': order_id,
                'reset': result,
                'message': 'Sale order reset to draft successfully'
            }
        })
        
    except Exception as e:
        logger.error(f"Error resetting sale order: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 4000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    initialize_odoo()   # panggil langsung di startup
    
    logger.info(f"Starting Odoo XML-RPC Client on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
