"""
Placeholder for Python AI services
Will call individual extraction/detection modules
Implemented in Phase 2+
"""

import json
import sys

def handle_request(service_type):
    """Route service requests"""
    response = {
        'status': 'not_implemented',
        'message': f'{service_type} service will be implemented in Phase 2+'
    }
    return response

if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        service = data.get('service', 'unknown')
        output = handle_request(service)
        print(json.dumps(output))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
