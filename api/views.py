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

from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from . import models, serializers

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
            
            # Xtra handling for folder assignment
            folder_pk = request.data.get('folder_id', None)

            for file in files:
                data = {
                    'file': file, 
                    'title': file.name.removesuffix(Path(file.name).suffix), 
                    'folder': folder_pk 
                }

                print(data)
                
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
                uploaded_documents.append(serializer.data)

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
