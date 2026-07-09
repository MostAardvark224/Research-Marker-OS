# pyright: reportAttributeAccessIssue=false

import asyncio
import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path

import requests
from django.core.files import File
from django.db.models import Q, Max
from django.http import FileResponse
from django.utils.text import get_valid_filename
from django.utils import timezone
from django_q.tasks import async_task, fetch
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api import models, serializers
from api.arxiv import fetch_arxiv_metadata, parse_arxiv_id
from api.OCR import OCRError, get_ocr_providers, normalize_ocr_provider
from api.ai import (
    AI_PROVIDER_CONFIG,
    add_message_to_chat,
    generate_reading_recommendations,
    get_all_provider_models,
    get_provider_api_key,
    get_provider_base_url,
    name_chat,
    normalize_provider,
    rag_context_injection,
    send_prompt,
)
from api.scholar_inbox import fetch_scholar_inbox_papers
from api.user_preferences import deep_get, load_user_preferences, write_user_preferences
from api.utils import (
    get_env_vars_potential_list,
    intitial_env_vars_data,
    load_env_vars,
    write_env_vars,
)

MAX_SCHOLAR_PDF_BYTES = 100 * 1024 * 1024

# to bool helper method for flag parsing
def to_bool(value):
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ('yes', 'true', 't', 'y', '1', 'on'):
            return True
        if normalized in ('no', 'false', 'f', 'n', '0', 'off', None):
            return False
            
    return bool(value) # fallback

def _next_document_sort_order(folder_id):
    max_order = models.Document.objects.filter(folder_id=folder_id).aggregate(
        Max("sort_order")
    )["sort_order__max"]
    return (max_order if max_order is not None else -1) + 1

def _next_folder_sort_order(parent_id):
    max_order = models.Folder.objects.filter(parent_id=parent_id).aggregate(
        Max("sort_order")
    )["sort_order__max"]
    return (max_order if max_order is not None else -1) + 1


def _stream_pdf_to_document(pdf_url, title, folder):
    temp_path = None
    safe_filename = get_valid_filename(f"{title}.pdf") or "paper.pdf"

    try:
        with requests.get(
            pdf_url,
            stream=True,
            timeout=(10, 120),
            headers={"User-Agent": "Research-Marker-OS/1.0"},
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_SCHOLAR_PDF_BYTES:
                raise ValueError(f"PDF is larger than {MAX_SCHOLAR_PDF_BYTES} bytes")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_path = temp_file.name
                bytes_written = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        bytes_written += len(chunk)
                        if bytes_written > MAX_SCHOLAR_PDF_BYTES:
                            raise ValueError(f"PDF exceeded {MAX_SCHOLAR_PDF_BYTES} bytes")
                        temp_file.write(chunk)

        folder_id = folder.pk if folder else None
        document = models.Document(
            title=title,
            folder=folder,
            sort_order=_next_document_sort_order(folder_id),
        )

        with open(temp_path, "rb") as file_handle:
            document.file.save(safe_filename, File(file_handle), save=True)

        return document
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _apply_ocr_settings_to_document(document, skip_ocr, ocr_provider):
    if skip_ocr:
        document.ocr_provider = ocr_provider
        document.ocr_status = models.Document.OcrStatus.NOT_STARTED
        document.ocr_error = ""
        document.save(update_fields=["ocr_provider", "ocr_status", "ocr_error"])
        return

    document.ocr_provider = ocr_provider
    document.ocr_status = models.Document.OcrStatus.QUEUED
    document.ocr_error = ""
    document.save(update_fields=["ocr_provider", "ocr_status", "ocr_error"])
    async_task(
        "api.OCR.create_searchable_document_pdf",
        document.pk,
        ocr_provider,
    )


class ArxivPaperMetadataView(APIView):
    def post(self, request):
        arxiv_input = request.data.get("arxiv_url") or request.data.get("arxiv_id")
        arxiv_id = parse_arxiv_id(str(arxiv_input or ""))

        if not arxiv_id:
            return Response(
                {"error": "Could not parse a valid arXiv link or ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            metadata = fetch_arxiv_metadata(arxiv_id)
        except Exception as exc:
            print(f"Failed to fetch arXiv metadata for {arxiv_id}: {exc}")
            return Response(
                {"error": "Failed to fetch paper metadata from arXiv."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not metadata:
            return Response(
                {"error": "No paper found for that arXiv link."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(metadata, status=status.HTTP_200_OK)


class ImportArxivPaperView(APIView):
    def post(self, request):
        arxiv_input = request.data.get("arxiv_url") or request.data.get("arxiv_id")
        arxiv_id = parse_arxiv_id(str(arxiv_input or ""))

        if not arxiv_id:
            return Response(
                {"error": "Could not parse a valid arXiv link or ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        skip_ocr = to_bool(request.data.get("skip_ocr", "true"))
        ocr_provider = normalize_ocr_provider(request.data.get("ocr_provider", "paddleocr"))

        if not skip_ocr:
            provider_config = next(
                (item for item in get_ocr_providers(load_env_vars()) if item["id"] == ocr_provider),
                None,
            )
            if provider_config and provider_config["kind"] == "byok" and not provider_config["has_api_key"]:
                return Response(
                    {"error": f"{provider_config['label']} API key is not configured in Settings."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            metadata = fetch_arxiv_metadata(arxiv_id)
        except Exception as exc:
            print(f"Failed to fetch arXiv metadata for {arxiv_id}: {exc}")
            return Response(
                {"error": "Failed to fetch paper metadata from arXiv."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not metadata or not metadata.get("pdf_url"):
            return Response(
                {"error": "No paper found for that arXiv link."},
                status=status.HTTP_404_NOT_FOUND,
            )

        use_arxiv_title = to_bool(request.data.get("use_arxiv_title", "false"))
        custom_title = str(request.data.get("title", "")).strip()
        title = metadata["title"] if use_arxiv_title or not custom_title else custom_title

        if not title:
            return Response(
                {"error": "A paper title is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder = None
        folder_id = request.data.get("folder_id")
        if folder_id not in (None, "", "null", "undefined"):
            try:
                folder = models.Folder.objects.get(pk=folder_id)
            except models.Folder.DoesNotExist:
                return Response(
                    {"error": "Selected folder was not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            document = _stream_pdf_to_document(metadata["pdf_url"], title, folder)
        except Exception as exc:
            print(f"Failed to import arXiv paper {arxiv_id}: {exc}")
            return Response(
                {"error": "Failed to download or save the arXiv PDF."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        _apply_ocr_settings_to_document(document, skip_ocr, ocr_provider)

        serializer = serializers.DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# View that returns folders, documents are nested within.
class CompleteFetch(APIView):
    def get(self, request, format=None):
        root_folders = models.Folder.objects.filter(parent__isnull=True).order_by(
            "sort_order", "name"
        )
        folder_serializer = serializers.FolderSerializer(root_folders, many=True)

        unassigned_docs = models.Document.objects.filter(folder__isnull=True).order_by(
            "sort_order", "id"
        )
        unassigned_serializer = serializers.DocumentSerializer(unassigned_docs, many=True)

        return Response({
            'folders': folder_serializer.data,
            'Unassigned': unassigned_serializer.data
        }, status=status.HTTP_200_OK)

# View that handles all document-related operations
class DocumentsViewSet(viewsets.ModelViewSet):
    queryset = models.Document.objects.all()
    serializer_class = serializers.DocumentSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        files = request.FILES.getlist('file')

        if files:
            uploaded_documents = []

            skip_ocr = request.data.get("skip_ocr", "false").lower() == "true"
            ocr_provider = normalize_ocr_provider(request.data.get("ocr_provider", "paddleocr"))

            if not skip_ocr:
                provider_config = next(
                    (item for item in get_ocr_providers(load_env_vars()) if item["id"] == ocr_provider),
                    None,
                )
                if provider_config and provider_config["kind"] == "byok" and not provider_config["has_api_key"]:
                    return Response(
                        {"error": f"{provider_config['label']} API key is not configured in Settings."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            
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
                    serializer.instance.ocr_provider = ocr_provider
                    serializer.instance.ocr_status = models.Document.OcrStatus.QUEUED
                    serializer.instance.ocr_error = ""
                    serializer.instance.save(update_fields=["ocr_provider", "ocr_status", "ocr_error"])
                    async_task(
                        "api.OCR.create_searchable_document_pdf",
                        serializer.instance.pk,
                        ocr_provider,
                    )
                else:
                    serializer.instance.ocr_provider = ocr_provider
                    serializer.instance.ocr_status = models.Document.OcrStatus.NOT_STARTED
                    serializer.instance.ocr_error = ""
                    serializer.instance.save(update_fields=["ocr_provider", "ocr_status", "ocr_error"])

                uploaded_documents.append(self.get_serializer(serializer.instance).data)

            return Response(uploaded_documents, status=status.HTTP_201_CREATED)

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        folder = serializer.validated_data.get("folder")
        folder_id = folder.pk if folder else None
        serializer.save(sort_order=_next_document_sort_order(folder_id))

    def perform_update(self, serializer):
        instance = serializer.instance
        old_folder_id = instance.folder_id
        folder = serializer.validated_data.get("folder", instance.folder)
        folder_id = folder.pk if folder else None

        extra = {}
        if "folder" in serializer.validated_data and folder_id != old_folder_id:
            extra["sort_order"] = _next_document_sort_order(folder_id)
        serializer.save(**extra)

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

    def perform_create(self, serializer):
        parent = serializer.validated_data.get("parent")
        parent_id = parent.pk if parent else None
        serializer.save(sort_order=_next_folder_sort_order(parent_id))


class ReorderDocumentsView(APIView):
    def post(self, request):
        folder_id = request.data.get("folder_id")
        document_ids = request.data.get("document_ids", [])

        if folder_id in ("", "null", "undefined"):
            folder_id = None

        if not isinstance(document_ids, list) or not document_ids:
            return Response(
                {"error": "document_ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        docs = models.Document.objects.filter(pk__in=document_ids, folder_id=folder_id)
        if docs.count() != len(document_ids):
            return Response(
                {"error": "One or more documents do not belong to this folder."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for index, doc_id in enumerate(document_ids):
            models.Document.objects.filter(pk=doc_id).update(sort_order=index)

        return Response({"message": "Documents reordered."}, status=status.HTTP_200_OK)


class ReorderFoldersView(APIView):
    def post(self, request):
        parent_id = request.data.get("parent_id")
        folder_ids = request.data.get("folder_ids", [])

        if parent_id in ("", "null", "undefined"):
            parent_id = None

        if not isinstance(folder_ids, list) or not folder_ids:
            return Response(
                {"error": "folder_ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folders = models.Folder.objects.filter(pk__in=folder_ids, parent_id=parent_id)
        if folders.count() != len(folder_ids):
            return Response(
                {"error": "One or more folders do not belong to this parent."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for index, folder_id in enumerate(folder_ids):
            models.Folder.objects.filter(pk=folder_id).update(sort_order=index)

        return Response({"message": "Folders reordered."}, status=status.HTTP_200_OK)

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
    
# get/set user prefs
class UserPreferencesView(APIView): 
    def get(self, request): 
        preferences = load_user_preferences()
        return Response(preferences, status=status.HTTP_200_OK)

    def put(self, request): 
        preferences = request.data.get('preferences', {})
        write_user_preferences(preferences)
        return Response({'message': 'Preferences updated successfully.'}, status=status.HTTP_200_OK)
    
# get/set env vars
class EnvironmentVariablesView(APIView): 
    def get(self, request): 
        env_vars = load_env_vars()
        init_data = intitial_env_vars_data()

        # lets the frontend know if it should display the env var setting screen
        exists = any(key not in init_data for key in env_vars) or bool(env_vars.get("exists")) 

        potential_list = get_env_vars_potential_list()
      
        return Response({"exists": exists, "variables": env_vars, "potential_list": potential_list}, status=status.HTTP_200_OK)

    def put(self, request): 
        vars = request.data.get('variables', {})
        write_env_vars(vars)
        get_all_provider_models(load_env_vars(), force_refresh=True)
        return Response({'message': 'Variables updated successfully.'}, status=status.HTTP_200_OK)


class AIModelsView(APIView):
    def get(self, request):
        force_refresh = to_bool(request.query_params.get("refresh", False))
        providers = get_all_provider_models(load_env_vars(), force_refresh=force_refresh)
        return Response({"providers": providers}, status=status.HTTP_200_OK)


class OCRProvidersView(APIView):
    def get(self, request):
        return Response({"providers": get_ocr_providers(load_env_vars())}, status=status.HTTP_200_OK)


class DocumentOCRView(APIView):
    def post(self, request, pk):
        try:
            document = models.Document.objects.get(pk=pk)
        except models.Document.DoesNotExist:
            return Response({"error": "Document not found."}, status=status.HTTP_404_NOT_FOUND)

        if not document.file:
            return Response({"error": "Document has no file to OCR."}, status=status.HTTP_400_BAD_REQUEST)

        if document.ocr_status in (
            models.Document.OcrStatus.QUEUED,
            models.Document.OcrStatus.PROCESSING,
        ):
            return Response(
                {
                    "error": "OCR is already in progress for this document.",
                    "document": serializers.DocumentSerializer(document).data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        provider = normalize_ocr_provider(request.data.get("ocr_provider") or document.ocr_provider)
        model = request.data.get("model") or None

        provider_config = next((item for item in get_ocr_providers(load_env_vars()) if item["id"] == provider), None)
        if not provider_config:
            return Response(
                {"error": f"Unknown OCR provider: {provider}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if provider_config["kind"] == "byok" and not provider_config["has_api_key"]:
            return Response(
                {"error": f"{provider_config['label']} API key is not configured in Settings."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.ocr_provider = provider
        document.ocr_status = models.Document.OcrStatus.QUEUED
        document.ocr_error = ""
        document.searchable = False
        document.ocr_started_at = None
        document.ocr_completed_at = None
        document.save(
            update_fields=[
                "ocr_provider",
                "ocr_status",
                "ocr_error",
                "searchable",
                "ocr_started_at",
                "ocr_completed_at",
            ]
        )

        async_task("api.OCR.create_searchable_document_pdf", document.pk, provider, model)
        return Response(
            {"message": "OCR queued.", "document": serializers.DocumentSerializer(document).data},
            status=status.HTTP_202_ACCEPTED,
        )


# Runs fetch from scholar inbox and uplaods papers to "Scholar Inbox" folder
class FetchScholarInboxPapers(APIView):
    def post(self, request):
        # Running fetch, logic can be altered in scholar_inbox.py
        current_env_vars = load_env_vars()
        amount_to_import = request.data.get('amount_to_import', 'all')

        if not current_env_vars.get("scholar_inbox_email") or not current_env_vars.get("gmail_app_password"):
            print("ADD SCHOLAR INBOX GMAIL CREDENTIALS TO BACKEND ENV FILE")
            return Response({'error': 'Scholar Inbox Gmail credentials not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        papers_dict = loop.run_until_complete(fetch_scholar_inbox_papers(current_env_vars, amount_to_import))
        loop.close()

        if (papers_dict is None) or (len(papers_dict) == 0):    
            return Response(
                {'message': 'No new papers found in Scholar Inbox.', 'imported': 0, 'skipped': 0},
                status=status.HTTP_200_OK,
            )

        # Writing papers to "Scholar Inbox" folder
        # Making sure that a "Scholar Inbox" folder exists
        folder, created = models.Folder.objects.get_or_create(
            name="Scholar Inbox",
            parent=None,
            defaults={"sort_order": 0},
        )

        existing_titles = set(
            models.Document.objects.filter(folder=folder).values_list('title', flat=True)
        )

        imported_count = 0
        skipped_count = 0
        for paper in papers_dict: 
            pdf_url = paper.get('pdf_url', None)
            title = paper.get('title', 'Untitled Paper')

            if not pdf_url:
                print(f"Skipping {title} due to missing PDF URL.")
                skipped_count += 1
                continue

            if title in existing_titles:
                print(f"Skipping duplicate paper: {title}")
                skipped_count += 1
                continue
            
            try:
                _stream_pdf_to_document(pdf_url, title, folder)
                existing_titles.add(title)
                imported_count += 1
            except Exception as e: 
                print(f"Issue with saving Scholar Inbox pdf file to storage: {e}")
                print("Skipping this file for now.")
                skipped_count += 1
                continue
        
        return Response(
            {
                'message': f'Imported {imported_count} paper(s) from Scholar Inbox.',
                'imported': imported_count,
                'skipped': skipped_count,
            },
            status=status.HTTP_200_OK,
        )

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
    def get(self, request, format=None): 
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
class AIChatView(APIView):
    def post(self, request, format=None):
        current_env_vars = load_env_vars()
        current_prefs = load_user_preferences()

        ai_prefs = deep_get(current_prefs, "user_preferences.ai", default={}) or {}
        provider = normalize_provider(
            request.data.get("model_provider")
            or ai_prefs.get("default_provider")
            or "gemini"
        )

        provider_config = AI_PROVIDER_CONFIG[provider]
        preferred_models = ai_prefs.get("models", {}) if isinstance(ai_prefs, dict) else {}
        model = (
            request.data.get("model")
            or preferred_models.get(provider)
            or ai_prefs.get("default_model")
            or deep_get(current_prefs, "GEMINI_MODEL", default=None)
            or provider_config["default_chat_model"]
        )
        if not model:
            return Response({"error": "AI model not set. See Settings."}, status=status.HTTP_400_BAD_REQUEST)

        api_key = get_provider_api_key(provider, current_env_vars)
        if provider == "custom":
            if not get_provider_base_url(provider, current_env_vars):
                return Response(
                    {"error": "Custom server base URL not set. See Settings."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not api_key:
            return Response(
                {"error": f"{provider_config['label']} API key not set. See Settings."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prompt = request.data.get("prompt", "")
        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Saving chat logs
        chat_id = request.data.get("chat_id", None)
        chatlog_obj = None

        # means that this is a new chat
        if not chat_id:
            # using a model to create a new chat name based on input prompt
            chat_name = name_chat(provider, api_key, prompt, model=model)
            chatlog_obj = models.ChatLogs.objects.create(
                name=chat_name,
            )
            chat_id = chatlog_obj.pk
        else: # get existing chatlog model obj
            try:
                chatlog_obj = models.ChatLogs.objects.get(id=chat_id)
            except models.ChatLogs.DoesNotExist:
                return Response({"error": "Chat session not found"}, status=404)   

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

        at_recent = to_bool(request.data.get("at_recent", False))
        print(f"at_recent: {at_recent}")
        paper_ids = request.data.get("paper_ids", None)
        print(f"paper_ids: {paper_ids}")
        folder_ids = request.data.get("folder_ids", None)
        print(f"folder_ids: {folder_ids}")
        rag_enabled = to_bool(request.data.get("rag_enabled", False))
        print(f"rag enabled: {rag_enabled}")

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
            new_prompt = prompt +  "\n\n" + context_block    

            model_response = send_prompt(
                provider = provider,
                api_key = api_key,
                model = model,
                prompt = new_prompt, 
                pdf_count=0, 
                pdf_paths=[],
                chat_id = chat_id
                )

            # saving prompt to chatlogs (only original user question)
            add_message_to_chat(chat_id, "user", prompt) 

            # Save and return model response
            add_message_to_chat(chat_id, "model", model_response)
            return Response({
                "model_response": model_response, 
                "chat_id": chat_id, 
                "chat_name": chatlog_obj.name},  
            status=status.HTTP_200_OK)

        # handles @paper
        elif paper_ids:
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
            new_prompt = prompt +  "\n\n" + context_block    

            model_response = send_prompt(
                provider = provider,
                api_key = api_key,
                model = model,
                prompt = new_prompt, 
                pdf_count=len(pdf_paths), 
                pdf_paths = pdf_paths,
                chat_id = chat_id
                )
            
            # saving prompt to chatlogs (only original user question)
            add_message_to_chat(chat_id, "user", prompt)

            # Save and return model response
            add_message_to_chat(chat_id, "model", model_response)
            return Response({
                "model_response": model_response, 
                "chat_id": chat_id, 
                "chat_name": chatlog_obj.name}, 
            status=status.HTTP_200_OK)
            

        # handles @folder, doesn't send any paper pdfs
        elif folder_ids:
            print("Folder IDs detected, handling @folder context injection")
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
                new_prompt = prompt +  "\n\n" + context_block    

                model_response = send_prompt(
                    provider = provider,
                    api_key = api_key,
                    model = model,
                    prompt = new_prompt, 
                    chat_id = chat_id
                    )
                
                 # saving prompt to chatlogs (only original user question)
                add_message_to_chat(chat_id, "user", prompt)

                # Save and return model response
                add_message_to_chat(chat_id, "model", model_response)
                return Response({
                    "model_response": model_response, 
                    "chat_id": chat_id, 
                    "chat_name": chatlog_obj.name},
                status=status.HTTP_200_OK)
            
            else: 
                print("No folder context, some error in AIChatView most likely")
                return Response({"error": "Model pipeline failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # running rag if enabled
        elif rag_enabled:
            # func takes original prompt, spits out context-injected prompt     
            context = rag_context_injection(prompt)  

            context_block = ""
            if context: 
                context_block = context_template.format(annot_data=context)
                
            new_prompt = prompt + "\n\n" + context_block  


            model_response = send_prompt(
                    provider = provider,
                    api_key = api_key,
                    model = model,
                    prompt = new_prompt, 
                    chat_id = chat_id
                )
            
            # saving prompt to chatlogs (only original user question)
            add_message_to_chat(chat_id, "user", prompt)

            # Save and return model response
            add_message_to_chat(chat_id, "model", model_response)
            return Response({
                    "model_response": model_response, 
                    "chat_id": chat_id, 
                    "chat_name": chatlog_obj.name},  
                status=status.HTTP_200_OK)

        # running normal model if not context or no rag 
        else: 
            model_response = send_prompt(
                    provider = provider,
                    api_key = api_key,
                    model = model,
                    prompt = prompt, 
                    chat_id = chat_id
                )
            
            # saving prompt to chatlogs (only original user question)
            add_message_to_chat(chat_id, "user", prompt)

            # Save and return model response
            add_message_to_chat(chat_id, "model", model_response)
            return Response({
                    "model_response": model_response, 
                    "chat_id": chat_id, 
                    "chat_name": chatlog_obj.name},  
                status=status.HTTP_200_OK)

# Handles all chat logs
class ChatLogsViewset(viewsets.ModelViewSet): 
    queryset = models.ChatLogs.objects.all()
    serializer_class = serializers.ChatLogSerializer


# Note: entierty of smart collection logic is in ai.py file, here Im just running & polling progress & returning finished data
class SmartCollectionView(APIView):
    # Running the smart collection
    def post(self, request):  
        # returns task id immediately, which can then be sent to the frontend for polling
        collection = models.SmartCollections.objects.first()

        if collection:
            # reset existing collection
            collection.is_ready = False
            collection.save()
        else:
            # will create the model obj after the view is done running
            pass

        task_id = async_task(
            'api.ai.run_smart_collection'        
            )

        return Response({
            "message": "Initialization started",
            "task_id": task_id,
        })
    
    
    """
    sending smart collection data for frontend rendering
    format in simple way
    frontend should have to do minimal work to render

    # data will look like this
    [
        {
            id: id, 
            doc_title: doc_title, 
            major_topic: major_topic, 
            sub_topic: sub_topic, 
            x_coordinate: x_coordinate,  
            y_coordinate: y_coordinate, 
        }
    ] 
    - where each dict in the list is the data from the annot obj
    - won't send actual highlight/sticky/notepad data yet as cross-connection ideas hasn't been implemented yet, will def do this in future

    Frontend will need to calculate geometric mean for each cluster, shouldn't be an intensive computation tho
    
    """
    def get(self, request): 
        # small check jsut to make sure that the object exists and tell the client if it doesn't
        smart_collection = models.SmartCollections.objects.first()
        if smart_collection: 
            is_ready = smart_collection.is_ready
            
            if is_ready: 
                list_of_annot_objs = smart_collection.annotation_ids
                annot_objs = models.Annotations.objects.filter(
                    pk__in = list_of_annot_objs
                ).select_related("document")

                data = []

                for obj in annot_objs: 
                    data_dict = dict(
                        id = obj.pk, 
                        doc_title = obj.document.title, 
                        major_topic = obj.major_topic, 
                        sub_topic = obj.sub_topic, 
                        x_coordinate = obj.x_coordinate,
                        y_coordinate = obj.y_coordinate,
                        similar_papers = obj.similar_papers
                    )

                    data.append(data_dict)

                colors = smart_collection.colors

                return Response({"data": data, "colors": colors}, status=status.HTTP_200_OK)

            else: 
                return Response({"error": "data is not ready yet."}, status=status.HTTP_400_BAD_REQUEST)
                
        else: 
            return Response({"error": "smart collection doesn't exist."}, status=status.HTTP_400_BAD_REQUEST)

# polling view so that frontend can track status of collection creation
class PollSmartCollection(APIView):
    def get(self, request, task_id):

        if task_id == "null" or not task_id: 
            return Response({"state": "no task"})


        task = fetch(task_id)  

        if task:
            if task.success: 
                return Response({"state": "success"})
            else: 
                return Response({"state": "failed"})

        else:
            return Response({"state": "queued"})


class ReadingRecommendationsView(APIView):
    def get(self, request): 
        
        sc_obj = models.SmartCollections.objects.first() 
        if not sc_obj: 
            return Response({"error": "failed generating recommendations"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
            
        recs = sc_obj.reading_recommendations # already in JSON

        if not recs: 
            return Response({"error": "failed generating recommendations"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
        
        # NOTE to self: format display on frontend

        return Response({"recommendations": recs}, status=status.HTTP_200_OK)
    
    # regeneration in case user doesn't like or something goes wrong
    def post(self, request): 
        sc_obj = models.SmartCollections.objects.first() 

        if not sc_obj: 
            return Response({"error": "failed generating recommendations"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
        

        if sc_obj.annotation_ids: 
            recs = generate_reading_recommendations(sc_obj.annotation_ids)

            if not recs:
                return Response(
                    {"error": "failed generating recommendations"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            sc_obj.reading_recommendations = recs
            sc_obj.save(
                update_fields=["reading_recommendations"]
            )

            return Response(status=status.HTTP_200_OK)

        else: 
            return Response({"error": "failed generating recommendations"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
