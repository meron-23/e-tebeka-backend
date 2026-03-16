import google.generativeai as genai
import json
from app.core.config import settings

# Global index for key rotation
_current_key_idx = 0

def get_model(key_index: int = 0):
    keys = settings.GEMINI_API_KEYS
    idx = key_index % len(keys)
    genai.configure(api_key=keys[idx])
    return genai.GenerativeModel(settings.GEMINI_MODEL)

PROMPT_TEMPLATE = """
You are a legal document parser for Ethiopian laws. Extract the following information from this proclamation/regulation text and return ONLY valid JSON:

{
  "document_type": "proclamation" or "regulation",
  "document_number": "extracted number (e.g., 1396/2025)",
  "document_number_am": "Amharic number if present",
  "issuing_body_am": "Issuing body in Amharic",
  "issuing_body_en": "Issuing body in English",
  "title_am": "Full Amharic title",
  "title_en": "Full English title",
  "short_title_am": "Short title in Amharic",
  "short_title_en": "Short title in English",
  "year_ec": "Ethiopian calendar year as integer",
  "year_gregorian": "Gregorian year as integer",
  "date_issued_ec": "Issue date in Ethiopian calendar",
  "date_issued_gregorian": "Issue date as YYYY-MM-DD",
  "date_published_ec": "Publication date in Ethiopian calendar",
  "date_published_gregorian": "Publication date as YYYY-MM-DD",
  "gazette_year": "Gazette year as integer",
  "gazette_number": "Gazette number as integer",
  "page_start": "Starting page as integer",
  "page_end": "Ending page as integer",
  "signed_by_am": "Signatory name in Amharic",
  "signed_by_en": "Signatory name in English",
  "signed_title_am": "Signatory title in Amharic",
  "signed_title_en": "Signatory title in English",
  "legal_basis_am": "For regulations: legal basis in Amharic",
  "legal_basis_en": "For regulations: legal basis in English",
  "parent_proclamation_number": "If regulation, source proclamation number",
  "amends_document_number": "If amendment, source document number",
  "articles": [
    {
      "section_number": "article number",
      "section_number_am": "Amharic article number",
      "section_type": "article",
      "title_am": "Article title in Amharic",
      "title_en": "Article title in English",
      "content_am": "Full Amharic content",
      "content_en": "Full English content",
      "sequence_order": "order number"
    }
  ],
  "categories": ["Labour Law", "Civil Law", "Criminal Law", "etc."]
}

Note: Choose categories that best describe the legal area of the document.

Text to parse:
"""

def extract_document_data(text_content: str):
    global _current_key_idx
    
    if not text_content or len(text_content.strip()) < 10:
        return {"error": "Insufficient text content for extraction. PDF may be scanned or empty."}

    prompt = f"{PROMPT_TEMPLATE}\n\n{text_content}"
    
    # Try multiple keys if one fails
    max_retries = len(settings.GEMINI_API_KEYS)
    last_error = None
    
    for _ in range(max_retries):
        try:
            model = get_model(_current_key_idx)
            response = model.generate_content(prompt)
            
            # Try to find JSON in the response
            text_response = response.text
            try:
                # 1. Try stripping backticks if presence
                cleaned_text = text_response
                if "```json" in cleaned_text:
                    cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned_text:
                    cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()
                
                try:
                    return json.loads(cleaned_text)
                except json.JSONDecodeError:
                    # 2. Try simple regex find if direct load fails
                    import re
                    json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
                    raise
            except Exception as e:
                return {
                    "error": "Failed to parse JSON", 
                    "raw_response": text_response[:1000],  # Limit size
                    "parse_error": str(e)
                }
                
        except Exception as e:
            last_error = e
            # Rotate and retry
            _current_key_idx = (_current_key_idx + 1) % len(settings.GEMINI_API_KEYS)
            continue
            
    return {"error": f"All Gemini API keys failed. Last error: {last_error}"}
