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
    min_cluster_size = max(5, int(n_samples / 10))
    major_clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=5, metric='euclidean')
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
        m_label = data['major_topic']
        s_label = data['sub_topic']

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

# Whole big function that creates all of the smart collection stuff
def run_smart_collection():
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

    # pyright: ignore[reportOptionalSubscript]
    # pyright: ignore[reportOptionalMemberAccess]
    # writing everything back

    for annot_obj_pk in cluster_results.keys():  
        major_cluster = cluster_results[annot_obj_pk]["major_topic"]   
        sub_cluster = cluster_results[annot_obj_pk]["sub_topic"]
        sub_cluster_tuple = (major_cluster, sub_cluster)

        # replacing major cluster 
        major_label = new_mappings[major_cluster]
        cluster_results[annot_obj_pk]["major_topic"] = major_label

        # replacing sub cluster 
        sub_label = new_mappings[sub_cluster_tuple]
        cluster_results[annot_obj_pk]["sub_topic"] = sub_label

    """
    cluster_results now looks like this: type == dict 
    annotation model obj pk: {
        major_topic : human readable label
        sub_topic : human readable label
    }

    Will write everything back to the db after we find the x,y coords for each object to save a round trip
    """

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
    
    print(f"Successfully updated {len(updates)} annotations.")

    # saving ids to SmartCollections
    annot_ids = list(cluster_results.keys())

    smart_collection_obj = models.SmartCollections.objects.first()

    if smart_collection_obj: 
        smart_collection_obj.is_ready = True 
        smart_collection_obj.annotation_ids = annot_ids
        smart_collection_obj.save(update_fields=["is_ready", "annotation_ids"])

    else: 
        models.SmartCollections.objects.create(
            annotation_ids=annot_ids, 
            is_ready=True, 
            reading_recommendations = None
        )
    
    smart_collection_obj = models.SmartCollections.objects.first()
    if not smart_collection_obj: 
        return 
    
    recs = generate_reading_recommendations(annot_ids)

    if not recs: 
        return

    smart_collection_obj.reading_recommendations = recs # type: ignore
    smart_collection_obj.save(
        update_fields=["reading_recommendations"]
    )


