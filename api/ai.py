# File where all calls to AI model provider are handled 
from google import genai
from google.genai import types
import pathlib
import api.models as models
import api.serializers as serializers
from django.utils import timezone
import os
import numpy as np 
import hdbscan
from collections import defaultdict
import random
import umap
backup_gemini_key = os.getenv("GEMINI_API_KEY")

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

# NOTE: following is specifically for Smart Collections

# general function to embed all annotations that are marked to be embedded (batch)
def embed_annotations():
    client = genai.Client(api_key=backup_gemini_key) 

    # getting all anots to update
    annots_to_embed = list(models.Annotations.objects.filter(
        needs_embedding=True  
    ).select_related("document"))

    if not annots_to_embed:
        print("No annotations to embed.")
        return
    
    print(f"embedding {len(annots_to_embed)} notes.")

    ordered_notes_content = []
    
    # droppping noise from annots obj, only want to embed useful stuff
    for a in annots_to_embed: 
        title = a.document.title
        
        # extract sticky note text only
        sticky_text = ""
        data = a.sticky_note_data
        if isinstance(data, list):
            extracted_texts = [str(item.get("content", "")) for item in data] # type: ignore
            sticky_text = "".join(extracted_texts)

        notepad_content = a.notepad or ""

        content_string = f"{title}|{sticky_text}|{notepad_content}" # formatted content string
        ordered_notes_content.append(content_string)

    # NOTE: I think that gemini might have a limit on how many indiviudal strings u can send at once 
    # if embedding is erroring this might be the issue, you might have to change it to chunk the requests
    # but this is prob only an issue if u have 100+ notes in a single session (very unlikely)
    result = client.models.embed_content(
        model="text-embedding-004", 
        contents=ordered_notes_content,
        config=types.EmbedContentConfig(
            output_dimensionality=512
        )
    )

    to_update = []
    
    # converting embedding to binary and setting other fields
    # not gonna use the given method on the annot model because bulk update is faster
    # can zip bc gemini gurantees they come back in same order
    for obj, embedding in zip(annots_to_embed, result.embeddings):  # type: ignore
        obj.embedding_binary = np.array(embedding.values, dtype=np.float32).tobytes()
        obj.needs_embedding = False
        to_update.append(obj)
    
    models.Annotations.objects.bulk_update(to_update, ['embedding_binary', 'needs_embedding'])
    
    print(f"Successfully embedded {len(to_update)} annotations.")

# clusters embeddings into major and sub clusters for the creation of a smart collection
def cluster_embeddings(): 
    # creating clusters using hbdscan
    # uses all notes that have embeddings
    annotations = models.Annotations.objects.filter(
        embedding_binary__isnull = False
    ).values('id', 'embedding_binary')

    ids = [] # specifically annot ids
    vectors = []

    for annot in annotations:
        vector = np.frombuffer(annot['embedding_binary'], dtype=np.float32)
        
        if vector.shape[0] == 512: # making sure dim count is good
            ids.append(annot['id'])
            vectors.append(vector)

    if not vectors:
        print("No valid vectors found.")
        return None, None, None

    X = np.array(vectors)
    
    n_samples = X.shape[0]
    min_cluster_size = max(5, int(n_samples / 10))
    major_clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=5, metric='euclidean')
    major_labels = major_clusterer.fit_predict(X)

    results_map = defaultdict(dict)
    
    # Group idxs by their major cluster label
    major_cluster_indices = defaultdict(list)
    for index, label in enumerate(major_labels):
        annot_id = ids[index]
        results_map[annot_id]['major_cluster'] = int(label)
        results_map[annot_id]['sub_cluster'] = None 
        
        # filter out noise (-1) for sub-clustering
        if label != -1:
            major_cluster_indices[label].append(index)

    # sub clustering
    print(f"Found {len(major_cluster_indices)} major clusters. Starting sub-clustering")

    for major_label, indices in major_cluster_indices.items():
        # Extract vectors belonging to this specific major cluster, given by indices
        sub_X = X[indices]
        
        sub_clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2)
        sub_labels = sub_clusterer.fit_predict(sub_X)
        
        for i, sub_label in enumerate(sub_labels): # iterating thru sublabels
            original_index = indices[i]
            annot_id = ids[original_index]
            
            results_map[annot_id]['sub_cluster'] = int(sub_label)

    return results_map, ids, vectors # returning ids and vectors as well because I use it later in the view for the UMAP dimension reduction

# Gets representative samples of each cluster to send to AI model for labelling 
def get_representative_samples(cluster_results, max_major=7, max_sub=3): 
    major_samples = defaultdict(list)
    # NOTE: sub-cluster 0 in Major clutser A != sub-cluster 0 in Major cluster B
    # important because don't want to get samples from different subclusters accidentally
    sub_samples = defaultdict(list)

    # iterate through the data once and bucket them immediately
    items = list(cluster_results.items())
    
    # shuffling to get random representative items
    random.shuffle(items) 

    for annot_id, data in items:
        m_label = data['major_cluster']
        s_label = data['sub_cluster']

        # major cluster
        # Only add if limit hasn't hit yet
        if len(major_samples[m_label]) < max_major:
            major_samples[m_label].append(annot_id)

        # sub cluster sampling
        if s_label != -1: # ignores noise
            # use a tuple key to keep scopes separate
            if len(sub_samples[(m_label, s_label)]) < max_sub:
                sub_samples[(m_label, s_label)].append(annot_id)

    return major_samples, sub_samples

# func for labeling a major/sub cluster
# takes pks from Annotation model, formats those rows to be sent to the model, gets back label for cluster
def label_cluster(pks_to_use):
    client = genai.Client(api_key=backup_gemini_key) 
    model = "gemini-2.5-flash" # need a half-decent model for this task

    annot_model_objs = models.Annotations.objects.filter(
        pk__in = pks_to_use
    ).select_related("document")

    content = []
    for obj in annot_model_objs: 
        title = obj.document.title
        sticky_text = ""
        data = obj.sticky_note_data
        if isinstance(data, list):
            # formatting sticky notes so that they are LLM readable
            formatted_notes = [
                f"- {str(item.get('content', '')).strip()}" 
                for item in data  # type: ignore
                if item.get("content", "").strip()
            ]
    
            sticky_text = "\n".join(formatted_notes)

        notepad_content = obj.notepad or ""

        # formatted content string
        content_string = f"""Doucment Title: {title}
        
        Content from users sticky notes: 
        {sticky_text}

        Content from users notepad:
        {notepad_content}
        """ 
        content.append(content_string)


    prompt = f"""### Role
    You are an expert Knowledge Manager. Your specialty is synthesizing diverse research notes into precise, high-level topic labels.

    ### Task
    Analyze the provided user documents and notes, which have been grouped by the HDBSCAN clustering algorithm.
    Generate a **single, concise topic label (2-5 words)** that represents the *common semantic thread* connecting these items.

    ### Constraints & Rules
    1. **Format:** Return ONLY the label text. No quotation marks, no preamble, no period at the end.
    2. **Style:** Title Case.
    3. **Focus:** Describe the *subject matter*, not the format or the user's intent.
    4. **Strict Negative Constraints:** - Do NOT use: "Summary", "Overview", "Collection", "Various", "Miscellaneous", "Notes", "Papers", "Analysis".
    - Do NOT use: "Bot", "AI", "Assistant", "Chat", "Help".

    ### Input Data
    {content}
    """

    response = client.models.generate_content(
        model=model, 
        contents=prompt, 
        config=types.GenerateContentConfig(
            temperature=0.7)
        )

    return response.text

# convert n dim vector to 128 dims
# can do this bc MRL
def reduce_dimensions(data_dict, target_dim=128):
    reduced_dict = {}
    
    for key, vector in data_dict.items():
        sliced = vector[:target_dim]
        norm = np.linalg.norm(sliced) # normalizing sliced vector so mag == 1. 
        if norm > 0:
            sliced = sliced / norm
            
        reduced_dict[key] = sliced.astype(np.float32)
        
    return reduced_dict

def umap_dim_reduction_to_2d(data_dict): 
    ids = list(data_dict.keys())
    
    # stack vectors into np matrix (n x dimensions)
    matrix = np.stack(list(data_dict.values()))

    # n_components - 2 dims
    # cos is good for vector embeddings
    reducer = umap.UMAP(n_components=2, metric='cosine', min_dist=0.1)
    embedding_2d = reducer.fit_transform(matrix)

    result_dict = {
        ids[i]: embedding_2d[i].tolist()  # type: ignore
        for i in range(len(ids))
    }
    
    return result_dict