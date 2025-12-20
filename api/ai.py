# File where all calls to AI model provider are handled 
from google import genai
from google.genai import types
import pathlib
import api.models as models
import api.serializers as serializers
from django.utils import timezone

# for saving chat logs
# this only saves the user prompt and doesn't include added context so that it looks normal in the chat history
def add_message_to_chat(chat_id, role, text): 
        obj = models.ChatLogs.objects.get(pk=chat_id)
        
        new_message = {
            "role": role, # user or model
            "content": text,
            "timestamp": timezone.now().isoformat()
        }
        
        if obj.content is None:
            obj.content = []
        
        obj.content.append(new_message)
        obj.save(update_fields=['content'])  

# getting chat history to pass to model
# gets past 10 chats to save tokens
def get_chat_history(chat_id): 
    chatlog_obj = models.ChatLogs.objects.get(pk=chat_id)
    chatlog = chatlog_obj.content

    history = []
    for msg in chatlog:
        history.append({
            "role": msg['role'],
            "parts": [{"text": msg['content']}]
        })

    recent_history = history[-10:]
    return recent_history

# names the AI chat based on the user prompt
def name_chat(gemini_key, user_prompt):
    client = genai.Client(api_key=gemini_key) 
    model = "gemini-2.5-flash-lite" # extremely cheap

    prompt = f"""### Role
    You are a Chat Naming Specialist for a research application.

    ### Task
    Generate a concise, 2-4 word title that describes the *topic* of the user's message.

    ### Rules
    1. Format: Return ONLY the title text. No quotes.
    2. Content: Focus on the subject matter (e.g., "Quantum Computing Basics") rather than the action (e.g., "Explaining Quantum").
    3. Banned Words: Do NOT use the words: Bot, AI, Assistant, Chat, Explainer, Help, Question, or Response.
    4. Capitalization: Title Case.

    ### Examples
    - User: "Can you explain how CRISPR works?" -> Gene Editing Mechanics
    - User: "Help me find connections between these two papers" -> Cross-Paper Synthesis
    - User: "What are the notes I made on the Nvidia PDF?" -> Nvidia GPU Annotations

    ### Context
    User Prompt: {user_prompt}"""

    response = client.models.generate_content(
        model=model, 
        contents=prompt, 
        config=types.GenerateContentConfig(
            temperature=0.7)
        )

    return response.text

# main function that sends prompt and context to model and returns a response
def send_prompt(gemini_key, model, prompt, pdf_count=0, pdf_paths=[], chat_id=None):
    client = genai.Client(api_key=gemini_key) 

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
    - Use LaTeX for ALL mathematical formulas or scientific notations.
    - IMPORTANT: Wrap inline math in single dollar signs (e.g., $E=mc^2$).
    - IMPORTANT: Wrap block equations in double dollar signs (e.g., $$ x = ... $$).

    # LIMITATIONS
    - Do not hallucinate data that isn't present in the user's annotations or papers. However you can use general knowledge if no data is passed to you in the context.
    """

    # getting recent chat history to give gemini conversation context
    chat_history = get_chat_history(chat_id)

    chat = client.chats.create(
        model=model,
        history=chat_history, 
        config=types.GenerateContentConfig(
            system_instruction=sys_prompt, 
            temperature=0.7
        )
    )

    message_contents = []

    # adding pdfs if they need to be added
    if pdf_count > 0:
        for path in pdf_paths:
            if path.exists():
                message_contents.append(
                    types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type='application/pdf',
                    )
                )

    message_contents.append(prompt)

    response = chat.send_message(
        message=message_contents
    )

    return response.text

# general function to embed all annotations that are marked to be embedded
# Could do matryoshka embeddings
def embed_annotations(): 
    pass

