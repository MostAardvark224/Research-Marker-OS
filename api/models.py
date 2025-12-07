from django.db import models

class Folder(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Document(models.Model):
    title = models.CharField(max_length=255)
    uploaded_at = models.DateField(auto_now_add=True)
    file = models.FileField(upload_to='documents/')
    folder = models.ForeignKey(Folder, related_name='documents', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.title