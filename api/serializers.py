import api.models as models
from rest_framework import serializers
from django.db.models import Q


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

class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Annotations
        fields = '__all__'

class GroupedAnnotationsSerializer(serializers.ModelSerializer): 
    document__title = serializers.CharField(source="title")
    document__pk = serializers.IntegerField(source="pk")

    annotations = serializers.SerializerMethodField()

    class Meta:
        model = models.Document
        fields = ('document__title', 'document__pk', 'annotations')
        
    def get_annotations(self, document_instance):
        non_empty_q = (
            Q(highlight_data__isnull=False) |
            Q(sticky_note_data__isnull=False)
        )

        filtered_annotations = models.Annotations.objects.filter(
            document=document_instance
        ).filter(non_empty_q)
        
        serializer = AnnotationSerializer(filtered_annotations, many=True)
        
        return serializer.data
    
class ChatLogSerializer(serializers.ModelSerializer): 
    class Meta: 
        model = models.ChatLogs
        fields = '__all__'

class SmartCollectionsSerializer(serializers.ModelSerializer): 
    class Meta: 
        model = models.SmartCollections
        fields = '__all__'