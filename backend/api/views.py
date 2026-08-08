# pyright: reportAttributeAccessIssue=false

import json
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

import requests
from django.core.files import File
from django.db.models import Q, Max
from django.http import FileResponse
from django.utils.text import get_valid_filename
from django.utils import timezone
from django_q.tasks import async_task
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
    extract_pdf_pages,
    get_all_provider_models,
    get_provider_api_key,
    get_provider_base_url,
    name_chat,
    normalize_page_numbers,
    normalize_provider,
    rag_context_injection,
    send_prompt,
)
from api.scholar_inbox import ScholarInboxError
from api.scholar_inbox_import import import_scholar_inbox_papers
from api.smart_collections.config import get_smart_collection_config
from api.smart_collections.service import (
    reconcile_stale_job,
    regenerate_recommendations,
    safe_failure,
    serialize_job,
)
from api.smart_collections.tasks import queue_smart_collection_job
from api.startup_scripts import get_startup_scripts_status, sanitize_startup_script_paths
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


def _queue_context_ingestion(document):
    if document.context_status in ("queued", "processing"):
        return
    document.context_status = "queued"
    document.context_error = ""
    document.save(update_fields=["context_status", "context_error"])
    async_task("api.paper_context.ingestion.ingest_document", document.pk)


def _apply_ocr_settings_to_document(document, skip_ocr, ocr_provider):
    if skip_ocr:
        document.ocr_provider = ocr_provider
        document.ocr_status = models.Document.OcrStatus.NOT_STARTED
        document.ocr_error = ""
        document.save(update_fields=["ocr_provider", "ocr_status", "ocr_error"])
        _queue_context_ingestion(document)
        return

    document.ocr_provider = ocr_provider
    document.ocr_status = models.Document.OcrStatus.QUEUED
    document.ocr_error = ""
    document.context_status = "waiting_for_ocr"
    document.save(
        update_fields=["ocr_provider", "ocr_status", "ocr_error", "context_status"]
    )
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
                    serializer.instance.context_status = "waiting_for_ocr"
                    serializer.instance.save(
                        update_fields=[
                            "ocr_provider",
                            "ocr_status",
                            "ocr_error",
                            "context_status",
                        ]
                    )
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
                    _queue_context_ingestion(serializer.instance)

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

        if (
            document.context_status not in ("ready", "queued", "processing", "waiting_for_ocr")
            and document.ocr_status
            not in (models.Document.OcrStatus.QUEUED, models.Document.OcrStatus.PROCESSING)
        ):
            _queue_context_ingestion(document)

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
        if not isinstance(preferences, dict):
            return Response(
                {'message': 'preferences must be an object.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_prefs = preferences.get('user_preferences')
        if isinstance(user_prefs, dict):
            general = user_prefs.get('general')
            if isinstance(general, dict) and 'startup_scripts' in general:
                cleaned, errors = sanitize_startup_script_paths(general.get('startup_scripts'))
                if errors:
                    return Response(
                        {
                            'message': 'One or more startup script paths are invalid.',
                            'errors': errors,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                general['startup_scripts'] = cleaned
                user_prefs['general'] = general
                preferences['user_preferences'] = user_prefs

        write_user_preferences(preferences)
        return Response({'message': 'Preferences updated successfully.'}, status=status.HTTP_200_OK)


class StartupScriptsStatusView(APIView):
    def get(self, request):
        return Response(get_startup_scripts_status(), status=status.HTTP_200_OK)
    
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
        providers = list(get_all_provider_models(load_env_vars(), force_refresh=force_refresh))
        from api.providers.codex import get_codex_provider

        codex_status = get_codex_provider().get_status()
        codex_models: list[str] = []
        codex_default = ""
        if codex_status.get("subscription_usable"):
            try:
                catalog = get_codex_provider().models()
                codex_models = [item["id"] for item in catalog]
                defaults = [item["id"] for item in catalog if item.get("is_default")]
                codex_default = defaults[0] if defaults else (codex_models[0] if codex_models else "")
            except Exception:
                codex_models = []
        providers.append(
            {
                "id": "codex",
                "label": "Codex — ChatGPT account",
                "models": codex_models,
                "default_chat_model": codex_default,
                "default_naming_model": codex_default,
                "has_api_key": False,
                "ready": bool(codex_status.get("subscription_usable")),
                "status": codex_status,
                "capabilities": {
                    "embedded_chat": True,
                    "requires_active_document": True,
                    "streaming": True,
                    "subscription_auth": True,
                    "smart_collection_labels": True,
                },
                "error": None,
            }
        )
        from api.providers.embeddings import embedding_provider_catalog

        return Response(
            {
                "providers": providers,
                "embedding_providers": embedding_provider_catalog(load_env_vars()),
            },
            status=status.HTTP_200_OK,
        )


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
        document.context_status = "waiting_for_ocr"
        document.save(
            update_fields=[
                "ocr_provider",
                "ocr_status",
                "ocr_error",
                "searchable",
                "ocr_started_at",
                "ocr_completed_at",
                "context_status",
            ]
        )

        async_task("api.OCR.create_searchable_document_pdf", document.pk, provider, model)
        return Response(
            {"message": "OCR queued.", "document": serializers.DocumentSerializer(document).data},
            status=status.HTTP_202_ACCEPTED,
        )


# Runs fetch from scholar inbox and uploads papers to "Scholar Inbox" folder
class FetchScholarInboxPapers(APIView):
    def post(self, request):
        amount_to_import = request.data.get("amount_to_import", "All")
        skip_ocr = to_bool(request.data.get("skip_ocr", "true"))
        ocr_provider = normalize_ocr_provider(
            request.data.get("ocr_provider", "paddleocr")
        )

        try:
            result = import_scholar_inbox_papers(
                amount_to_import,
                skip_ocr=skip_ocr,
                ocr_provider=ocr_provider,
            )
        except ScholarInboxError as exc:
            print(f"Scholar Inbox fetch failed ({exc.code}): {exc.message}")
            return Response(
                {
                    "error": exc.message,
                    "code": exc.code,
                    "imported": 0,
                    "skipped": 0,
                },
                status=exc.http_status,
            )
        except Exception as exc:
            print(f"Scholar Inbox fetch crashed: {exc}")
            return Response(
                {
                    "error": f"Scholar Inbox import failed: {exc}",
                    "code": "unexpected_error",
                    "imported": 0,
                    "skipped": 0,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        payload = {
            "message": result.get("message"),
            "imported": result.get("imported", 0),
            "skipped": result.get("skipped", 0),
            "unmatched": result.get("unmatched", 0),
            "digest_found": result.get("digest_found", False),
            "titles_found": result.get("titles_found", 0),
        }
        if result.get("unmatched_titles"):
            payload["unmatched_titles"] = result["unmatched_titles"]
        if result.get("errors"):
            payload["errors"] = result["errors"]

        return Response(payload, status=status.HTTP_200_OK)

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
            Q(sticky_note_data__isnull = False) |
            Q(notepad__isnull = False)
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
        original_prompt = prompt
        paper_context = None
        document_id = request.data.get("document_id")
        if document_id:
            from api.errors import ResearchMarkerError
            from api.paper_context.builder import build_paper_context, format_paper_context
            from api.paper_context.types import ContextLimits

            try:
                paper_context = build_paper_context(
                    document_id=int(document_id),
                    question=original_prompt,
                    current_page=(
                        int(request.data.get("current_page"))
                        if request.data.get("current_page") not in (None, "")
                        else None
                    ),
                    selected_text=str(request.data.get("selected_text", "")),
                    selected_text_page=(
                        int(request.data.get("selected_text_page"))
                        if request.data.get("selected_text_page") not in (None, "")
                        else None
                    ),
                    include_page_image=to_bool(request.data.get("include_page_image", False)),
                    limits=ContextLimits(),
                )
                prompt = format_paper_context(paper_context)
            except ResearchMarkerError as exc:
                return Response(exc.as_dict(), status=exc.http_status)
        
        # Saving chat logs
        chat_id = request.data.get("chat_id", None)
        chatlog_obj = None

        # means that this is a new chat
        if not chat_id:
            # using a model to create a new chat name based on input prompt
            chat_name = name_chat(provider, api_key, original_prompt, model=model)
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
        paper_ids = None if paper_context is not None else request.data.get("paper_ids", None)
        print(f"paper_ids: {paper_ids}")
        folder_ids = request.data.get("folder_ids", None)
        print(f"folder_ids: {folder_ids}")
        rag_enabled = False if paper_context is not None else to_bool(request.data.get("rag_enabled", False))
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
            add_message_to_chat(chat_id, "user", original_prompt)

            # Save and return model response
            add_message_to_chat(chat_id, "model", model_response)
            return Response({
                "model_response": model_response, 
                "chat_id": chat_id, 
                "chat_name": chatlog_obj.name},  
            status=status.HTTP_200_OK)

        # handles @paper (full PDF) and @page (single-page PDF via pages=[...])
        elif paper_ids:
            papers = models.Document.objects.filter(pk__in = paper_ids)
            pdf_paths = [Path(p.file.path) for p in papers if p.file]
            pages = normalize_page_numbers(request.data.get("pages", None))

            temp_dir = None
            try:
                if pages:
                    temp_dir = tempfile.mkdtemp(prefix="ai_page_pdf_")
                    page_pdf_paths = extract_pdf_pages(pdf_paths, pages, temp_dir)
                    if not page_pdf_paths:
                        return Response(
                            {"error": f"Could not extract requested page(s): {pages}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    pdf_paths = page_pdf_paths
                    page_label = ", ".join(str(p) for p in pages)
                    print(
                        "AIChatView @page extracted PDFs: "
                        + ", ".join(f"{p.name}={p.stat().st_size}B" for p in pdf_paths)
                    )
                    new_prompt = (
                        prompt
                        + f"\n\n[Attached PDF page(s): {page_label}. "
                        "A real application/pdf file attachment for these page(s) is included "
                        "in this request (not plain text).]"
                    )
                else:
                    # Getting annotations for full-paper context
                    annot_serializer = serializers.GroupedAnnotationsSerializer(papers, many=True)
                    annot_data = annot_serializer.data
                    try:
                        annot_data = json.dumps(annot_data)
                    except Exception as e:
                        print(f"error with converting @paper data to JSON {e}")
                        pass

                    context_block = context_template.format(annot_data=annot_data)
                    new_prompt = prompt + "\n\n" + context_block

                model_response = send_prompt(
                    provider = provider,
                    api_key = api_key,
                    model = model,
                    prompt = new_prompt,
                    pdf_count=len(pdf_paths),
                    pdf_paths = pdf_paths,
                    chat_id = chat_id
                    )
            finally:
                if temp_dir:
                    shutil.rmtree(temp_dir, ignore_errors=True)

            # saving prompt to chatlogs (only original user question)
            add_message_to_chat(chat_id, "user", original_prompt)

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
                add_message_to_chat(chat_id, "user", original_prompt)

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
            add_message_to_chat(chat_id, "user", original_prompt)

            # Save and return model response
            citation_data = []
            if paper_context is not None:
                from api.paper_context.citations import extract_citations

                allowed_pages = {
                    page.page_number for page in paper_context.page_text
                } | {
                    page
                    for chunk in paper_context.retrieved_chunks
                    for page in range(chunk.start_page, chunk.end_page + 1)
                }
                citation_data = [
                    citation.to_dict()
                    for citation in extract_citations(
                        model_response,
                        document_id=paper_context.document_id,
                        allowed_pages=allowed_pages,
                    )
                ]
            add_message_to_chat(chat_id, "model", model_response, citations=citation_data)
            return Response({
                    "model_response": model_response, 
                    "chat_id": chat_id, 
                    "chat_name": chatlog_obj.name,
                    "citations": citation_data},
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
            add_message_to_chat(chat_id, "user", original_prompt)

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
    def post(self, request):
        active = models.SmartCollectionJob.objects.filter(
            status__in=[
                models.SmartCollectionJob.Status.QUEUED,
                models.SmartCollectionJob.Status.RUNNING,
            ]
        ).first()
        if active:
            active = reconcile_stale_job(active)
            if active.status in (
                models.SmartCollectionJob.Status.QUEUED,
                models.SmartCollectionJob.Status.RUNNING,
            ):
                return Response(
                    {
                        "message": "A Smart Collection update is already running.",
                        "job": serialize_job(active),
                        "already_running": True,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
        if not models.Annotations.objects.exists():
            return Response(
                {
                    "error": "no_annotations",
                    "message": (
                        "Add notes or annotations to at least one paper before "
                        "building a Smart Collection."
                    ),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        try:
            config = get_smart_collection_config(
                embedding_provider=request.data.get("embedding_provider"),
                embedding_model=request.data.get("embedding_model"),
                generation_provider=request.data.get("generation_provider"),
                generation_model=request.data.get("generation_model"),
            )
        except Exception as exc:
            code, message = safe_failure(exc, "preflight")
            return Response(
                {"error": code, "message": message},
                status=getattr(exc, "http_status", status.HTTP_400_BAD_REQUEST),
            )
        job = models.SmartCollectionJob.objects.create(
            embedding_provider=config.embedding.provider,
            embedding_model=config.embedding.model,
            embedding_dimensions=config.embedding.dimensions,
            generation_provider=config.generation_provider,
            generation_model=config.generation_model,
            total_items=models.Annotations.objects.count(),
        )
        try:
            task_id = queue_smart_collection_job(str(job.id))
        except Exception as exc:
            code, message = safe_failure(exc, "queueing")
            job.status = models.SmartCollectionJob.Status.FAILED
            job.stage = "queued"
            job.error_code = code
            job.error_message = (
                f"{message} Ensure the django-q worker is running on this host."
            )[:1000]
            job.finished_at = timezone.now()
            job.save()
            return Response(
                {
                    "error": code,
                    "message": job.error_message,
                    "job": serialize_job(job),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        job.task_id = task_id
        job.save(update_fields=["task_id", "updated_at"])
        return Response(
            {
                "message": "Smart Collection initialization started.",
                "job": serialize_job(job),
                "task_id": task_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )
    
    
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
        active = models.SmartCollectionJob.objects.filter(
            status__in=[
                models.SmartCollectionJob.Status.QUEUED,
                models.SmartCollectionJob.Status.RUNNING,
            ]
        ).first()
        if active:
            active = reconcile_stale_job(active)
        smart_collection = models.SmartCollections.objects.first()
        if smart_collection and smart_collection.is_ready:
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

                return Response(
                    {
                        "data": data,
                        "colors": colors or {},
                        "recommendations": smart_collection.reading_recommendations or {},
                        "active_job": serialize_job(active) if active else None,
                    },
                    status=status.HTTP_200_OK,
                )
        return Response(
            {
                "data": [],
                "colors": {},
                "recommendations": {},
                "active_job": serialize_job(active) if active else None,
            },
            status=status.HTTP_200_OK,
        )

# polling view so that frontend can track status of collection creation
class PollSmartCollection(APIView):
    def get(self, request, task_id):
        if task_id == "null" or not task_id:
            return Response({"state": "no_task", "job": None})
        job = models.SmartCollectionJob.objects.filter(task_id=task_id).first()
        if job is None:
            try:
                job = models.SmartCollectionJob.objects.get(pk=task_id)
            except (models.SmartCollectionJob.DoesNotExist, ValueError):
                return Response(
                    {
                        "state": "not_found",
                        "job": None,
                        "message": "This Smart Collection job no longer exists.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
        job = reconcile_stale_job(job)
        state_map = {
            models.SmartCollectionJob.Status.QUEUED: "queued",
            models.SmartCollectionJob.Status.RUNNING: "running",
            models.SmartCollectionJob.Status.COMPLETED: "success",
            models.SmartCollectionJob.Status.FAILED: "failed",
            models.SmartCollectionJob.Status.CANCELLED: "cancelled",
        }
        return Response({"state": state_map[job.status], "job": serialize_job(job)})


class SmartCollectionJobView(APIView):
    def get(self, request, job_id):
        try:
            job = models.SmartCollectionJob.objects.get(pk=job_id)
        except models.SmartCollectionJob.DoesNotExist:
            return Response(
                {"error": "job_not_found", "message": "Smart Collection job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"job": serialize_job(reconcile_stale_job(job))})

    def delete(self, request, job_id):
        try:
            job = models.SmartCollectionJob.objects.get(pk=job_id)
        except models.SmartCollectionJob.DoesNotExist:
            return Response(
                {"error": "job_not_found", "message": "Smart Collection job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if job.status not in (
            models.SmartCollectionJob.Status.QUEUED,
            models.SmartCollectionJob.Status.RUNNING,
        ):
            return Response({"job": serialize_job(job)})
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested", "updated_at"])
        return Response({"job": serialize_job(job)}, status=status.HTTP_202_ACCEPTED)


class ReadingRecommendationsView(APIView):
    def get(self, request): 
        
        sc_obj = models.SmartCollections.objects.first() 
        if not sc_obj:
            return Response({"recommendations": {}}, status=status.HTTP_200_OK)
            
        recs = sc_obj.reading_recommendations # already in JSON

        if not recs:
            return Response({"recommendations": {}}, status=status.HTTP_200_OK)
        
        # NOTE to self: format display on frontend

        return Response({"recommendations": recs}, status=status.HTTP_200_OK)
    
    # regeneration in case user doesn't like or something goes wrong
    def post(self, request): 
        try:
            recs = regenerate_recommendations(get_smart_collection_config())
            return Response({"recommendations": recs}, status=status.HTTP_200_OK)
        except Exception as exc:
            code, message = safe_failure(exc, "recommendations")
            return Response(
                {"error": code, "message": message},
                status=getattr(exc, "http_status", status.HTTP_502_BAD_GATEWAY),
            )
