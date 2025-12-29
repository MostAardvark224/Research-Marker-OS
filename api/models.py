from django.db import models
import numpy as np
from django.utils import timezone
import hashlib
import json
from django.db import transaction

class Folder(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Document(models.Model):
    title = models.CharField(max_length=255)
    uploaded_at = models.DateField(auto_now_add=True)
    file = models.FileField(upload_to='documents/', max_length=255)
    folder = models.ForeignKey(Folder, related_name='documents', on_delete=models.SET_NULL, null=True)
    searchable = models.BooleanField(default=False)
    last_page = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.title
    
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

    def __str__(self):
        return f"Annotation for {self.document.title} at {self.created_at}"

class ChatLogs(models.Model): 
    name = models.CharField(max_length=255)
    content = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

class SmartCollections(models.Model): 
    annotation_ids = models.JSONField(default=list, blank=True)
    is_ready = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    reading_recommendations = models.JSONField(blank=True, null=True)
    colors = models.JSONField(blank=True, null=True)
    
    