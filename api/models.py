from django.db import models
import numpy as np

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

    def __str__(self):
        return self.title
    
class Annotations(models.Model):
    document = models.OneToOneField(Document, related_name='annotations', on_delete=models.CASCADE)
    highlight_data = models.JSONField(null=True,)
    notepad = models.TextField(null=True, blank=True)
    sticky_note_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    embedding_binary = models.BinaryField(null=True, blank=True)

    def set_embedding(self, float_list):
        # Convert list to a numpy float32 array and then to bytes
        self.embedding_binary = np.array(float_list, dtype=np.float32).tobytes()

    def get_embedding(self):
        # Convert bytes back to a numpy array
        return np.frombuffer(self.embedding_binary, dtype=np.float32) # type: ignore


    def __str__(self):
        return f"Annotation for {self.document.title} at {self.created_at}"

# Update whenever AI chat implementation is done
class ChatLogs(models.Model): 
    name = models.CharField(max_length=255)
    content = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

class SmartCollections(models.Model): 
    name = models.CharField(max_length=255)
    created_at = models.DateField(auto_now_add=True)
