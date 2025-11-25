"""
OCR Service using Vision Language Model (VLM) for text extraction
Handles both check images and remittance PDFs with handwritten text support
"""
import os
import base64
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_bytes
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from collections import Counter
import re

# Load environment variables from .env file
# Try backend/.env first, then project root .env
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent  # backend/
_project_root = _backend_dir.parent  # project root

env_paths = [
    _backend_dir / ".env",  # backend/.env
    _project_root / ".env",  # project root .env
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break
else:
    # Fallback to default behavior (current directory)
    load_dotenv(override=True)


class OCRService:
    """Service for extracting text from images and PDFs using GPT-4 Vision"""
    
    def __init__(self):
        # Ensure .env is loaded (in case it wasn't loaded at module level)
        _current_file = Path(__file__).resolve()
        _backend_dir = _current_file.parent.parent.parent
        _project_root = _backend_dir.parent
        env_paths = [
            _backend_dir / ".env",
            _project_root / ".env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                break
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                f"OPENAI_API_KEY environment variable not set. "
                f"Checked .env files at: {[str(p) for p in env_paths]}. "
                f"Please ensure OPENAI_API_KEY is set in your .env file."
            )
        self.client = OpenAI(api_key=api_key)
    
    def _encode_image(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _pdf_to_images(self, pdf_bytes: bytes) -> list[Image.Image]:
        """Convert PDF bytes to list of PIL Images"""
        try:
            images = convert_from_bytes(pdf_bytes, dpi=300)
            return images
        except Exception as e:
            raise Exception(f"Failed to convert PDF to images: {str(e)}")
    
    def _extract_with_vlm(self, image: Image.Image, prompt: str) -> str:
        """Extract text from image using GPT-4 Vision"""
        base64_image = self._encode_image(image)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"VLM extraction failed: {str(e)}")
    
    def _parse_check_data(self, extracted_text: str) -> Dict[str, Any]:
        """Parse extracted text from check image"""
        result = {
            "check_number": None,
            "amount": None,
            "date": None,
            "payor_name": None,
            "payee_name": None,
            "invoice_numbers": [],
            "raw_text": extracted_text
        }
        
        # Extract check number first (so we can exclude it from amount extraction)
        check_number = None
        check_patterns = [
            r'check\s+number\s*:?\s*(\d+)',
            r'check\s*#?\s*:?\s*(\d+)',
            r'ck\s*#?\s*:?\s*(\d+)',
        ]
        for pattern in check_patterns:
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                check_number = match.group(1)
                result["check_number"] = check_number
                break
        
        # Extract amount (prioritize explicitly labeled amounts)
        # Focus on patterns that work reliably - ignore asterisks in OCR output
        explicit_amount_patterns = [
            # Most reliable: explicit labels with amounts
            (r'amount\s+is\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'amount is'),
            (r'numerical\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'numerical'),
            (r'handwritten\s*:?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'handwritten'),
            (r'amount\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'amount'),
            (r'pay\s+amount\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'pay amount'),
            (r'numerical\s+(\d+(?:,\d{3})*(?:\.\d{2})?)', 'numerical no colon'),
            (r'handwritten\s+(\d+(?:,\d{3})*(?:\.\d{2})?)', 'handwritten no colon'),
        ]
        
        explicit_amounts = []
        for pattern, _ in explicit_amount_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            for m in matches:
                try:
                    amount = float(m.replace(',', '').strip())
                    # Exclude check numbers and very large numbers
                    # Prioritize amounts with decimal points (more likely to be actual amounts)
                    if (0.01 <= amount <= 1000000 and  # Reasonable range for check amounts
                        (check_number is None or str(int(amount)) != check_number) and  # Not the check number
                        ('.' in m or amount < 10000)):  # Has decimal point or is reasonable size
                        explicit_amounts.append(amount)
                except:
                    pass
        
        # If we found explicit amounts, prioritize those with decimal points
        if explicit_amounts:
            # Separate amounts with decimals from those without
            amounts_with_decimals = [a for a in explicit_amounts if a % 1 != 0]
            amounts_without_decimals = [a for a in explicit_amounts if a % 1 == 0]
            
            if amounts_with_decimals:
                # Use most common amount with decimal
                amount_counts = Counter(amounts_with_decimals)
                result["amount"] = amount_counts.most_common(1)[0][0]
            elif amounts_without_decimals:
                # Fallback to amounts without decimals, but exclude check numbers
                filtered = [a for a in amounts_without_decimals 
                           if check_number is None or str(int(a)) != check_number]
                if filtered:
                    amount_counts = Counter(filtered)
                    result["amount"] = amount_counts.most_common(1)[0][0]
                else:
                    amount_counts = Counter(amounts_without_decimals)
                    result["amount"] = amount_counts.most_common(1)[0][0]
        else:
            # Fallback: look for dollar amounts with $ sign
            dollar_amount_patterns = [
                r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            ]
            dollar_amounts = []
            for pattern in dollar_amount_patterns:
                matches = re.findall(pattern, extracted_text, re.IGNORECASE)
                for m in matches:
                    try:
                        amount = float(m.replace(',', ''))
                        if 0.01 <= amount <= 10000000:
                            dollar_amounts.append(amount)
                    except:
                        pass
            
            if dollar_amounts:
                amount_counts = Counter(dollar_amounts)
                result["amount"] = amount_counts.most_common(1)[0][0]
        
        # Extract date
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                result["date"] = match.group(1)
                break
        
        # Extract payor name (usually at the top of the check, before "Pay To The Order Of")
        # First, try to find "Payor Name:" label (most reliable)
        payor_label_match = re.search(
            r'payor\s+name\s*:?\s*([A-Z][A-Z\s&,\.\-]+(?:INC|LLC|CORP|LTD|INC\.|LLC\.|CORP\.|LTD\.|VENDOR)?(?:\s*-\s*\([^)]+\))?)',
            extracted_text,
            re.IGNORECASE
        )
        if payor_label_match:
            payor_name = payor_label_match.group(1).strip()
            # Clean up - take first line if multi-line
            payor_name = payor_name.split('\n')[0].strip()
            if len(payor_name) > 3:
                result["payor_name"] = payor_name
        
        # If not found, look for company name patterns but exclude amount-related text
        if not result["payor_name"]:
            # Exclude common words that might match from amount text
            exclude_words = ['EXACTLY', 'PAY', 'ORDER', 'DOLLARS', 'ONLY', 'AND', 'THE', 'TO', 'DOLLAR']
            
            # Split text by "Pay To The Order Of" to get the header section
            parts = re.split(r'pay\s+to\s+the\s+order\s+of', extracted_text, flags=re.IGNORECASE, maxsplit=1)
            if len(parts) > 0:
                header_text = parts[0]
                # Look for company name in header (must be substantial and have business suffix)
                company_patterns = [
                    r'^([A-Z][A-Z\s&,\.\-]{5,}(?:INC|LLC|CORP|LTD|INC\.|LLC\.|CORP\.|LTD\.|VENDOR))',
                    r'([A-Z][A-Z\s&,\.\-]{8,}(?:INC|LLC|CORP|LTD|INC\.|LLC\.|CORP\.|LTD\.|VENDOR))',
                ]
                for pattern in company_patterns:
                    matches = re.finditer(pattern, header_text, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        payor_name = match.group(1).strip()
                        payor_upper = payor_name.upper()
                        # Skip if it's in excluded words or contains amount-related terms
                        if (payor_upper not in exclude_words and 
                            len(payor_name) > 5 and
                            not any(word in payor_upper for word in exclude_words)):
                            # Take first line if multi-line
                            payor_name = payor_name.split('\n')[0].strip()
                            result["payor_name"] = payor_name
                            break
                    if result["payor_name"]:
                        break
        
        # Extract payee name (after "Pay To The Order Of")
        payee_match = re.search(r'pay\s+to\s+the\s+order\s+of\s*:?\s*([A-Z][A-Z\s&,\.]+(?:INC|LLC|CORP|LTD|INC\.|LLC\.|CORP\.|LTD\.)?)', extracted_text, re.IGNORECASE)
        if payee_match:
            result["payee_name"] = payee_match.group(1).strip()
        
        # Extract invoice numbers (look for patterns like "INV-", "Invoice #", etc.)
        invoice_patterns = [
            r'inv[oice]*\s*#?\s*:?\s*([A-Z0-9\-]+)',
            r'invoice\s+number\s*:?\s*([A-Z0-9\-]+)',
            r'([A-Z]{2,}-[A-Z0-9\-]+)',  # Pattern like INV-UOC-16210973
        ]
        for pattern in invoice_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            result["invoice_numbers"].extend(matches)
        
        # Remove duplicates and filter out invalid invoice numbers
        # Filter out single letters, common words, or very short strings that aren't invoice numbers
        invalid_patterns = ['s', 'numbers', 'number', 'inv', 'invoice', 'for', 'the', 'and', 'or']
        filtered_invoices = []
        for inv in set(result["invoice_numbers"]):
            inv_upper = inv.upper().strip()
            # Must be at least 3 characters, not start with dash, and not in invalid list
            if (len(inv_upper) >= 3 and 
                not inv_upper.startswith('-') and 
                inv_upper not in [p.upper() for p in invalid_patterns]):
                # Should contain at least one number or dash (typical invoice format)
                if any(c.isdigit() or c == '-' for c in inv_upper):
                    filtered_invoices.append(inv)
        
        result["invoice_numbers"] = filtered_invoices
        
        return result
    
    def _parse_remittance_data(self, extracted_text: str) -> Dict[str, Any]:
        """Parse extracted text from remittance PDF"""
        result = {
            "invoice_numbers": [],
            "amount": None,
            "customer_name": None,
            "check_number": None,
            "date": None,
            "raw_text": extracted_text
        }
        
        # Extract invoice numbers (more flexible for remittances)
        invoice_patterns = [
            r'inv[oice]*\s*#?\s*:?\s*([A-Z0-9\-]+)',
            r'invoice\s+number\s*:?\s*([A-Z0-9\-]+)',
            r'([A-Z]{2,}-[A-Z0-9\-]+)',  # Pattern like INV-UOC-16210973
            r'for\s+inv\s*#\s*([A-Z0-9\-]+)',  # "For inv # INV-UOC-16210973"
        ]
        for pattern in invoice_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            result["invoice_numbers"].extend(matches)
        
        # Remove duplicates and filter out invalid invoice numbers
        invalid_patterns = ['s', 'numbers', 'number', 'inv', 'invoice', 'for', 'the', 'and', 'or']
        filtered_invoices = []
        for inv in set(result["invoice_numbers"]):
            inv_upper = inv.upper().strip()
            # Must be at least 3 characters, not start with dash, and not in invalid list
            if (len(inv_upper) >= 3 and 
                not inv_upper.startswith('-') and 
                inv_upper not in [p.upper() for p in invalid_patterns]):
                # Should contain at least one number or dash (typical invoice format)
                if any(c.isdigit() or c == '-' for c in inv_upper):
                    filtered_invoices.append(inv)
        
        result["invoice_numbers"] = filtered_invoices
        
        # Extract amount (prioritize explicitly labeled amounts)
        explicit_amount_patterns = [
            (r'amount\s+paid\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'amount paid'),
            (r'numerical\s+(\d+(?:,\d{3})*(?:\.\d{2})?)', 'numerical'),
            (r'handwritten\s+(\d+(?:,\d{3})*(?:\.\d{2})?)', 'handwritten'),
            (r'amount\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'amount'),
            (r'payment\s+amount\s*:?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'payment amount'),
        ]
        
        explicit_amounts = []
        for pattern, _ in explicit_amount_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            for m in matches:
                try:
                    amount = float(m.replace(',', ''))
                    if 0.01 <= amount <= 10000000:  # Reasonable range
                        explicit_amounts.append(amount)
                except:
                    pass
        
        # If we found explicit amounts, use the most common one
        if explicit_amounts:
            amount_counts = Counter(explicit_amounts)
            result["amount"] = amount_counts.most_common(1)[0][0]
        else:
            # Fallback: look for dollar amounts with $ sign
            dollar_amount_patterns = [
                r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            ]
            dollar_amounts = []
            for pattern in dollar_amount_patterns:
                matches = re.findall(pattern, extracted_text, re.IGNORECASE)
                for m in matches:
                    try:
                        amount = float(m.replace(',', ''))
                        if 0.01 <= amount <= 10000000:
                            dollar_amounts.append(amount)
                    except:
                        pass
            
            if dollar_amounts:
                amount_counts = Counter(dollar_amounts)
                result["amount"] = amount_counts.most_common(1)[0][0]
        
        # Extract customer/payor name
        # First try "Payor Name:" label (most reliable)
        customer_match = re.search(
            r'payor\s+name\s*:?\s*([A-Z][A-Z\s&,\.\-]+(?:INC|LLC|CORP|LTD|INC\.|LLC\.|CORP\.|LTD\.|VENDOR)?(?:\s*-\s*\([^)]+\))?)',
            extracted_text,
            re.IGNORECASE
        )
        if customer_match:
            customer_name = customer_match.group(1).strip()
            # Clean up - take first line if multi-line
            customer_name = customer_name.split('\n')[0].strip()
            if len(customer_name) > 3:
                result["customer_name"] = customer_name
        
        # Extract check number
        check_match = re.search(r'check\s*#?\s*:?\s*(\d+)', extracted_text, re.IGNORECASE)
        if check_match:
            result["check_number"] = check_match.group(1)
        
        # Extract date
        date_match = re.search(r'date\s+presented\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', extracted_text, re.IGNORECASE)
        if date_match:
            result["date"] = date_match.group(1)
        
        return result
    
    def process_check_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """Process check image and extract relevant data"""
        image = Image.open(BytesIO(image_bytes))
        
        prompt = """Extract all text from this check image. Pay special attention to:
1. Check number
2. Amount (both written and numerical)
3. Date
4. Payor name (the person/company writing the check)
5. Payee name (the person/company receiving the check)
6. Any invoice numbers or references written on the check (in memo line or elsewhere)

Return all visible text, including any handwritten notes or references."""
        
        extracted_text = self._extract_with_vlm(image, prompt)
        parsed_data = self._parse_check_data(extracted_text)
        
        return parsed_data
    
    def process_remittance_pdf(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Process remittance PDF and extract relevant data"""
        images = self._pdf_to_images(pdf_bytes)
        
        # Process all pages and combine results
        all_text = []
        combined_result = {
            "invoice_numbers": [],
            "amount": None,
            "customer_name": None,
            "check_number": None,
            "date": None,
            "raw_text": ""
        }
        
        prompt = """Extract all text from this remittance document. Pay special attention to:
1. Invoice numbers (may be handwritten or printed)
2. Amount paid
3. Customer/payor name
4. Check number
5. Date presented
6. Any handwritten notes or references

Return all visible text, including handwritten text."""
        
        for image in images:
            extracted_text = self._extract_with_vlm(image, prompt)
            all_text.append(extracted_text)
            parsed_data = self._parse_remittance_data(extracted_text)
            
            # Merge results
            combined_result["invoice_numbers"].extend(parsed_data.get("invoice_numbers", []))
            if parsed_data.get("amount") and not combined_result["amount"]:
                combined_result["amount"] = parsed_data["amount"]
            if parsed_data.get("customer_name") and not combined_result["customer_name"]:
                combined_result["customer_name"] = parsed_data["customer_name"]
            if parsed_data.get("check_number") and not combined_result["check_number"]:
                combined_result["check_number"] = parsed_data["check_number"]
            if parsed_data.get("date") and not combined_result["date"]:
                combined_result["date"] = parsed_data["date"]
        
        combined_result["raw_text"] = "\n\n".join(all_text)
        combined_result["invoice_numbers"] = list(set(combined_result["invoice_numbers"]))
        
        return combined_result

