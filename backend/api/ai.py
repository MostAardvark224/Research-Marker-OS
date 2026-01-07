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
import json
import re
import colorsys
import math
from django.db.models import Avg
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


"""
Helper func for formatting 
output will look like this: 

{
    title, 
    major topic, 
    sub topic, 
    formatted sticky notes, 
    formatted notepad,
    highlights 
}
"""

def format_annotation_for_readability(obj): 
    formatted_content = defaultdict(dict)
    sticky = obj.sticky_note_data
    notepad = obj.notepad
    highlights = obj.highlight_data

    # formatting sticky 
    # care abt content, possibly page, and tag
    formatted_sticky = []
    if sticky and type(sticky) == dict:
        for key, note in sticky.items():  # type: ignore
            d = dict(
                content = note["content"] if note["content"] else None, 
                tag = note["tag"] if note["tag"] else None, 
                )
            if any(d.values()): 
                formatted_sticky.append(d)
            
    # formatting highlights
    formatted_highlights = [h["text"] for h in highlights if h["text"]]
    
    final = dict(
        title = obj.document.title,
        major_topic = obj.major_topic, 
        sub_topic = obj.sub_topic,
        sticky_notes = formatted_sticky, 
        notepad = obj.notepad, 
        formatted_highlights = formatted_highlights
    )

    formatted_content[obj.pk] = final 

    return formatted_content
    
"""
Handles RAG context injection to prompt 
only modifies the prompt itself, then just use the send prompt function for a response

specifics: 
- will use embedding similarity to find relevant annotation objects (selected if they are above a sim threshold)
- Will format each object into an easy to read format for the model 
- Will send the model each formatted object if the inclusion of that object doesn't cause the token limit to be exceeded (thinking 2,000 tokens as a RAG limit to save money and not overload the model, could change tho)
- Will use BM25 for keyword analysis (will find some way to fit this into the similarity pipeline) 

- once I have rankings from both cos sim and BM25, will run Reciprocal Rank Fusion (RRF) to find the highest annot objects in both rankings

- could have a small LLM turn the raw user prompt into specific querys i can run in my db. Extracts useful stuff from user query (query decomposition).
- could have LLM hallucinate possible notes if the user prompt is super vague and just embed those

In general embedding the user prompt could have its downsides, could have an LLM generate a better verison and then embed that 
- be cautious of model calls tho don't want to have too many
"""

# function that executes embedding search
def embedding_search_rankings(query, annot_objs): 
    client = genai.Client(api_key=backup_gemini_key) 
    query_emb_full = client.models.embed_content(
        model="text-embedding-004", 
        contents=query,
        config=types.EmbedContentConfig(
            output_dimensionality=512
        )
    )

    if not query_emb_full.embeddings:
        print("No embeddings returned by API")
        return
    
    raw_embedding = query_emb_full.embeddings[0].values
    query_emb = np.array(raw_embedding, dtype=np.float32)

    query_norm = np.linalg.norm(query_emb)
    if query_norm > 0:
        query_emb = query_emb / query_norm

    # getting annotation model object rankings based on cos similarity 
    # must be above threshold of 0.6 to be included in the ranking

    data = annot_objs.values_list("id", "embedding_binary")

    if data: 
        thresh = 0.6

        ids, binaries = zip(*data)

        flat_array = np.frombuffer(b''.join(binaries), dtype=np.float32)

        dimensions = len(flat_array) // len(ids)

        matrix = flat_array.reshape(len(ids), dimensions) # matrix of all embeddings for annot model objs

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)

        # normalizing the matrix
        matrix = matrix / (norms + 1e-10) # prevents div by zero

        # keeping ids (for the annot model) that are above the threshold
        # ranking them by similarity to highest similarity comes first
        similarities = matrix @ query_emb

        valid_indices = np.where(similarities >= thresh)[0]

        if len(valid_indices) == 0:
            return None 

        # Extract valid ids and Scores
        valid_ids = [ids[i] for i in valid_indices]
        valid_scores = similarities[valid_indices]

        # can zip because idx of ids and matrix match up
        emb_rankings = sorted(zip(valid_ids, valid_scores), key=lambda x: x[1], reverse=True)
        emb_rankings = [t[0] for t in emb_rankings] # list of ranked ids
        return emb_rankings
    
# function that does BM25 rankings 
def bm25_search_rankings(query, annot_objs): 
    tokens = re.findall(r"\b\w+(?:['\-]\w+)*\b", query.lower())
     
    hits = models.AnnotationIndex.objects.filter(
        term__word__in=tokens, 
        annotation__in = annot_objs
    ).select_related('term').values(
        'annotation_id', 
        'frequency', 
        'term__idf', 
    )
    
    scores = {}
    # industry standard, will finetune later
    k1 = 1.5
    b = 0.75

    # avg doc length
    avgdl = models.Annotations.objects.aggregate(Avg("token_count"))['token_count__avg']
    if not avgdl:
        return []

    # calculating doc len for each id
    annot_ids = [hit['annotation_id'] for hit in hits]
    doc_len_map = dict(
        models.Annotations.objects.filter(id__in=annot_ids).values_list('id', 'token_count')
    )
    
    for hit in hits:
        annot_id = hit['annotation_id']
        tf = hit['frequency']
        idf = hit['term__idf'] 

        doc_len = doc_len_map.get(annot_id, avgdl)
        
        # bm25 form
        numerator = tf * (k1 + 1)
        # NOTE: fix to fetch actual doc length
        denominator = tf + k1 * (1 - b + b * (doc_len / avgdl)) # type: ignore
        
        score = idf * (numerator / denominator)
        
        # summing scores for each annot_id
        scores[annot_id] = scores.get(annot_id, 0.0) + score
    
    bm25_rankings = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    bm25_rankings = [t[0] for t in bm25_rankings] # list of ranked ids
    return bm25_rankings

def calculate_idf(docs_containing_term): 
    total_docs_count = models.Annotations.objects.filter(
        content_hash__isnull=False
    ).exclude(
        content_hash=""
    ).count()

    n = docs_containing_term # just to stay in terms of formula

    numerator = total_docs_count - n + 0.5
    denominator = n + 0.5
    total = math.log((numerator / denominator) + 1)
    return total

# takes both sets of rankings and produces one final ranking
# both are ordered tuples, where 0 idx is id and 1 idx is score
# scores have been normalized between -1 and 1
def rerank_rag(emb_ranks, bm_ranks):
    if not emb_ranks:
        return bm_ranks if bm_ranks else []
    if not bm_ranks:
        return emb_ranks
    
    emb_rank_map = {doc_id: i for i, doc_id in enumerate(emb_ranks)}
    bm_rank_map = {doc_id: i for i, doc_id in enumerate(bm_ranks)}
    
    all_ids = set(emb_rank_map.keys()) | set(bm_rank_map.keys())
    
    scores = {}
    k = 60 # standard for k constant
    
    for doc_id in all_ids:
        if doc_id in emb_rank_map:
            # +1 because index is 0 based but rank is 1 based
            emb_score = 1 / (k + emb_rank_map[doc_id] + 1)
        else:
            emb_score = 0.0
            
        if doc_id in bm_rank_map:
            bm_score = 1 / (k + bm_rank_map[doc_id] + 1)
        else:
            bm_score = 0.0
        
        scores[doc_id] = emb_score + bm_score
    
    top_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_id_list =  [x[0] for x in top_ids]
    return top_id_list[:20]

def rag_context_injection(original_prompt): 
    annot_objs = models.Annotations.objects.filter(
        embedding_binary__isnull = False
    )

    if annot_objs: 
        
        emb_rankings = embedding_search_rankings(original_prompt, annot_objs)
        
        bm25_rankings = bm25_search_rankings(original_prompt, annot_objs)

        # RRF to get finalized list of annots
        # should be able to handle one of the rankings failing/returning nothing
        ids = rerank_rag(emb_rankings, bm25_rankings) # list of annot obj, highest scoring first

        # formatting annots for model readability             
        objs = models.Annotations.objects.filter(pk__in = ids).prefetch_related("document") # unordered
        obj_map = {obj.pk: obj for obj in objs}
        ordered_objs = [obj_map[id] for id in ids if id in obj_map] # ordered list of objs
        
        # keeping objects until I hit the token limit
        # not going to use gemini token counter api to save http round trip time, will just cap at 1500 words
        word_limit = 1500
        current_count = 0 
        context = []
        for obj in ordered_objs: 
            try: 
                annotation = format_annotation_for_readability(obj) # dict

                json_annotation = json.dumps(annotation) # str to count words
                wcount = len(re.findall(r"\b\w+(?:['\-]\w+)*\b", json_annotation))
                current_count += wcount

                if current_count <= word_limit: 
                     context.append(annotation)
                else: 
                    if (len(context) == 0): 
                        continue # skip to next to try to get some context
                    else: 
                        break # reached limit

            except Exception as e: 
                print(f"failed dumping annotation {e}")
                continue

        # retuning final context as json string
        if not context: 
            return
        
        try: 
            fin = json.dumps(context)
            return fin
        except Exception as e: 
            print(f"failed final dump {e}")
            return

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

"""
Smart Collections Notes: 

Features: 
General idea - give users a 2d graph mapping out all of their ideas and showing them relationships between them. 

3 layers: 
- Major Topics 
- Subtopics 
- User papers/notes

As the user scrolls in, major topics change to subtopics, etc. 
lines connect between idea "nodes", showing relationships in notetaking ideas.

Sidebar: 3 tabs.
Tab 1: AI chat (similar to on base page with RAG setup)
Tab 2: Explore functionality. Shows hierarchy of topics/ideas in text form rather than graph form. Is interactive.
Tab 3: Recommendations. Generated by AI, takes similar topics and generates recommendations to fill gaps in knowledge. Effectively gives more reading topics.

Technical Implementation: 
1. Embed all notes objects (dim count/model TBD)
- Not including highlights in the embedding to save money on tokens.
- Using gemini embedding api for speed. Also, Gemini api is already trained w/ Matryoshka (MRL) system in mind, so I can just slice and normalize vectors for faster computation
- Will store as a 512 dim embedding (decided based on MTEB score google provides)

2. Create clusters of papers based using HDBScan
- 512 dim vector will keep high quality clusters
- Will take major clusters and pass them through so I can get make sub-clusters as well
- make sure to keep track of which annot is attached to what cluster    

3. Send clusters off to LLM, ask for a singular major topic + sub-topics 
- Keep track of which annotations are in what cluster

4. Leverage MRL and slice + normalize unit vectors so that they are now 128 dims (will use for vector projection down to 2d)

5. Use UMAP to project each vector embedding down to 2D (so that the vector can be represented on a graph)

6. Save everything to the django model.
- save fields to each annot obj
- get all anot objects and save them to the smart collections obj

7. Send to frontend and render graph
- note: place topics in geometic center of their related annotations to make it look nice on ui
"""


# general function to embed all annotations that are marked to be embedded (batch)
def embed_annotations():

    # getting all anots to update
    annots_to_embed = list(models.Annotations.objects.filter(
        needs_embedding=True  
    ).select_related("document"))

    if not annots_to_embed:
        print("No annotations to embed.")
        return
    
    print(f"embedding {len(annots_to_embed)} notes.")
    client = genai.Client(api_key=backup_gemini_key) 

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
    min_cluster_size = max(4, int(n_samples / 10))
    major_clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=4, metric='euclidean')
    major_labels = major_clusterer.fit_predict(X)

    results_map = defaultdict(dict)
    
    # Group idxs by their major cluster label
    major_cluster_indices = defaultdict(list)
    for index, label in enumerate(major_labels):
        annot_id = ids[index]
        results_map[annot_id]['major_topic'] = int(label)
        results_map[annot_id]['sub_topic'] = None 
        
        # filter out noise (-1) for sub-clustering
        if label != -1:
            major_cluster_indices[label].append(index)

    # sub clustering
    print(f"Found {len(major_cluster_indices)} major clusters. Starting sub-clustering")

    for major_label, indices in major_cluster_indices.items():
        # Extract vectors belonging to this specific major cluster, given by indices
        sub_X = X[indices]
        
        n_samples = sub_X.shape[0]
        min_cluster_size = max(2, int(n_samples / 10))
        sub_clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_cluster_size)
        sub_labels = sub_clusterer.fit_predict(sub_X)
        
        for i, sub_label in enumerate(sub_labels): # iterating thru sublabels
            original_index = indices[i]
            annot_id = ids[original_index]
            
            results_map[annot_id]['sub_topic'] = int(sub_label)

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
        m_label = data['major_topic']
        s_label = data['sub_topic']

        # major cluster
        # Only add if limit hasn't hit yet
        if len(major_samples[m_label]) < max_major:
            major_samples[m_label].append(annot_id)

        # sub cluster sampling
        if s_label != -1 and s_label: # ignores noise
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

def umap_dim_reduction_to_2d(data_dict, n_neighbors=15): 
    ids = list(data_dict.keys())
    
    # stack vectors into np matrix (n x dimensions)
    matrix = np.stack(list(data_dict.values()))

    # n_components - 2 dims
    # cos is good for vector embeddings
    reducer = umap.UMAP(n_components=2, 
                        n_neighbors=n_neighbors,
                        metric='cosine', 
                        min_dist=0.1)
    embedding_2d = reducer.fit_transform(matrix)

    result_dict = {
        ids[i]: embedding_2d[i].tolist()  # type: ignore
        for i in range(len(ids))
    }
    
    return result_dict

# generates new user reading recs based on their given context (papers)
def generate_reading_recommendations(annot_ids): 
    client = genai.Client(api_key=backup_gemini_key) 
    model = "gemini-3-flash-preview" 

    """
    NOTE: make sure string is formatted well so its easy for user to read
        - want json output
        - ENSURE THAT DICT WONT BREAK WHEN DUMPED TO JSON
    retrieving context
    want data in this format to send to model: 

    {
        major topic: {
            sub topic : {
                [paper1, paper2, etc.]
            }
        }
    }
    """

    if not annot_ids: 
        return

    annot_objs = models.Annotations.objects.filter(
        pk__in = annot_ids
    ).select_related("document")

    data_dict = {}
    for obj in annot_objs: 
        maj = obj.major_topic or "Unassigned"
        sub = obj.sub_topic or "Unassigned Sub Topic"

        if not maj in data_dict: 
            data_dict[maj] = {}

        if not sub in data_dict[maj]:
            data_dict[maj][sub] = []

        if len(data_dict[maj][sub]) <= 4: # max docs just to save tokens and not overload model w/ too much context
            data_dict[maj][sub].append(str(obj.document.title))
        
    content = json.dumps(data_dict)

    prompt = f"""### Role
    You are an expert Academic Research Advisor. Your specialty is analyzing a researcher's current bibliography to identify knowledge gaps, adjacent fields, and logical next steps for investigation.

    ### Task
    Analyze the provided JSON data, which represents the user's current Knowledge Graph (structured as Major Topic -> Sub Topic -> Paper Titles). 
    Based on these existing interests, recommend a maximum of **5 NEW research areas/topics** the user should explore next. 

    These recommendations should be:
    1. **Adjacent:** Related to their current work but distinct enough to expand their horizons.
    2. **Specific:** Avoid overly generic terms like "Math" or "Science." Focus on sub-fields (e.g., instead of "AI", suggest "Neuromorphic Engineering").
    3. **Actionable:** Provide specific paper titles that exist in academic literature or sound highly plausible within that domain.

    ### Constraints & Rules
    1. **Format:** Return ONLY a valid JSON object. Do not include markdown formatting (like ```json), introduction, or conclusion.
    2. **Novelty:** Do not recommend topics that are already explicitly listed as "Major Topics" in the input data.
    3. **Structure:** The output must strictly follow the schema below.

    ### Output Schema
    {{
    "Name of New Topic": {{
        "overview": "A brief 1-2 sentence explanation of why this topic is relevant to the user's current research.",
        "paper1": "Title of a specific foundational or cutting-edge paper in this field",
        "paper2": "Title of a second complementary paper in this field"
    }},
    ... (repeat for up to 5 topics)
    }}

    ### Input Data
    {content}
    """

    response = client.models.generate_content(
        model=model, 
        contents=prompt, 
        config=types.GenerateContentConfig(
            temperature=0.7, 
            response_mime_type="application/json"
            )
        )

    resp = response.text

    if resp:
        # cleaning any json markdown model might produce
        json_clean_pattern = re.compile(r"^```json\s*|\s*```$", flags=re.MULTILINE | re.IGNORECASE)

        clean_json_str = json_clean_pattern.sub("", resp.strip())

        try:
            recs = json.loads(clean_json_str)
            return recs

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            return

    else: 
        return


"""
Generates color palette for each cluster to be displayed in the frontend 
{
    <major_topic>: {
        major: "some hex",
        sub: "some hex",
        paper: "some hex",
    }
}

"""

# converts hsv to hex string
def _hsv_to_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return '#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255))


"""
    Assigns colors to topics. 
    1. Uses a curated palette for the first 12 topics.
    2. Uses a Golden Ratio algorithm to generate unique, legible colors 
       for any topics beyond the palette size.
"""

def generate_colors(topics):
    
    fixed_palette = [
        {"major": "#4338ca", "sub": "#818cf8", "paper": "#eef2ff"}, # Indigo
        {"major": "#059669", "sub": "#34d399", "paper": "#ecfdf5"}, # Emerald
        {"major": "#e11d48", "sub": "#fb7185", "paper": "#fff1f2"}, # Rose
        {"major": "#7c3aed", "sub": "#a78bfa", "paper": "#f5f3ff"}, # Violet
        {"major": "#d97706", "sub": "#fbbf24", "paper": "#fffbeb"}, # Amber
        {"major": "#0891b2", "sub": "#22d3ee", "paper": "#ecfeff"}, # Cyan
        {"major": "#475569", "sub": "#94a3b8", "paper": "#f8fafc"}, # Slate
        {"major": "#db2777", "sub": "#f472b6", "paper": "#fdf2f8"}, # Pink
        {"major": "#ea580c", "sub": "#fb923c", "paper": "#fff7ed"}, # Orange
        {"major": "#0d9488", "sub": "#5eead4", "paper": "#f0fdfa"}, # Teal
        {"major": "#dc2626", "sub": "#f87171", "paper": "#fef2f2"}, # Red
        {"major": "#2563eb", "sub": "#60a5fa", "paper": "#eff6ff"}, # Blue
    ]
    
    colors = {}
    num_fixed = len(fixed_palette)
    
    # Golden ratio conjugate ensures distinct hues for the dynamic part
    golden_ratio_conjugate = 0.618033988749895 
    
    for i, topic in enumerate(topics):
        
        if i < num_fixed:
            colors[topic] = fixed_palette[i]
            
        else:
            hue = (i * golden_ratio_conjugate) % 1.0
            
            colors[topic] = {
                "major": _hsv_to_hex(hue, 0.75, 0.60), 
                "sub":   _hsv_to_hex(hue, 0.55, 0.90), 
                "paper": _hsv_to_hex(hue, 0.10, 0.98)  
            }
            
    return colors

# finds good baseline for cos similarity between embeddings 
# not running constantly, only running for testing
def test_cos_sim():
    # If your dataset is small (<5k), you can use the whole matrix.
    data = models.Annotations.objects.filter(
        embedding_binary__isnull=False
    ).values_list('id', 'embedding_binary')

    # ids will be a tuple of all ids
    # binaries will be a tuple of all byte strings
    ids, binaries = zip(*data)

    flat_array = np.frombuffer(b''.join(binaries), dtype=np.float32)

    dimensions = len(flat_array) // len(ids) # should be 512 but doing this instead of hardcoding
    matrix = flat_array.reshape(len(ids), dimensions)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / (norms + 1e-5)

    sims = np.dot(matrix, matrix.T) 

    flat_scores = sims.flatten()
    flat_scores = flat_scores[flat_scores < 0.99] # Remove self-identity matches

    print(f"Average Similarity: {np.mean(flat_scores):.4f}")
    print(f"90th Percentile:    {np.percentile(flat_scores, 90):.4f}")
    print(f"95th Percentile:    {np.percentile(flat_scores, 95):.4f}")
    print(f"97th Percentile:    {np.percentile(flat_scores, 97):.4f}")

# cos similarity to find similar papers
def find_similar_papers(): 
    data = models.Annotations.objects.filter(
        embedding_binary__isnull=False
    ).values_list('id', 'embedding_binary')

    if data:
        # ids will be a tuple of all ids
        # binaries will be a tuple of all byte strings
        ids, binaries = zip(*data)

        flat_array = np.frombuffer(b''.join(binaries), dtype=np.float32)

        dimensions = len(flat_array) // len(ids) # should be 512 but doing this instead of hardcoding
        matrix = flat_array.reshape(len(ids), dimensions)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / (norms + 1e-5) # Prevent divide by zero

        similarity_matrix = np.dot(matrix, matrix.T)
        # thresh is 0.6 based on testing, but this can change as my dataset grows
        thresh = 0.6
        updates = []
        
        similar_papers = {}
        for i, row_scores in enumerate(similarity_matrix):
            current_id = ids[i]

            valid_indices = np.where(row_scores >= thresh)[0] # type: ignore

            # Sort these specific valid indices by score (descending)
            valid_scores = row_scores[valid_indices]
            
            sorted_relative_indices = np.argsort(valid_scores)[::-1]
            
            # Map back to the original matrix indices
            final_indices = valid_indices[sorted_relative_indices]

            top_ids = []
            for idx in final_indices:
                neighbor_id = ids[idx]
                if neighbor_id != current_id: # Remove self-match
                    top_ids.append(neighbor_id)

            updates.append(
                models.Annotations(
                    id=current_id, 
                    similar_papers=top_ids  
                )
            )

        models.Annotations.objects.bulk_update(
            updates, 
            ['similar_papers'],
            batch_size=1000
        ) 


# Whole big function that creates all of the smart collection stuff
def run_smart_collection():
    embed_annotations()
    print("clustering embeddings")
    cluster_results, ids, vectors = cluster_embeddings()
    print("finished clustering embeddings")

    """
    cluster_results now looks like this: type == dict 
    annotation model obj pk: {
        major_topic : int major_cluster (just value assigned by Hdb scan, no semantic meaning yet),
        sub_topic : int sub_cluster (just value assigned by Hdb scan, no semantic meaning yet)
    }

    ids and vectors will be used later for UMAP dimension reduction to get x,y coordinates.
    Assigning it here because I don't want to needlessly requery the db for the same thing again.
    """

    if not cluster_results or not isinstance(cluster_results, dict) or not ids or not vectors: 
        print("no results to cluster. This is likely because you don't have any/enough embedded vectors.")
        return

    # now I use cluster_results to pass some notes/paper titles to an AI model and it then returns a human-readable label for either the major cluster or sub cluster
    
    # getting representative samples to send to model 
    print("getting representative samples")
    major_samples, sub_samples = get_representative_samples(cluster_results=cluster_results)
    print("finished getting representative samples")

    """
    major_samples looks like this: type == dict 
    {
        0: [1,2,3,4,5],
    }
    Where 0 is major cluster zero and 1,2,3, etc. are annotations model obj pks in that major cluster

    sub_samples looks like this: type == dict 
    {
        (0, 0): [10,15,20],
    }
    Where the first 0 is major cluster zero, the second 0 represents the first sub cluster of major cluster zero and 10,15,20, etc. are annotations model obj pks in that sub cluster
    NOTE: must access sub_samples with tuple based index keys
    """

    # sending representative samples to model
    # getting actual content strings from samples based on model PK
    # replace non-readable numeric clusters in cluster_results with readable results 
    print("sending representative samples to model")

    new_mappings = {}

    # doing major clusters first
    for cluster, pks in major_samples.items():
        cluster_label =  label_cluster(pks)

        # saving mapping: 
        new_mappings[cluster] = cluster_label

    # sub clusters
    for cluster, pks in sub_samples.items(): # cluster is already of type tuple
        cluster_label =  label_cluster(pks)

        # saving mapping: 
        new_mappings[cluster] = cluster_label

    print("got cluster labels")

    # writing everything back

    for annot_obj_pk in cluster_results.keys():  
        major_cluster = cluster_results[annot_obj_pk]["major_topic"]   
        sub_cluster = cluster_results[annot_obj_pk]["sub_topic"]
        sub_cluster_tuple = (major_cluster, sub_cluster)

        # replacing major cluster 
        if major_cluster == -1:
             cluster_results[annot_obj_pk]["major_topic"] = "Uncategorized"
        else:
            cluster_results[annot_obj_pk]["major_topic"] = new_mappings.get(major_cluster, "Unknown Topic")

        # replacing sub cluster 
        try: 
            sub_label = new_mappings[sub_cluster_tuple]
            cluster_results[annot_obj_pk]["sub_topic"] = sub_label
        except Exception as e: # handles key errors
            cluster_results[annot_obj_pk]["sub_topic"] = None

    """
    cluster_results now looks like this: type == dict 
    annotation model obj pk: {
        major_topic : human readable label
        sub_topic : human readable label
    }

    Will write everything back to the db after we find the x,y coords for each object to save a round trip
    """

    # getting list of all major cluster names for color assignment
    unique_major_clusters = list(set([maj["major_topic"] for maj in cluster_results.values()]))

    # getting colors: 
    colors = generate_colors(unique_major_clusters)

    try: 
        colors = json.dumps(colors)
    except Exception as e: 
        print("failed to dump colors to json")

    # getting x,y coords 
    # combining ids and vectors into a dict to make it easy to work with 

    annot_vectors = {}
    if isinstance(ids, list) and isinstance(vectors, list):
        for idx, id in enumerate(ids): 
            # idxs of id and vector should match up 
            annot_vectors[id] = vectors[idx]
    else: 
        print("either ids or vectors isnt a list, UMAP mapping will therefore not run")
        return 

    # now levraging Matryoshka representation learning to cut 512 dim vector down to 128 dims for easy and fast UMAP dimension reduction down to 2d
    annot_vectors = reduce_dimensions(data_dict = annot_vectors, target_dim=128)

    # using umap to get x,y coordinates based on each vector.
    # UMAP essentially drops the dims down from 128 to a 2d projection
    print("performing UMAP reduction")

    data_count = len(annot_vectors)
    
    safe_n_neighbors = max(2, min(15, data_count - 1))

    if data_count <= 2: # fallback
        print("Dataset too small for UMAP. Assigning default coordinates.")
        annot_coords = {k: [0.0, 0.0] for k in annot_vectors}
    else:
        annot_coords = umap_dim_reduction_to_2d(
            data_dict=annot_vectors, 
            n_neighbors=safe_n_neighbors
        )

    print("finished performing UMAP reduction")

    # combining annot_coords w/ cluster_results
    for id in cluster_results.keys(): 
        cluster_results[id]["x_coordinate"] = annot_coords[id][0]
        cluster_results[id]["y_coordinate"] = annot_coords[id][1]

    # now cluster results has major cluster, sub cluster, x coord and y coord for each id in anntotations.

    # writing everything back to db
    updates = []
    
    for annot_id, data in cluster_results.items():
        updates.append(
            models.Annotations(
                id=annot_id,
                major_topic=data['major_topic'],
                sub_topic=data['sub_topic'],
                x_coordinate=data.get('x_coordinate', 0.0), 
                y_coordinate=data.get('y_coordinate', 0.0)
            )
        )

    models.Annotations.objects.bulk_update(
        updates, 
        ['major_topic', 'sub_topic', 'x_coordinate', 'y_coordinate'],
        batch_size=1000
    )

    find_similar_papers()
    
    print(f"Successfully updated {len(updates)} annotations.")

    annot_ids = list(cluster_results.keys())

    recs = None
    # generating reading recommendations
    try:
        recs = generate_reading_recommendations(annot_ids)
    except Exception as e: 
        print(f"failed to generate recs: {e}")

    # saving to SmartCollections
    smart_collection_obj = models.SmartCollections.objects.first()

    if smart_collection_obj: 
        smart_collection_obj.is_ready = True 
        smart_collection_obj.annotation_ids = annot_ids
        smart_collection_obj.colors = colors # type: ignore
        smart_collection_obj.reading_recommendations = recs 

        smart_collection_obj.save(update_fields=["is_ready", "annotation_ids", "colors", "reading_recommendations"])

    else: 
        models.SmartCollections.objects.create(
            annotation_ids=annot_ids, 
            is_ready=True, 
            reading_recommendations = recs,
            colors = colors
        )
    
    


