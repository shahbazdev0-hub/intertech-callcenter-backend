# backend/app/utils/csv_parser.py
import pandas as pd
import re
from typing import List, Tuple, Dict
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

class CSVParser:
    """Parse and validate CSV/Excel files for bulk campaigns"""
    
    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, str]:
        """
        Validate and format phone number
        Returns: (is_valid, formatted_number)
        """
        if not phone or pd.isna(phone):
            return False, ""
        
        # Convert to string and remove whitespace
        phone_str = str(phone).strip()
        
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', phone_str)
        
        # Check minimum length
        if len(cleaned) < 10:
            return False, ""
        
        # Format with + prefix
        if not phone_str.startswith('+'):
            formatted = f'+{cleaned}'
        else:
            formatted = f'+{cleaned}'
        
        return True, formatted
    
    @staticmethod
    def parse_csv_file(file_content: bytes, filename: str) -> Dict:
        """
        Parse CSV or Excel file
        Returns dictionary with parsed data and statistics
        """
        try:
            # Determine file type
            if filename.endswith('.csv'):
                df = pd.read_csv(BytesIO(file_content))
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(BytesIO(file_content))
            else:
                return {
                    'success': False,
                    'error': 'Unsupported file format. Please upload CSV or Excel file.',
                    'recipients': []
                }
            
            # Check if dataframe is empty
            if df.empty:
                return {
                    'success': False,
                    'error': 'File is empty',
                    'recipients': []
                }
            
            # Identify phone number column (case-insensitive)
            phone_column = None
            for col in df.columns:
                col_lower = col.lower()
                if any(term in col_lower for term in ['phone', 'number', 'mobile', 'cell', 'contact']):
                    phone_column = col
                    break
            
            if phone_column is None:
                # If no phone column found, assume first column
                phone_column = df.columns[0]
            
            # Identify name column
            name_column = None
            for col in df.columns:
                col_lower = col.lower()
                if any(term in col_lower for term in ['name', 'customer', 'contact_name', 'full_name']):
                    name_column = col
                    break
            
            # Identify email column
            email_column = None
            for col in df.columns:
                col_lower = col.lower()
                if 'email' in col_lower or 'mail' in col_lower:
                    email_column = col
                    break
            
            # Parse recipients
            recipients = []
            invalid_numbers = []
            duplicate_check = set()
            
            for idx, row in df.iterrows():
                phone = row[phone_column]
                is_valid, formatted_phone = CSVParser.validate_phone_number(phone)
                
                if not is_valid:
                    invalid_numbers.append({
                        'row': idx + 2,  # +2 for header and 0-indexing
                        'phone': str(phone),
                        'reason': 'Invalid phone number format'
                    })
                    continue
                
                # Check for duplicates
                if formatted_phone in duplicate_check:
                    invalid_numbers.append({
                        'row': idx + 2,
                        'phone': formatted_phone,
                        'reason': 'Duplicate phone number'
                    })
                    continue
                
                duplicate_check.add(formatted_phone)
                
                recipient = {
                    'phone_number': formatted_phone,
                    'name': str(row[name_column]).strip() if name_column and not pd.isna(row[name_column]) else None,
                    'email': str(row[email_column]).strip() if email_column and not pd.isna(row[email_column]) else None
                }
                
                recipients.append(recipient)
            
            return {
                'success': True,
                'recipients': recipients,
                'total_rows': len(df),
                'valid_numbers': len(recipients),
                'invalid_numbers': len(invalid_numbers),
                'invalid_details': invalid_numbers,
                'columns_detected': {
                    'phone': phone_column,
                    'name': name_column,
                    'email': email_column
                }
            }
        
        except Exception as e:
            logger.error(f"Error parsing CSV file: {str(e)}")
            return {
                'success': False,
                'error': f'Error parsing file: {str(e)}',
                'recipients': []
            }
    
    @staticmethod
    def validate_bulk_recipients(recipients: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        Validate a list of recipients
        Returns: (valid_recipients, error_messages)
        """
        valid = []
        errors = []
        seen_phones = set()
        
        for idx, recipient in enumerate(recipients):
            phone = recipient.get('phone_number', '')
            
            is_valid, formatted = CSVParser.validate_phone_number(phone)
            
            if not is_valid:
                errors.append(f"Row {idx + 1}: Invalid phone number '{phone}'")
                continue
            
            if formatted in seen_phones:
                errors.append(f"Row {idx + 1}: Duplicate phone number '{formatted}'")
                continue
            
            seen_phones.add(formatted)
            
            valid.append({
                'phone_number': formatted,
                'name': recipient.get('name'),
                'email': recipient.get('email')
            })
        
        return valid, errors