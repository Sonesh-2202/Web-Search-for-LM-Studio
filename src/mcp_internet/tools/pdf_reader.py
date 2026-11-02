"""
PDF Reader Tool - Extract text from PDF URLs.

Uses pdfplumber or basic PDF parsing for text extraction.
"""

import io
import logging
import re

from ..utils.http_client import ResponseLimitError, UnsafeURLError, fetch_bytes

logger = logging.getLogger(__name__)


async def read_pdf(url: str, max_pages: int = 5, max_length: int = 5000) -> str:
    """
    Extract text content from a PDF URL.
    
    Args:
        url: URL of the PDF file
        max_pages: Maximum number of pages to extract (default: 5)
        max_length: Maximum characters to return (default: 5000)
        
    Returns:
        Extracted text from the PDF
    """
    if not url.strip():
        return "❌ Error: Please provide a PDF URL."
    
    if len(url) > 4096:
        return "❌ Error: URL exceeds the 4096 character limit."
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not isinstance(max_length, int) or isinstance(max_length, bool):
        return "❌ Error: max_pages and max_length must be integers."
    max_pages = max(1, min(max_pages, 20))
    max_length = max(1, min(max_length, 20000))
    # Add protocol if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    # Validate URL looks like a PDF
    if not url.lower().endswith('.pdf') and 'pdf' not in url.lower():
        logger.warning("Requested resource URL does not have a recognizable PDF suffix")
    
    try:
        pdf_bytes = await fetch_bytes(url, timeout=30, retries=1)
        
        if not pdf_bytes:
            return "❌ Error: Unable to download PDF."
        
        # Check if it's actually a PDF
        if not pdf_bytes[:5] == b'%PDF-':
            return "❌ Error: The URL does not point to a valid PDF file."
        
        try:
            # Try pdfplumber first
            import pdfplumber
            
            text_content = []
            
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                total_pages = len(pdf.pages)
                if total_pages > 500:
                    return "❌ Error: PDF exceeds the 500 page processing limit."
                pages_to_read = min(max_pages, total_pages)
                
                for i in range(pages_to_read):
                    page = pdf.pages[i]
                    text = page.extract_text()
                    if text:
                        text_content.append(f"--- Page {i+1} ---\n{text}")
            
            if not text_content:
                return "❌ Error: No text could be extracted from this PDF. It may contain only images."
            
            full_text = "\n\n".join(text_content)
            
            # Truncate if needed
            if len(full_text) > max_length:
                full_text = full_text[:max_length] + "\n\n[Content truncated...]"
            
            output = f"""📄 **PDF Content**
🔗 {url}
📖 Pages: {pages_to_read}/{total_pages}
{'=' * 50}

{full_text}
"""
            return output[:max_length]
            
        except ImportError:
            # Fallback: Basic PDF text extraction without pdfplumber
            # Try to extract text using basic patterns
            text = pdf_bytes.decode('latin-1', errors='ignore')
            
            # Extract text between BT and ET markers (simplified)
            text_parts = re.findall(r'\((.*?)\)', text)
            extracted = ' '.join(text_parts)[:max_length]
            
            if len(extracted) < 100:
                return """❌ Error: Unable to extract text from this PDF.

💡 To enable full PDF support, install pdfplumber:
   pip install pdfplumber
"""
            
            output = f"""📄 **PDF Content** (Basic extraction)
🔗 {url}
{'=' * 50}

{extracted}

💡 Note: For better PDF extraction, install pdfplumber:
   pip install pdfplumber
"""
            return output[:max_length]
        
    except (UnsafeURLError, ResponseLimitError) as e:
        return f"❌ Error: {e}"
    except Exception as e:
        logger.error("Error reading PDF (%s)", type(e).__name__)
        return f"❌ Error: Unable to read PDF ({type(e).__name__})."
