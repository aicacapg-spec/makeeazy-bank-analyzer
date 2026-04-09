"""
Parser Factory — Routes files to the appropriate parser based on file type.
"""

import os
from typing import Dict, Any, Optional

from app.services.parser.pdf_parser import parse_pdf
from app.services.parser.excel_parser import parse_excel
from app.services.parser.csv_parser import parse_csv


PARSER_MAP = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "csv",
    ".txt": "csv",  # Try CSV parser for text files
}


def parse_file(file_path: str, password: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a bank statement file. Auto-detects file type and routes to
    the appropriate parser.

    Args:
        file_path: Path to the file
        password: Optional password for encrypted PDFs

    Returns:
        Parsed data dict with account_info, transactions, discrepancies etc.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in PARSER_MAP:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {', '.join(PARSER_MAP.keys())}")

    parser_type = PARSER_MAP[ext]

    if parser_type == "pdf":
        return parse_pdf(file_path, password=password)
    elif parser_type == "excel":
        return parse_excel(file_path)
    elif parser_type == "csv":
        return parse_csv(file_path)
    else:
        raise ValueError(f"No parser available for file type: {ext}")
