from django.db import models
import numpy as np
from django.utils import timezone
import hashlib
import json
from django.db import transaction
import re

class Folder(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        related_name="subfolders",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="unique_folder_name_per_parent",
            ),
        ]

    def __str__(self):
        return self.name

class Document(models.Model):
    class OcrStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    title = models.CharField(max_length=255)
    uploaded_at = models.DateField(auto_now_add=True)
    file = models.FileField(upload_to='documents/', max_length=255)
    folder = models.ForeignKey(Folder, related_name='documents', on_delete=models.SET_NULL, null=True)
    sort_order = models.IntegerField(default=0)
    searchable = models.BooleanField(default=False)
    ocr_provider = models.CharField(max_length=64, blank=True, default="paddleocr")
    ocr_status = models.CharField(
        max_length=32,
        choices=OcrStatus.choices,
        default=OcrStatus.NOT_STARTED,
    )
    ocr_error = models.TextField(blank=True, default="")
    ocr_started_at = models.DateTimeField(blank=True, null=True)
    ocr_completed_at = models.DateTimeField(blank=True, null=True)
    last_page = models.IntegerField(blank=True, null=True)
    zoom_level = models.IntegerField(blank=True, null=True)
    document_hash = models.CharField(max_length=64, blank=True, db_index=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    absolute_local_path = models.TextField(blank=True, default="")
    page_count = models.PositiveIntegerField(default=0)
    context_status = models.CharField(max_length=32, default="not_started", db_index=True)
    context_error = models.TextField(blank=True, default="")
    context_created_at = models.DateTimeField(blank=True, null=True)
    context_updated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.title


class DocumentPage(models.Model):
    class SourceType(models.TextChoices):
        EMBEDDED = "embedded", "Embedded text"
        OCR = "ocr", "OCR"
        COMBINED = "combined", "Embedded text and OCR"
        FAILED = "failed", "Extraction failed"

    document = models.ForeignKey(Document, related_name="context_pages", on_delete=models.CASCADE)
    page_number = models.PositiveIntegerField()
    extracted_text = models.TextField(blank=True, default="")
    text_blocks = models.JSONField(default=list, blank=True)
    page_image_path = models.TextField(blank=True, default="")
    thumbnail_path = models.TextField(blank=True, default="")
    source_type = models.CharField(
        max_length=16,
        choices=SourceType.choices,
        default=SourceType.EMBEDDED,
    )
    ocr_used = models.BooleanField(default=False)
    ocr_confidence = models.FloatField(blank=True, null=True)
    width = models.FloatField(default=0)
    height = models.FloatField(default=0)
    rotation = models.SmallIntegerField(default=0)
    visually_complex = models.BooleanField(default=False, db_index=True)
    complexity_reasons = models.JSONField(default=list, blank=True)
    extraction_error = models.TextField(blank=True, default="")
    ocr_cache_key = models.CharField(max_length=128, blank=True, default="")
    renderer_version = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "page_number"],
                name="unique_context_page_per_document",
            )
        ]


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, related_name="context_chunks", on_delete=models.CASCADE)
    chunk_id = models.CharField(max_length=96, unique=True)
    start_page = models.PositiveIntegerField()
    end_page = models.PositiveIntegerField()
    chunk_text = models.TextField()
    normalized_text = models.TextField(blank=True, default="")
    section_title = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_page", "id"]
        indexes = [
            models.Index(
                fields=["document", "start_page"],
                name="api_documen_documen_76bf5b_idx",
            ),
        ]


class Annotations(models.Model):
    document = models.OneToOneField(Document, related_name='annotations', on_delete=models.CASCADE)
    highlight_data = models.JSONField(null=True,)
    notepad = models.TextField(null=True, blank=True)
    sticky_note_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    major_topic = models.CharField(max_length=100, null=True)
    sub_topic = models.CharField(max_length=100, null=True)
    x_coordinate = models.FloatField(blank=True, db_index=True, null=True)
    y_coordinate = models.FloatField(blank=True, db_index=True, null=True)

    embedding_binary = models.BinaryField(null=True, blank=True)
    needs_embedding = models.BooleanField(default=False)

    content_hash = models.CharField(max_length=64, blank=True, default="")

    similar_papers = models.JSONField(default=list, blank=True)

    token_count = models.IntegerField(default=0) # for bm25 calcs

    def generate_content_hash(self):
        # hashing fields that contribute to embedding
        # NOTE: will include doc title in embedding just don't want to hash it to prevent N+1 Query

        # just getting the sticky note content because idc about any other data for embedding purposes
        sticky_text = ""
        data = self.sticky_note_data
        
        if isinstance(data, list):
            extracted_texts = [str(item.get("content", "")) for item in data] # type: ignore
            sticky_text = "".join(extracted_texts)

        notepad_content = self.notepad or ""

        content_string = f"{sticky_text}|{notepad_content}"
        return hashlib.sha256(content_string.encode('utf-8')).hexdigest()

    # override save to see if embedding is needed
    def save(self, *args, **kwargs):
        # Calculate new hash
        new_hash = self.generate_content_hash()
        
        # Only if the hash changed do, mark it as needing update 
        if new_hash != self.content_hash:
            self.content_hash = new_hash
            self.needs_embedding = True
            
        super().save(*args, **kwargs)

    def set_embedding(self, float_list):
        # Convert list to a numpy float32 array and then to bytes
        self.embedding_binary = np.array(float_list, dtype=np.float32).tobytes()
        self.needs_embedding = False

    def get_embedding(self):
        # Convert bytes back to a numpy array
        if not self.embedding_binary:
            return None
        return np.frombuffer(self.embedding_binary, dtype=np.float32) # type: ignore

    """
    most useful for bm25 
    unformatted string of text 
    includes doc title, major_topic, sub_topic, highlight_data, sticky_note_data, notepad
    """
    def get_meaningful_text_unformatted(self): 
        title = self.document.title
        major_topic = self.major_topic
        sub_topic = self.sub_topic
        highlight_data = self.highlight_data
        sticky_note_data = self.sticky_note_data
        notepad = self.notepad

        formatted_highlights = " ".join(h["text"] for h in highlight_data) if highlight_data else "" # type: ignore
        
        formatted_sticky = " ".join(f"{s.get('tag', '')} {s.get('content', '')}" for s in sticky_note_data) if sticky_note_data else "" # type: ignore

        fields = [title, major_topic, sub_topic, formatted_highlights, formatted_sticky, notepad]

        output = " ".join(fields)

        # rough tokenization that finds each word
        tokens = re.findall(r"\b\w+(?:['\-]\w+)*\b", output)
        tokens = [t.lower() for t in tokens]
        return tokens

    def __str__(self):
        return f"Annotation for {self.document.title} at {self.created_at}"
    
# for bm25
class SearchTerm(models.Model): 
    word = models.CharField(max_length=255)
    idf = models.FloatField(default=0.0)
    docs_containing = models.IntegerField(default=0)

# one for each term and annotation
class AnnotationIndex(models.Model): 
    term = models.ForeignKey(SearchTerm, on_delete=models.CASCADE)
    annotation = models.ForeignKey(Annotations, on_delete=models.CASCADE, related_name="bm25_entries")
    frequency = models.IntegerField() 
    field_boost = models.FloatField(default=1.0) # Bonus for matches in major_topic

    class Meta:
        unique_together = ('term', 'annotation')
        indexes = [models.Index(fields=['term', 'annotation'])]

class ChatLogs(models.Model): 
    name = models.CharField(max_length=255)
    content = models.JSONField(default=list)
    provider = models.CharField(max_length=32, default="legacy", db_index=True)
    document = models.ForeignKey(
        Document,
        related_name="chat_logs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    codex_thread_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

class SmartCollections(models.Model): 
    annotation_ids = models.JSONField(default=list, blank=True)
    is_ready = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    reading_recommendations = models.JSONField(blank=True, null=True)
    colors = models.JSONField(blank=True, null=True)
    
    