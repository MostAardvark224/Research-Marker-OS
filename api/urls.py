from django.urls import path
import api.views as views  
from rest_framework.routers import DefaultRouter
from .views import DocumentsViewSet

router = DefaultRouter()

router.register(r'documents', DocumentsViewSet, basename='documents')
router.register(r'folders', views.FoldersViewSet, basename='folders')

urlpatterns = [
    path('complete-fetch/', views.CompleteFetch.as_view(), name='complete-fetch'),
    path('get-paper/<int:pk>/', views.getPaper.as_view(), name='get-paper'),
]

urlpatterns += router.urls