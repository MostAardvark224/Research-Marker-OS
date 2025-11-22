from django.shortcuts import render
from rest_framework import viewsets
import api.models as models
import api.serializers as serializers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView


# Uploaded PDF List
class DocumentsListView(viewsets.ModelViewSet):
    queryset = models.Document.objects.all()
    serializer_class = serializers.DocumentSerializer


# Upload PDFs (Supports multiple)
class DocumentsUploadView(APIView):  
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist('file')
        uploaded_documents = []

        for file in files:
            document = models.Document(file=file, title=file.name)
            document.size_mb = document.file.size // (1024 * 1024)  # Size in MB
            document.save()
            uploaded_documents.append(document)

        serializer = serializers.DocumentSerializer(uploaded_documents, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
