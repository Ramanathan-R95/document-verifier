"""
Generic document validation.
Validates extracted document fields for supported types.
"""

import json
import re
import sys
from datetime import datetime

sys.path.insert(0, '/home/beesto/sih/ai')

from config import DOCUMENT_RULES


def validate_document(fields, document_type='passport'):
    """Main validation entry point for supported document types."""
    rules = DOCUMENT_RULES.get(document_type)
    if not rules:
        violations = [{
            'field': 'document_type',
            'rule': 'unsupported',
            'severity': 'error',
            'message': f'Document type "{document_type}" is not supported yet'
        }]
        return {
            'isValid': False,
            'violations': violations,
            'status': _validation_status(violations),
        }

    required_fields = rules.get('requiredFields', [])
    violations = []

    for field in required_fields:
        value = fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    if document_type == 'passport':
        result = validate_passport_fields(fields, violations)
    elif document_type == 'visa':
        result = validate_visa_fields(fields, violations)
    elif document_type == 'national_id':
        result = validate_national_id_fields(fields, violations)
    elif document_type == 'driving_license':
        result = validate_driving_license_fields(fields, violations)
    elif document_type == 'permit':
        result = validate_permit_fields(fields, violations)
    else:
        result = {'isValid': False, 'violations': violations}

    result['status'] = _validation_status(result.get('violations', []))
    return result


def _validation_status(violations):
    if any(v.get('severity') == 'error' for v in violations):
        return 'failed'
    if any(v.get('severity') == 'warning' for v in violations):
        return 'warning'
    return 'valid'


def validate_passport_fields(extracted_fields, pre_violations=None):
    violations = list(pre_violations or [])
    required_fields = ['name', 'passportNumber', 'nationality', 'dateOfBirth', 'gender', 'expiryDate']

    if pre_violations is None:
      for field in required_fields:
        value = extracted_fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    passport_num = extracted_fields.get('passportNumber')
    if passport_num and not re.match(r'^[A-Z0-9]{6,9}$', str(passport_num).upper()):
        violations.append({
            'field': 'passportNumber',
            'rule': 'format_check',
            'severity': 'error',
            'message': f'Passport number "{passport_num}" does not match expected format (6-9 alphanumeric)'
        })

    gender = extracted_fields.get('gender')
    if gender and str(gender).upper() not in ['M', 'F']:
        violations.append({
            'field': 'gender',
            'rule': 'format_check',
            'severity': 'error',
            'message': f'Gender "{gender}" must be M or F'
        })

    _validate_date_field('dateOfBirth', extracted_fields.get('dateOfBirth'), violations)
    _validate_date_field('expiryDate', extracted_fields.get('expiryDate'), violations)

    expiry = extracted_fields.get('expiryDate')
    if expiry and _is_date_expired(expiry):
        violations.append({
            'field': 'expiryDate',
            'rule': 'expiry_check',
            'severity': 'error',
            'message': f'Passport expired on {expiry}'
        })

    dob = extracted_fields.get('dateOfBirth')
    if dob and expiry:
        try:
            dob_date = _parse_date(dob)
            expiry_date = _parse_date(expiry)
            if dob_date >= expiry_date:
                violations.append({
                    'field': 'dateOfBirth',
                    'rule': 'date_relationship',
                    'severity': 'error',
                    'message': 'Date of birth cannot be after or equal to expiry date'
                })
        except Exception:
            pass

    nationality = extracted_fields.get('nationality')
    if nationality and not re.match(r'^[A-Z]{3}$', str(nationality).upper()):
        violations.append({
            'field': 'nationality',
            'rule': 'format_check',
            'severity': 'warning',
            'message': f'Nationality "{nationality}" does not match 3-letter ISO format'
        })

    return {
        'isValid': not any(v['severity'] == 'error' for v in violations),
        'violations': violations,
    }


def validate_visa_fields(extracted_fields, pre_violations=None):
    violations = list(pre_violations or [])
    required_fields = ['visaNumber', 'visaType', 'entryValidity', 'stayDuration', 'issueDate', 'expiryDate']

    if pre_violations is None:
      for field in required_fields:
        value = extracted_fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    visa_number = extracted_fields.get('visaNumber')
    if visa_number and not re.match(r'^[A-Z0-9]{6,12}$', str(visa_number).upper()):
        violations.append({
            'field': 'visaNumber',
            'rule': 'format_check',
            'severity': 'error',
            'message': f'Visa number "{visa_number}" does not match expected format (6-12 alphanumeric)'
        })

    _validate_date_field('issueDate', extracted_fields.get('issueDate'), violations)
    _validate_date_field('expiryDate', extracted_fields.get('expiryDate'), violations)

    issue_date = extracted_fields.get('issueDate')
    expiry = extracted_fields.get('expiryDate')
    if issue_date and expiry:
        try:
            if _parse_date(issue_date) > _parse_date(expiry):
                violations.append({
                    'field': 'issueDate',
                    'rule': 'date_relationship',
                    'severity': 'error',
                    'message': 'Issue date cannot be after expiry date'
                })
        except Exception:
            pass

    if expiry and _is_date_expired(expiry):
        violations.append({
            'field': 'expiryDate',
            'rule': 'expiry_check',
            'severity': 'error',
            'message': f'Visa expired on {expiry}'
        })

    stay_duration = extracted_fields.get('stayDuration')
    if stay_duration and not re.match(r'^[0-9]+\s*(day|days|month|months|year|years)?$', str(stay_duration), re.IGNORECASE):
        violations.append({
            'field': 'stayDuration',
            'rule': 'format_check',
            'severity': 'warning',
            'message': f'Stay duration "{stay_duration}" should be numeric with a duration unit'
        })

    return {
        'isValid': not any(v['severity'] == 'error' for v in violations),
        'violations': violations,
    }


def validate_national_id_fields(extracted_fields, pre_violations=None):
    violations = list(pre_violations or [])
    required_fields = ['fullName', 'idNumber', 'dateOfBirth', 'issueDate', 'expiryDate']

    if pre_violations is None:
      for field in required_fields:
        value = extracted_fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    _validate_date_field('dateOfBirth', extracted_fields.get('dateOfBirth'), violations)
    _validate_date_field('issueDate', extracted_fields.get('issueDate'), violations)
    _validate_date_field('expiryDate', extracted_fields.get('expiryDate'), violations)

    if extracted_fields.get('idNumber') and not re.match(r'^[A-Z0-9]{6,20}$', str(extracted_fields.get('idNumber')).upper()):
        violations.append({
            'field': 'idNumber',
            'rule': 'format_check',
            'severity': 'error',
            'message': 'ID number format is not valid for this document type'
        })

    _validate_expiry_relationship(extracted_fields, violations)
    return {'isValid': not any(v['severity'] == 'error' for v in violations), 'violations': violations}


def validate_driving_license_fields(extracted_fields, pre_violations=None):
    violations = list(pre_violations or [])
    required_fields = ['fullName', 'licenseNumber', 'dateOfBirth', 'issueDate', 'expiryDate']

    if pre_violations is None:
      for field in required_fields:
        value = extracted_fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    _validate_date_field('dateOfBirth', extracted_fields.get('dateOfBirth'), violations)
    _validate_date_field('issueDate', extracted_fields.get('issueDate'), violations)
    _validate_date_field('expiryDate', extracted_fields.get('expiryDate'), violations)

    if extracted_fields.get('licenseNumber') and not re.match(r'^[A-Z0-9]{6,20}$', str(extracted_fields.get('licenseNumber')).upper()):
        violations.append({
            'field': 'licenseNumber',
            'rule': 'format_check',
            'severity': 'error',
            'message': 'License number format is not valid for this document type'
        })

    _validate_expiry_relationship(extracted_fields, violations)
    return {'isValid': not any(v['severity'] == 'error' for v in violations), 'violations': violations}


def validate_permit_fields(extracted_fields, pre_violations=None):
    violations = list(pre_violations or [])
    required_fields = ['holderName', 'permitNumber', 'permitType', 'issueDate', 'expiryDate']

    if pre_violations is None:
      for field in required_fields:
        value = extracted_fields.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            violations.append({
                'field': field,
                'rule': 'required_field',
                'severity': 'error',
                'message': f'{field} is required but missing'
            })

    _validate_date_field('issueDate', extracted_fields.get('issueDate'), violations)
    _validate_date_field('expiryDate', extracted_fields.get('expiryDate'), violations)

    if extracted_fields.get('permitNumber') and not re.match(r'^[A-Z0-9]{6,20}$', str(extracted_fields.get('permitNumber')).upper()):
        violations.append({
            'field': 'permitNumber',
            'rule': 'format_check',
            'severity': 'error',
            'message': 'Permit number format is not valid for this document type'
        })

    if extracted_fields.get('expiryDate') and _is_date_expired(extracted_fields.get('expiryDate')):
        violations.append({
            'field': 'expiryDate',
            'rule': 'expiry_check',
            'severity': 'error',
            'message': 'Permit is expired'
        })

    return {'isValid': not any(v['severity'] == 'error' for v in violations), 'violations': violations}


def _validate_date_field(field_name, value, violations):
    if value and not _is_valid_date(value):
        violations.append({
            'field': field_name,
            'rule': 'date_format',
            'severity': 'error',
            'message': f'{field_name} "{value}" is not in valid format (DD/MM/YYYY or DD-MM-YYYY)'
        })


def _validate_expiry_relationship(fields, violations):
    dob = fields.get('dateOfBirth')
    issue = fields.get('issueDate')
    expiry = fields.get('expiryDate')

    if issue and expiry:
        try:
            if _parse_date(issue) > _parse_date(expiry):
                violations.append({
                    'field': 'issueDate',
                    'rule': 'date_relationship',
                    'severity': 'error',
                    'message': 'Issue date cannot be after expiry date'
                })
        except Exception:
            pass

    if dob and expiry:
        try:
            if _parse_date(dob) >= _parse_date(expiry):
                violations.append({
                    'field': 'dateOfBirth',
                    'rule': 'date_relationship',
                    'severity': 'error',
                    'message': 'Date of birth cannot be after or equal to expiry date'
                })
        except Exception:
            pass

    if expiry and _is_date_expired(expiry):
        violations.append({
            'field': 'expiryDate',
            'rule': 'expiry_check',
            'severity': 'error',
            'message': f'Document expired on {expiry}'
        })


def _is_valid_date(date_str):
    if not date_str:
        return False
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']:
        try:
            datetime.strptime(str(date_str), fmt)
            return True
        except ValueError:
            continue
    return False


def _parse_date(date_str):
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']:
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    raise ValueError(f'Could not parse date: {date_str}')


def _is_date_expired(date_str):
    try:
        return _parse_date(date_str) < datetime.now()
    except Exception:
        return False


if __name__ == '__main__':
    data = json.load(sys.stdin)
    fields = data.get('fields', {})
    doc_type = data.get('documentType', 'passport')
    result = validate_document(fields, doc_type)
    print(json.dumps(result))
