"""
Risk calculator service wrapper
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.risk_calculator import calculate_risk_score


if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        ocr = data.get('ocr', {})
        validation = data.get('validation', {})
        tampering = data.get('tampering')
        face = data.get('face')
        result = calculate_risk_score(ocr, validation, tampering, face)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({
            'error': str(e), 'riskScore': 100, 'riskLevel': 'CRITICAL',
            'requiresHumanReview': True,
            'factors': [{'category': 'system', 'finding': 'Risk calculation failed; manual review is required.', 'weight': 100, 'confidence': 1.0}],
            'recommendation': 'Risk calculation failed. Escalate for human review.'
        }))
