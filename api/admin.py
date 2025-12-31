from django.contrib import admin
import api.models as models
# Register your models here.
admin.site.register(models.Folder)
admin.site.register(models.Document)
admin.site.register(models.Annotations)
admin.site.register(models.ChatLogs)
admin.site.register(models.SmartCollections)