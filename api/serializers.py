import api.models as models
from rest_framework import serializers

# class FolderSerializer(serializers.ModelSerializer):

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Document
        fields = '__all__'


