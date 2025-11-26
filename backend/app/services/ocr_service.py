"""
OCR Service using Vision Language Model (VLM) for text extraction
Handles both check images and remittance PDFs with handwritten text support
"""
import os
import base64
from typing import Dict, Any, Optional, List
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
            # Ensure poppler is in PATH (for macOS Homebrew installations)
            import os
            poppler_paths = [
                '/opt/homebrew/bin',  # Homebrew on Apple Silicon
                '/usr/local/bin',      # Homebrew on Intel
                '/opt/homebrew/opt/poppler/bin',  # Direct poppler path
            ]
            current_path = os.environ.get('PATH', '')
            for poppler_path in poppler_paths:
                if poppler_path not in current_path and os.path.exists(poppler_path):
                    os.environ['PATH'] = f"{poppler_path}:{current_path}"
                    break
            
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
    
    def _normalize_check_number(self, check_num: Optional[str]) -> Optional[str]:
        """Normalize check number by removing leading zeros"""
        if not check_num:
            return None
        # Remove any non-digit characters
        check_num = re.sub(r'[^\d]', '', str(check_num))
        if check_num:
            # Remove leading zeros to normalize (e.g., "014607" -> "14607")
            check_num = check_num.lstrip('0') or '0'  # Keep at least one digit if all zeros
            return check_num
        return None
    
    def _parse_check_data(self, extracted_text: str) -> Dict[str, Any]:
        """Parse extracted text from check image - simple label-based extraction"""
        result = {
            "check_number": None,
            "amount": None,
            "date": None,
            "payor_name": None,
            "payee_name": None,
            "invoice_numbers": [],
            "raw_text": extracted_text
        }
        
        def extract_after_label(text: str, label: str) -> Optional[str]:
            """Simple extraction: find label, return everything after colon, trimmed"""
            # Handle numbered list format: "1. Label: value" or just "Label: value"
            patterns = [
                rf'\d+\.\s*{re.escape(label)}\s*:\s*(.+?)(?:\n|$)',
                rf'{re.escape(label)}\s*:\s*(.+?)(?:\n|$)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    # Remove any trailing asterisks or markdown
                    value = re.sub(r'\*+$', '', value).strip()
                    if value:
                        return value
            return None
        
        # Extract check number - simple label extraction
        check_num = extract_after_label(extracted_text, "Check Number")
        if check_num:
            result["check_number"] = self._normalize_check_number(check_num)
        
        # Extract amount - prioritize "Amount (Numerical):" label
        amount_str = extract_after_label(extracted_text, "Amount (Numerical)")
        if not amount_str:
            amount_str = extract_after_label(extracted_text, "Amount")
        
        if amount_str:
            # Clean up: remove $, commas, asterisks, whitespace
            amount_str = re.sub(r'[\$,\*\s]', '', amount_str)
            try:
                amount = float(amount_str)
                if 0.01 <= amount <= 10000000:  # Reasonable range
                    result["amount"] = amount
            except (ValueError, TypeError):
                pass
        
        # Extract date - simple label extraction
        date_str = extract_after_label(extracted_text, "Date")
        if date_str:
            # Normalize month names to numbers if present
            month_map = {
                'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
            }
            date_upper = date_str.upper()
            for month_name, month_num in month_map.items():
                if month_name in date_upper:
                    # Convert "11 NOV 2025" or "06 AUG 2025" to "11/11/2025" or "08/06/2025"
                    # Format: MM/DD/YYYY (month first)
                    parts = date_str.upper().split()
                    if len(parts) == 3:
                        day, month, year = parts
                        result["date"] = f"{month_num}/{day}/{year}"
                    else:
                        result["date"] = date_str
                    break
            else:
                # Already in numeric format, use as-is (assumes MM/DD/YYYY or DD/MM/YYYY)
                # If format is DD/MM/YYYY, convert to MM/DD/YYYY
                numeric_date = date_str.strip()
                if '/' in numeric_date:
                    parts = numeric_date.split('/')
                    if len(parts) == 3:
                        # Check if first part > 12 (likely DD/MM format)
                        if parts[0].isdigit() and int(parts[0]) > 12:
                            # Swap day and month: DD/MM/YYYY -> MM/DD/YYYY
                            result["date"] = f"{parts[1]}/{parts[0]}/{parts[2]}"
                        else:
                            # Already MM/DD/YYYY
                            result["date"] = numeric_date
                    else:
                        result["date"] = numeric_date
                else:
                    result["date"] = numeric_date
        
        # Extract payor name - simple label extraction
        payor_name = extract_after_label(extracted_text, "Payor Name")
        if payor_name:
            # Clean up: normalize whitespace, remove trailing dashes
            payor_name = ' '.join(payor_name.split())
            payor_name = re.sub(r'\s*-\s*$', '', payor_name).strip()
            if len(payor_name) > 3:
                result["payor_name"] = payor_name
        
        # Extract payee name - simple label extraction
        payee_name = extract_after_label(extracted_text, "Payee Name")
        if payee_name:
            payee_name = ' '.join(payee_name.split()).strip()
            if len(payee_name) > 3:
                result["payee_name"] = payee_name
        
        # Extract invoice numbers (look for patterns like "INV-", "Invoice #", etc.)
        # Try to capture full invoice numbers including INV prefix
        invoice_patterns = [
            r'(?:invoice\s+numbers?\s*:?\s*|inv[oice]*\s*#?\s*:?\s*)([A-Z]{0,3}[\d\-]+[A-Z0-9\-]*)',  # "Invoice Numbers: INV240315267" or "inv: INV240315267"
            r'(?:for\s+inv\s*#?\s*|invoice\s*#?\s*)([A-Z]{0,3}[\d\-]+[A-Z0-9\-]*)',  # "For inv # INV240315267"
            r'\b(INV[A-Z0-9\-]+)\b',  # Standalone INV followed by alphanumeric
            r'\b([A-Z]{2,}-[A-Z0-9\-]+)\b',  # Pattern like INV-UOC-16210973
            r'(?:^|\s|,|\()([A-Z]{0,3}[\d]{6,}[A-Z0-9\-]*)\b',  # Numeric patterns that might be invoice numbers
        ]
        for pattern in invoice_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE | re.MULTILINE)
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
        # Try to capture full invoice numbers including INV prefix
        invoice_patterns = [
            r'(?:invoice\s+numbers?\s*:?\s*|inv[oice]*\s*#?\s*:?\s*)([A-Z]{0,3}[\d\-]+[A-Z0-9\-]*)',  # "Invoice Numbers: INV240315267" or "inv: INV240315267"
            r'(?:for\s+inv\s*#?\s*|invoice\s*#?\s*)([A-Z]{0,3}[\d\-]+[A-Z0-9\-]*)',  # "For inv # INV240315267"
            r'\b(INV[A-Z0-9\-]+)\b',  # Standalone INV followed by alphanumeric
            r'\b([A-Z]{2,}-[A-Z0-9\-]+)\b',  # Pattern like INV-UOC-16210973
            r'(?:^|\s|,|\()([A-Z]{0,3}[\d]{6,}[A-Z0-9\-]*)\b',  # Numeric patterns that might be invoice numbers
        ]
        for pattern in invoice_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE | re.MULTILINE)
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
            result["check_number"] = self._normalize_check_number(check_match.group(1))
        
        # Extract date
        date_match = re.search(r'date\s+presented\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', extracted_text, re.IGNORECASE)
        if date_match:
            result["date"] = date_match.group(1)
        
        return result
    
    def process_check_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """Process check image and extract relevant data"""
        image = Image.open(BytesIO(image_bytes))
        
        prompt = """Extract all text from this check image and format it as follows. Use plain text only - NO markdown formatting, NO asterisks, NO bold markers.

Format your response exactly like this:
1. Check Number: [number]
2. Amount (Written): [amount in words]
3. Amount (Numerical): [amount as number]
4. Date: [date]
5. Payor Name: [name]
6. Payee Name: [name]
7. Invoice/Reference: [any invoice numbers or references]

Then include any additional visible text, including handwritten notes or references.

IMPORTANT: Use plain text labels with colons. Do NOT use markdown formatting like ** or bold text."""
        
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
        
        prompt = """Extract all text from this remittance document and format it as follows. Use plain text only - NO markdown formatting, NO asterisks, NO bold markers.

Format your response exactly like this:
1. Invoice Numbers: [list all invoice numbers found]
2. Amount Paid: [amount]
3. Customer/Payor Name: [name]
4. Check Number: [number]
5. Date Presented: [date]
6. Additional Notes: [any handwritten notes or references]

Then include any additional visible text, including handwritten text.

IMPORTANT: Use plain text labels with colons. Do NOT use markdown formatting like ** or bold text."""
        
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
    
    def process_pdf_by_checks(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Process a lockbox PDF and group pages by check number.
        Handles cases where check info is on one page and remittance info is on another.
        Filters out pages with no useful information.
        Returns a list of check groups, where each group contains pages for a single check.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Converting PDF to images...")
        images = self._pdf_to_images(pdf_bytes)
        logger.info(f"PDF converted to {len(images)} page(s)")
        
        # Process each page to extract check information
        page_results = []
        for page_idx, image in enumerate(images):
            logger.info(f"Processing page {page_idx + 1}/{len(images)}...")
            # Enhanced prompt for lockbox PDFs - better extraction of invoice numbers and amounts
            prompt = """Extract all text from this document page. This could be a check image or remittance document.
            Format your response exactly like this. Use plain text only - NO markdown formatting, NO asterisks, NO bold markers.

Format your response exactly like this:
1. Check Number: [number if found]
2. Amount (Numerical): [amount as number]
3. Amount (Written): [amount in words if found]
4. Date: [date]
5. Payor Name: [name]
6. Payee Name: [name]
7. Customer/Payor Name: [name]
8. Invoice Numbers: [list all invoice numbers found - be thorough, look for INV, INVOICE, invoice numbers in various formats]
9. Additional Notes: [any handwritten notes or references]

Then include any additional visible text, including handwritten text.

IMPORTANT: 
- Use plain text labels with colons. Do NOT use markdown formatting like ** or bold text.
- For invoice numbers, extract ALL invoice numbers you see, including partial numbers
- Look for invoice numbers in formats like: INV123456, INV-123456, Invoice #123456, etc."""
            
            try:
                extracted_text = self._extract_with_vlm(image, prompt)
                logger.info(f"Page {page_idx + 1} OCR completed")
            except Exception as e:
                logger.error(f"Error processing page {page_idx + 1}: {e}", exc_info=True)
                # Continue with empty text rather than failing completely
                extracted_text = f"Error extracting text from page {page_idx + 1}: {str(e)}"
            
            # Try parsing as check first, then as remittance
            check_data = self._parse_check_data(extracted_text)
            remittance_data = self._parse_remittance_data(extracted_text)
            
            # Merge data (prefer check data for check-specific fields, remittance for invoice numbers)
            # Normalize check numbers (remove leading zeros)
            check_num = self._normalize_check_number(
                check_data.get("check_number") or remittance_data.get("check_number")
            )
            page_data = {
                "check_number": check_num,
                "amount": check_data.get("amount") or remittance_data.get("amount"),
                "date": check_data.get("date") or remittance_data.get("date"),
                "payor_name": check_data.get("payor_name") or remittance_data.get("customer_name"),
                "payee_name": check_data.get("payee_name"),
                "customer_name": remittance_data.get("customer_name") or check_data.get("payor_name"),
                "invoice_numbers": list(set((check_data.get("invoice_numbers", []) + remittance_data.get("invoice_numbers", [])))),
                "raw_text": extracted_text,
                "page_index": page_idx,
                "has_useful_data": bool(
                    check_data.get("check_number") or 
                    remittance_data.get("check_number") or
                    check_data.get("amount") or 
                    remittance_data.get("amount") or
                    check_data.get("invoice_numbers") or 
                    remittance_data.get("invoice_numbers") or
                    check_data.get("payor_name") or 
                    remittance_data.get("customer_name")
                )
            }
            
            page_results.append(page_data)
        
        logger.info(f"All {len(page_results)} pages processed. Filtering and grouping by check number...")
        
        # Filter out pages with no useful information
        useful_pages = [p for p in page_results if p.get("has_useful_data", True)]
        logger.info(f"Filtered to {len(useful_pages)} useful pages (removed {len(page_results) - len(useful_pages)} useless pages)")
        
        # Group pages by check number, including nearby pages without check numbers
        check_groups = []
        current_group = None
        nearby_window = 2  # Include pages within 2 pages of a check page
        
        for idx, page_data in enumerate(useful_pages):
            check_number = page_data.get("check_number")
            page_index = page_data["page_index"]
            
            if check_number:
                # Normalize check number for comparison
                normalized_check_num = self._normalize_check_number(check_number)
                # If we have a check number, start a new group or add to existing group with same check number
                if current_group and self._normalize_check_number(current_group["check_number"]) == normalized_check_num:
                    # Add to existing group
                    current_group["pages"].append(page_index)
                    self._merge_page_data(current_group, page_data)
                else:
                    # Start new group
                    if current_group:
                        check_groups.append(current_group)
                    # Normalize check number
                    normalized_check_num = self._normalize_check_number(check_number)
                    current_group = {
                        "check_number": normalized_check_num,
                        "pages": [page_index],
                        "amount": page_data.get("amount"),
                        "date": page_data.get("date"),
                        "payor_name": page_data.get("payor_name"),
                        "payee_name": page_data.get("payee_name"),
                        "customer_name": page_data.get("customer_name"),
                        "invoice_numbers": page_data.get("invoice_numbers", []).copy(),
                        "raw_text": f"--- Page {page_index + 1} ---\n{page_data['raw_text']}",
                        "check_page_indices": [idx]  # Track which pages have check numbers
                    }
            else:
                # No check number found - add to current group if it exists and is nearby
                if current_group:
                    # Check if this page is within the nearby window of a check page
                    last_check_idx = current_group["check_page_indices"][-1] if current_group.get("check_page_indices") else -1
                    if idx - last_check_idx <= nearby_window:
                        # Add to current group
                        current_group["pages"].append(page_index)
                        self._merge_page_data(current_group, page_data)
                    else:
                        # Too far from check page, start new unknown group
                        if current_group:
                            check_groups.append(current_group)
                        current_group = {
                            "check_number": None,
                            "pages": [page_index],
                            "amount": page_data.get("amount"),
                            "date": page_data.get("date"),
                            "payor_name": page_data.get("payor_name"),
                            "payee_name": page_data.get("payee_name"),
                            "customer_name": page_data.get("customer_name"),
                            "invoice_numbers": page_data.get("invoice_numbers", []).copy(),
                            "raw_text": f"--- Page {page_index + 1} ---\n{page_data['raw_text']}",
                            "check_page_indices": []
                        }
                else:
                    # Create a new group with unknown check number
                    current_group = {
                        "check_number": None,
                        "pages": [page_index],
                        "amount": page_data.get("amount"),
                        "date": page_data.get("date"),
                        "payor_name": page_data.get("payor_name"),
                        "payee_name": page_data.get("payee_name"),
                        "customer_name": page_data.get("customer_name"),
                        "invoice_numbers": page_data.get("invoice_numbers", []).copy(),
                        "raw_text": f"--- Page {page_index + 1} ---\n{page_data['raw_text']}",
                        "check_page_indices": []
                    }
        
        # Add the last group
        if current_group:
            check_groups.append(current_group)
        
        # Clean up check_page_indices from final groups
        for group in check_groups:
            if "check_page_indices" in group:
                del group["check_page_indices"]
        
        logger.info(f"Grouped into {len(check_groups)} check group(s)")
        
        return check_groups
    
    def _merge_page_data(self, group: Dict[str, Any], page_data: Dict[str, Any]) -> None:
        """Merge page data into a check group"""
        page_index = page_data["page_index"]
        
        # Merge invoice numbers
        group["invoice_numbers"] = list(set(
            group.get("invoice_numbers", []) + page_data.get("invoice_numbers", [])
        ))
        
        # Normalize and merge check number (remove leading zeros)
        page_check_num = self._normalize_check_number(page_data.get("check_number"))
        if page_check_num:
            group_check_num = self._normalize_check_number(group.get("check_number"))
            if not group_check_num or group_check_num == page_check_num:
                group["check_number"] = page_check_num
        
        # Prefer non-null values
        if not group.get("amount") and page_data.get("amount"):
            group["amount"] = page_data["amount"]
        if not group.get("date") and page_data.get("date"):
            group["date"] = page_data["date"]
        if not group.get("payor_name") and page_data.get("payor_name"):
            group["payor_name"] = page_data["payor_name"]
        if not group.get("customer_name") and page_data.get("customer_name"):
            group["customer_name"] = page_data["customer_name"]
        if not group.get("payee_name") and page_data.get("payee_name"):
            group["payee_name"] = page_data["payee_name"]
        
        # Append raw text
        group["raw_text"] += f"\n\n--- Page {page_index + 1} ---\n{page_data['raw_text']}"

