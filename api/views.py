from django.shortcuts import render
from rest_framework import viewsets
import api.models as models
import api.serializers as serializers
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
import os
from pathlib import Path
from django.http import Http404, FileResponse
import time
from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from . import models, serializers
from .OCR import create_searchable_pdf
from .user_preferences import load_user_preferences, write_user_preferences

import asyncio
import aiohttp
from .scholar_inbox import fetch_scholar_inbox_papers
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
import io

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
            
            serializer = serializers.DocumentSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()



