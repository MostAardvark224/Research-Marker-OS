# File where all calls to AI model provider are handled 
from google import genai
from google.genai import types
import pathlib

sys_prompt = """
# IDENTITY
You are the Research Marker Assistant, a specialized AI designed to help researchers, students, and professionals synthesize information from their personal "Knowledge Index." You are analytical, precise, and objective.

# OPERATIONAL RULES
1. DATA INTEGRITY: Only make claims based on the indexed documents (if they exist). If the information is not in the index, state clearly: "I don't find specific mention of that in your current library, but based on general knowledge..."
2. CITATION STYLE: When referencing a paper, always mention its title. If quoting a highlight, use "quotes" and mention the source.
3. SYNTHESIS: When asked to "summarize" or "find connections," use bullet points and bold headers for scannability.
4. TONE: Maintain a professional, academic, yet helpful tone. Avoid fluff, long introductions, or "I hope this helps" style filler.

# FORMATTING
- Use Markdown for structure (headers, bolding, lists).
- Use LaTeX for any mathematical formulas or scientific notations (e.g., $E=mc^2$).
- If the user provides a code snippet or technical logic, provide optimizations if relevant.

# LIMITATIONS
- Do not hallucinate data that isn't present in the user's annotations or papers. However you can use general knowledge if no data is passed to you in the context.
"""

def send_prompt(gemini_key, model, prompt, pdf_count=0, pdf_paths=[]):
    client = genai.Client(api_key=gemini_key) 
    
    # hve to have diff calls based on how many pdfs are being sent
    if pdf_count > 1: 
        contents = []

        for path in pdf_paths:
            if path.exists():
                contents.append(
                    types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type='application/pdf',
                    )
                )

        contents.append(prompt)

        response = client.models.generate_content(
            model=model, 
            contents=contents, 
            config=types.GenerateContentConfig(
                system_instruction=sys_prompt, 
                temperature=0.7
            )
        )

        return response.text
    
    elif pdf_count == 1: 
        response = client.models.generate_content(
        model=model, 
        contents=[
            types.Part.from_bytes(
                data=pdf_paths[0].read_bytes(),
                mime_type='application/pdf',
            ),
            prompt  
        ], 
        config=types.GenerateContentConfig(
            system_instruction=sys_prompt, 
            temperature=0.7
        )
    )
        
        return response.text

    else: 
        response = client.models.generate_content(
        model=model, 
        contents=prompt, 
        config=types.GenerateContentConfig(
            system_instruction=sys_prompt, 
            temperature=0.7)
        )

        return response.text

def embed_obj(obj): 
    pass