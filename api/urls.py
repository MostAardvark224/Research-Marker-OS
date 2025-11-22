from django.urls import path
import api.views as views  

urlpatterns = [
    path('upload-documents/', views.DocumentsUploadView.as_view(), name='upload-documents'),
    path('documents/', views.DocumentsListView.as_view({'get': 'list'}), name='documents-list'),
]