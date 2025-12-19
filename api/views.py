from django.shortcuts import render
from rest_framework import viewsets
import api.models as models
import api.serializers as serializers
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
import os
import json
from pathlib import Path
from django.http import Http404, FileResponse
import time
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from . import models, serializers
from .user_preferences import load_user_preferences, write_user_preferences
from django.db.models import Q
import asyncio
import aiohttp
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
import io

# to bool helper method for flag parsing
def to_bool(value):
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('yes', 'true', 't', 'y', '1', 'on'):
            return True
        if normalized in ('no', 'false', 'f', 'n', '0', 'off'):
            return False
            
    return bool(value) # fallback

# View that returns folders, documents are nested within.
class CompleteFetch(APIView):
    def get(self, request, format=None):
        folders = models.Folder.objects.all().prefetch_related('documents')
        folder_serializer = serializers.FolderSerializer(folders, many=True)

        unassigned_docs = models.Document.objects.filter(folder__isnull=True)
        unassigned_serializer = serializers.DocumentSerializer(unassigned_docs, many=True)

        return Response({
            'folders': folder_serializer.data,
            'Unassigned': unassigned_serializer.data
        }, status=status.HTTP_200_OK)

# View that handles all document-related operations
from .OCR import create_searchable_pdf
class DocumentsViewSet(viewsets.ModelViewSet):
    queryset = models.Document.objects.all()
    serializer_class = serializers.DocumentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        files = request.FILES.getlist('file')

        if files:
            uploaded_documents = []

            skip_ocr = request.data.get("skip_ocr", "false").lower() == "true"
            
            # Extra handling for folder assignment
            folder_pk = request.data.get('folder_id', None)

            for file in files:
                data = {
                    'file': file, 
                    'title': file.name.removesuffix(Path(file.name).suffix), 
                    'folder': folder_pk 
                }
                
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

                if not skip_ocr: 
                    
                    start_time = time.time()
                    # Performing OCR, overwriting input file to not cause storage bloat
                    input_path = serializer.instance.file.path
                    output_path = input_path

                    try: 
                        ocr_result = create_searchable_pdf(input_path, output_path)

                        instance = serializer.instance
                        instance.searchable = True
                        instance.save()
                    
                    except Exception as e:
                        print("ERROR")
                        print(e)

                    uploaded_documents.append(serializer.data)
                    
                    end_time = time.time()
                    print(f"OCR Processing Time for {file.name}: {end_time - start_time} seconds")

            return Response(uploaded_documents, status=status.HTTP_201_CREATED)

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Overriding to delete the physical file in documents dir as well as the model obj.
        obj = self.get_object()

        if obj.file: 
            if os.path.isfile(obj.file.path): 
                os.remove(obj.file.path)
            else: 
                print(f"{obj.file.path} doesn't exist")

        return super().destroy(request, *args, **kwargs)

# Handles all folder-related operations
class FoldersViewSet(viewsets.ModelViewSet):
    queryset = models.Folder.objects.all()
    serializer_class = serializers.FolderSerializer

# Get Paper for annotation (streams file as raw binary)
class getPaper(APIView):
    def get(self, request, pk, format=None):
        try:
            document = models.Document.objects.get(pk=pk)
        except models.Document.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        file = document.file.open("rb")

        response = FileResponse(file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{document.title}.pdf"'

        return response

# Handle all annotation-related operations
class AnnotationsViewSet(viewsets.ModelViewSet):
    queryset = models.Annotations.objects.all()
    serializer_class = serializers.AnnotationSerializer
    lookup_field = 'document' # b/c only 1 annotations object per document

    # Get or create so that it works on every post req
    def create(self, request, *args, **kwargs):
        doc_id = request.data.get('document', None)
        
        annotation, created = models.Annotations.objects.get_or_create(
            document=models.Document.objects.get(pk=doc_id), 
            defaults={
                'highlight_data': request.data.get('highlight_data', {}),
                'notepad': request.data.get('notepad', ''),
                'sticky_note_data': request.data.get('sticky_note_data', {}),
                }
            )
        
        if not created:
            # Update existing annotation
            annotation.highlight_data = request.data.get('highlight_data', annotation.highlight_data)
            annotation.notepad = request.data.get('notepad', annotation.notepad)
            annotation.sticky_note_data = request.data.get('sticky_note_data', annotation.sticky_note_data)
            annotation.save()
        
        return Response(
            serializers.AnnotationSerializer(annotation).data, 
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
class UserPreferencesView(APIView): 
    def get(self, request): 
        preferences = load_user_preferences()
        return Response(preferences, status=status.HTTP_200_OK)

    def put(self, request): 
        preferences = request.data.get('preferences', {})
        print(preferences)
        write_user_preferences(preferences)
        return Response({'message': 'Preferences updated successfully.'}, status=status.HTTP_200_OK)

# Runs fetch from scholar inbox and uplaods papers to "Scholar Inbox" folder
from .scholar_inbox import fetch_scholar_inbox_papers
class FetchScholarInboxPapers(APIView):
    def post(self, request):
        # Running fetch, logic can be altered in scholar_inbox.py
        login_url = os.getenv("SCHOLAR_INBOX_PERSONAL_LOGIN", "")
        amount_to_import = request.data.get('amount_to_import', 'all')

        if (login_url == ""):
            print("ADD LOGIN URL TO BACKEND ENV FILE")
            return Response({'error': 'Scholar Inbox login URL not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        papers_dict = loop.run_until_complete(fetch_scholar_inbox_papers(login_url, amount_to_import))
        loop.close()

        if (papers_dict is None) or (len(papers_dict) == 0):    
            return Response({'message': 'No new papers found in Scholar Inbox.'}, status=status.HTTP_200_OK)

        # Writing papers to "Scholar Inbox" folder
        # Making sure that a "Scholar Inbox" folder exists
        folder, created = models.Folder.objects.get_or_create(name="Scholar Inbox")
        folder_pk = folder.pk

        for paper in papers_dict: 
            pdf_content = paper.get('pdf_content', None)
            title = paper.get('title', 'Untitled Paper')

            if pdf_content is None:
                print(f"Skipping {title} due to missing PDF content.")
                continue

            pdf_file = InMemoryUploadedFile(
                file=io.BytesIO(pdf_content),
                field_name='file',
                name=f"{title}.pdf",
                content_type='application/pdf',
                size=len(pdf_content),
                charset=None
            )

            data = {
                'file': pdf_file, 
                'title': title, 
                'folder': folder_pk 
            }
            
            try:
                serializer = serializers.DocumentSerializer(data=data)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            except Exception as e: 
                print(f"Issue with saving Scholar Inbox pdf file to storage: {e}")
                print("Skipping this file for now.")
                continue
        
        return Response({'message': 'Papers fetched'}, status=status.HTTP_200_OK)

"""
Knowledge Index idea dump: (hopefully this should help anyone reading this understand my thoughts about the knowledge index so that you can tweak however you like)

Three main functions: 
1. Search notes (easiest)
2. AI features (medium)
3. Vector graph of relations between ideas (hardest)

Search
View that returns necessary info for knowledge index search

output format: 

document_title: {
    highlight data: {
        page, 
        text,
    },
    notepad, 
    stickynote data : {
        page, 
        content,
        tag, 
    }
}
"""

# Gets notes so that user can search on the frontend.
class SearchNotesView(APIView):
    def get(request, self, format=None): 
        documents = models.Document.objects.filter(
        annotations__in = models.Annotations.objects.filter(
            Q(highlight_data__isnull = False) | 
            Q(sticky_note_data__isnull = False) 
        )
        ).distinct()

        serializer = serializers.GroupedAnnotationsSerializer(documents, many=True)

        final_data = []
        for item in serializer.data:
            title = item.pop('document__title')
            doc_id = item.pop('document__pk')
            annotations = item['annotations'][0]
            final_data.append(
                dict(
                    title=title,
                    doc_id=doc_id, 
                    annotations=annotations
                )
            )
            
            
        return Response(final_data)
        
"""
AI features: 
Using gemini API. I may add OpenAI and Claude later, but I'm sure that it would be very easy to switch out the model provider.
    - just look for the "send_prompt" function in ai.py and just modify it to send to whatever API you like
- RAG + Context Engineering should work the same since everything's being appended to the prompt.
- Actual model choice/thinking budget can be configured in user_preferences either thru frontend UI or thru messing with the JSON file
- Default will be Gemini 3 Flash, since it's cheap.

Save chat logs and build out UI interface to present them.

frontend functionality: 
- The view will be equipped to handle pdfs.
- @paper:<paper-title> will send the paper pdf as well as any annotations to the model 
    - Multiple papers can be send for cross comparisons between the two 
- @recent: sends recent annotations (up to a certain amount of data) to the model for summary and analysis of key points
-@folder: sends the whole folder context, but doesn't send pdfs

- only one of these at a time
- make rag enabled false if one of these are typed since this already provides necessary context

- Minize hallucinations thru prompting the LLM for citations in the system prompt.

note to self: implement Latex and markdown

Button where user can pick whether they want to use RAG or not.
Rag will get top 2-3 embeddings with n cos similarity and append them to the prompt as context.
"""
# TODO: Implement chat log saving

from .ai import send_prompt
class AIChatView(APIView): 
    def post(self, request, format=None):
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key: 
            return Response({"error": "Gemini API key not set. See docs."}, status=status.HTTP_400_BAD_REQUEST)
        
        gemini_model = os.getenv("GEMINI_MODEL")
        if not gemini_model: 
            return Response({"error": "Gemini model not set. See docs."}, status=status.HTTP_400_BAD_REQUEST)
        
        prompt = request.get("prompt", "")
        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # handling context injections w/ @paper and @recent, etc.
        # plan is to append a contxt block to the prompt var
        # getting flags
        context_template = """The following section contains the raw research annotations retrieved from the user's library. This data is the "Source of Truth" for the current conversation. 

        - USE this data to answer queries accurately.
        - PRIORITIZE the information in this block over your general pre-trained knowledge.
        - IF the data is insufficient to answer a question, explicitly state what is missing.
        - Refer to papers by their titles.

        --- DATA START ---
        {annot_data}
        --- DATA END ---"""
        context_block = ""

        at_recent = to_bool(request.get("at_recent", False))
        paper_ids = request.getlist("paper_ids", None)
        folder_ids = request.getlist("folder_ids", None)
        rag_enabled = to_bool(request.get("rag_enabled", False))

        # handling flags

        # making sure that only one flag is set
        paper_id_bool = (paper_ids != None and paper_ids != [])
        folder_id_bool = (folder_ids != None and folder_ids != [])
        
        true_count = at_recent + paper_id_bool + folder_id_bool + rag_enabled
        if true_count > 1: 
            return Response({"error": "You can only have one unique context flag, i.e. you cannot do @recent and @paper in the same prompt, but two @paper calls are allowed."}, status=status.HTTP_400_BAD_REQUEST)

        # handles @recent
        if at_recent: # gets annotations that are a week old or less and pass to model
            one_week_ago = timezone.now() - timedelta(days=7)
            recent_data = models.Document.objects.filter(
                annotations__in = models.Annotations.objects.filter(updated_at__gte=one_week_ago)
            )
            serializer = serializers.GroupedAnnotationsSerializer(recent_data, many=True)
            annot_data = serializer.data
            try: 
                annot_data = json.dumps(annot_data)
            except Exception as e: 
                print(f"error with converting @recent data to JSON {e}")
                pass

            context_block = context_template.format(annot_data=annot_data)
            prompt += "\n\n" + context_block    
            print(prompt) # delete later

            model_response = send_prompt(
                gemini_key = gemini_key, 
                model = gemini_model, 
                prompt = prompt)

            return Response({"model_response": model_response}, status=status.HTTP_200_OK)

        # handles @paper
        elif paper_ids != None:
            papers = models.Document.objects.filter(pk__in = paper_ids)
            pdf_paths = [Path(p.file.path) for p in papers if p.file]

            # Getting annotations
            annot_serializer = serializers.GroupedAnnotationsSerializer(papers, many=True)
            annot_data = annot_serializer.data
            try: 
                annot_data = json.dumps(annot_data)
            except Exception as e: 
                print(f"error with converting @paper data to JSON {e}")
                pass

            context_block = context_template.format(annot_data=annot_data)
            prompt += "\n\n" + context_block    
            print(prompt) # delete later

            model_response = send_prompt(
                gemini_key = gemini_key, 
                model = gemini_model, 
                prompt = prompt, 
                pdf_count=len(pdf_paths), 
                pdf_paths = pdf_paths
                )
            
            return Response({"model_response": model_response}, status=status.HTTP_200_OK)
            

        # handles @folder, doesn't send any paper pdfs
        elif folder_ids != None:
            # get all necessary data (all 3 layers)
            folders = models.Folder.objects.filter(pk__in = folder_ids).prefetch_related(
            'documents', 
            'documents__annotations'
        )
            
            """
            creating an organized context dict. for model
            struct looks like .
            folder1 : {
                doc1 : {
                    annotations
                },
                doc2 : {
                    annotations
                },
            }, etc.
            """
            folder_context = {}
            for folder in folders: 
                folder_context[folder.name] = {}
                folder_id = folder.id # type: ignore
                papers = models.Document.objects.filter(folder = folder_id)

                # gets the paper titles and annotations in an easy to understand structure for model
                annot_serializer = serializers.GroupedAnnotationsSerializer(papers, many=True)
                annot_data = annot_serializer.data
                folder_context[folder.name] = annot_data

            try: 
                folder_context = json.dumps(folder_context)
            except Exception as e: 
                print(f"error with converting @folder data to JSON {e}")
                pass

            if folder_context != {} and folder_context != None: 
                context_block = context_template.format(annot_data=folder_context)
                prompt += "\n\n" + context_block    
                print(prompt) # delete later

                model_response = send_prompt(
                    gemini_key = gemini_key, 
                    model = gemini_model, 
                    prompt = prompt, 
                    )
                
                return Response({"model_response": model_response}, status=status.HTTP_200_OK)
            
            else: 
                print("No folder context, some error in AIChatView most likely")
                return Response({"error": "Model pipeline failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # running rag if enabled
        elif rag_enabled != None:
            pass

        # running normal model if not context or no rag 
        else: 
            pass

        # fallback response
        return Response({"error": "Model pipeline failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                


"""
Smart Collections feature notes (sorry these notes are a bit of a mess)

Ideas: 

Vector embed each level of the graph 
- Major topics
- Subtopics 
- Annotations

send annotations that are very similar (cos similarity) to AI (or pick some K nearest group)
- Have some checks for top 0.95, if not enough groups keep going down.
- Maybe let the user configure some settings, i.e. similarity or group count or you can just let them say "optimize" 

- Ask it to return JSON of 1 major topic (this will represent the entire embedded notes)
- Also return subtopics

Zoom takes you to down level, i.e. zooming takes you from major topics to subtopics

Layout stability layer to preserve spatial consistency across updates.

Plot the graph.
- Project n-dim vector embedding down to 2D with UMAP lib
- Without zoom, major topics should appear, i.e. ML and Quantum Computing (heading)
- As someone zooms in to a particular topic, subtopics appear and as they zoom in more you can see subtopics and paper titles. 
- Should also see some ideas from notes or highlights
- Linking between ideas should exist 
- Cluster boundaries
- Cross domain insights
     - Highlight connector lines
- Generate insights of what ideas could connect with each other (AI model)
    - i.e. what fields could the user possibly be interested in
- Have a couple of sidebar tabs, one with an AI chat, one with recommendations, one with text listing and such 
- LLM summaries generated per cluster 

Graph plotting specifics: 
- project vectors to 2d and let everything graph itself

Extra feature idea: backwards relationships: 
i.e. given LLM paper, llms come from transformers, transformers come from neural nets, etc.

for sidebar: 
1. AI chat with RAG setup 
2. Explore functionality (gives hierarchy of ideas in text form)
3. Recommendations for new topics to explore (generated by AI)
- based on similar topics and context engineering 
"""
class VectorGraphView(APIView):
    pass


