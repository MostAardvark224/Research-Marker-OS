import api.models as models
from rest_framework import serializers

# class FolderSerializer(serializers.ModelSerializer):

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Document
        fields = '__all__'

class FolderSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True) 

    class Meta:
        model = models.Folder
        fields = ['id', 'name', 'created_at', 'documents']

