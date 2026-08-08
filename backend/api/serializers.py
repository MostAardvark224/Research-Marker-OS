import api.models as models
from rest_framework import serializers
from django.db.models import Q


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Document
        fields = "__all__"


class FolderSerializer(serializers.ModelSerializer):
    documents = serializers.SerializerMethodField()
    subfolders = serializers.SerializerMethodField()

    class Meta:
        model = models.Folder
        fields = [
            "id",
            "name",
            "parent",
            "sort_order",
            "created_at",
            "documents",
            "subfolders",
        ]

    def get_documents(self, folder):
        documents = folder.documents.order_by("sort_order", "id")
        return DocumentSerializer(documents, many=True).data

    def get_subfolders(self, folder):
        children = folder.subfolders.order_by("sort_order", "name")
        return FolderSerializer(children, many=True).data

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        name = attrs.get("name", getattr(self.instance, "name", None))

        if not name:
            return attrs

        qs = models.Folder.objects.filter(name=name, parent=parent)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists at this level."}
            )

        return attrs


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Annotations
        fields = "__all__"


class GroupedAnnotationsSerializer(serializers.ModelSerializer):
    document__title = serializers.CharField(source="title")
    document__pk = serializers.IntegerField(source="pk")

    annotations = serializers.SerializerMethodField()

    class Meta:
        model = models.Document
        fields = ("document__title", "document__pk", "annotations")

    def get_annotations(self, document_instance):
        non_empty_q = (
            Q(highlight_data__isnull=False)
            | Q(sticky_note_data__isnull=False)
            | Q(notepad__isnull=False)
        )

        filtered_annotations = models.Annotations.objects.filter(
            document=document_instance
        ).filter(non_empty_q)

        serializer = AnnotationSerializer(filtered_annotations, many=True)

        return serializer.data


class ChatLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ChatLogs
        fields = "__all__"


class DocumentPageSerializer(serializers.ModelSerializer):
    has_image = serializers.SerializerMethodField()

    class Meta:
        model = models.DocumentPage
        fields = [
            "document",
            "page_number",
            "extracted_text",
            "text_blocks",
            "source_type",
            "ocr_used",
            "ocr_confidence",
            "width",
            "height",
            "rotation",
            "visually_complex",
            "complexity_reasons",
            "extraction_error",
            "has_image",
        ]

    def get_has_image(self, instance):
        return bool(instance.page_image_path)


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DocumentChunk
        fields = [
            "document",
            "chunk_id",
            "start_page",
            "end_page",
            "chunk_text",
            "section_title",
        ]


class SmartCollectionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SmartCollections
        fields = "__all__"
