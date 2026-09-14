"""
Risk Assessment
Combine OCR, validation, tampering, and face results into risk score
"""

import json


def calculate_risk_score(ocr_result, validation_result, tampering_result=None, face_result=None):
    """
    Calculate overall risk score combining all analysis results
    
    Args:
        ocr_result: OCR extraction result with confidence
        validation_result: Validation result with violations
        tampering_result: Tampering detection result (optional)
        face_result: Face verification result (optional)
    
    Returns:
        dict: {
            'riskScore': 0-100,
            'riskLevel': 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL',
            'requiresHumanReview': bool,
            'factors': [],
            'recommendation': str
        }
    """
    
    factors = []
    risk_score = 0
    
    # 1. OCR Confidence Factor (weight: 20 points)
    ocr_confidence = _clamp_number(ocr_result.get('confidence', 0))
    if ocr_confidence < 0.5:
        factors.append({
            'category': 'ocr',
            'finding': f'Low OCR confidence: {ocr_confidence}',
            'weight': 20,
            'confidence': 0.85
        })
        risk_score += 20
    elif ocr_confidence < 0.7:
        factors.append({
            'category': 'ocr',
            'finding': f'Moderate OCR confidence: {ocr_confidence}',
            'weight': 10,
            'confidence': 0.8
        })
        risk_score += 10
    
    # 2. Validation Violations (weight: 30 points)
    violations = validation_result.get('violations', []) or []
    # Missing validation output must never be treated as a clean document.
    is_valid = validation_result.get('isValid') is True
    
    error_count = sum(1 for v in violations if v.get('severity') == 'error')
    warning_count = sum(1 for v in violations if v.get('severity') == 'warning')

    if error_count > 0:
        factors.append({
            'category': 'validation',
            'finding': f'{error_count} validation errors: {", ".join(v["field"] for v in violations if v.get("severity") == "error")}',
            'weight': min(30, 10 + error_count * 5),
            'confidence': 0.9
        })
        risk_score += min(30, 10 + error_count * 5)

    if warning_count > 0:
        factors.append({
            'category': 'validation',
            'finding': f'{warning_count} validation warnings',
            'weight': min(10, warning_count * 3),
            'confidence': 0.7
        })
        risk_score += min(10, warning_count * 3)
    
    # 3. Tampering Detection (weight: 35 points)
    if tampering_result and tampering_result.get('success'):
        tampering_detected = tampering_result.get('tamperingDetected', False)
        tampering_confidence = _clamp_number(tampering_result.get('confidence', 0))
        
        if tampering_detected:
            weight = min(35, int(tampering_confidence * 35))
            factors.append({
                'category': 'tampering',
                'finding': f'Potential tampering detected ({tampering_confidence} confidence): {", ".join(f["type"] for f in tampering_result.get("findings", []))}',
                'weight': weight,
                'confidence': tampering_confidence
            })
            risk_score += weight
    elif tampering_result is not None:
        factors.append({
            'category': 'tampering',
            'finding': 'Tampering analysis was unavailable; manual inspection is required.',
            'weight': 5,
            'confidence': 1.0,
        })
        risk_score += 5
    
    # 4. Face Verification (weight: 15 points)
    if face_result and face_result.get('success'):
        match_status = face_result.get('matchStatus', 'not_verified')
        face_confidence = face_result.get('confidence', 0)
        similarity = face_result.get('similarity', 0)
        
        if match_status == 'match':
            # Match is good, reduce risk
            risk_score = max(0, risk_score - 5)
        elif match_status == 'no_match':
            factors.append({
                'category': 'face',
                'finding': f'Face mismatch detected (similarity: {similarity})',
                'weight': 15,
                'confidence': face_confidence
            })
            risk_score += 15
        elif match_status == 'inconclusive':
            factors.append({
                'category': 'face',
                'finding': f'Face verification inconclusive',
                'weight': 5,
                'confidence': face_confidence
            })
            risk_score += 5
        elif match_status == 'not_verified':
            # Face not detected, moderate increase
            factors.append({
                'category': 'face',
                'finding': 'Face verification not possible',
                'weight': 3,
                'confidence': 0.6
            })
            risk_score += 3
    else:
        factors.append({
            'category': 'face',
            'finding': 'Face verification was not run.',
            'weight': 3,
            'confidence': 1.0,
        })
        risk_score += 3
    
    # Clamp risk score to 0-100
    risk_score = max(0, min(100, risk_score))
    
    # Determine risk level
    if risk_score < 25:
        risk_level = 'LOW'
        recommendation = 'Document appears valid. No immediate action required.'
    elif risk_score < 50:
        risk_level = 'MEDIUM'
        recommendation = 'Document has some inconsistencies. Recommend manual review.'
    elif risk_score < 75:
        risk_level = 'HIGH'
        recommendation = 'Document shows multiple warning signs. Recommend thorough investigation.'
    else:
        risk_level = 'CRITICAL'
        recommendation = 'Severe inconsistencies detected. Escalate for urgent human review; do not make an automated rejection decision.'
    
    uncertainty = any(f.get('category') in {'ocr', 'face'} and f.get('weight', 0) > 0 for f in factors)
    requires_review = risk_level in ['MEDIUM', 'HIGH', 'CRITICAL'] or not is_valid or uncertainty
    
    return {
        'riskScore': risk_score,
        'riskLevel': risk_level,
        'requiresHumanReview': requires_review,
        'factors': factors,
        'recommendation': recommendation
    }


def _clamp_number(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


if __name__ == '__main__':
    # For testing
    import sys
    data = json.load(sys.stdin)
    ocr = data.get('ocr', {})
    validation = data.get('validation', {})
    tampering = data.get('tampering')
    face = data.get('face')
    
    result = calculate_risk_score(ocr, validation, tampering, face)
    print(json.dumps(result))
