from django.urls import path
import api.views as views  
from rest_framework.routers import DefaultRouter
from .views import DocumentsViewSet

router = DefaultRouter()

router.register(r'documents', DocumentsViewSet, basename='documents')
router.register(r'folders', views.FoldersViewSet, basename='folders')
router.register(r'annotations', views.AnnotationsViewSet, basename='annotations')

urlpatterns = [
    path('complete-fetch/', views.CompleteFetch.as_view(), name='complete-fetch'),
    path('get-paper/<int:pk>/', views.getPaper.as_view(), name='get-paper'),
    path('user-preferences/', views.UserPreferencesView.as_view(), name='user-preferences'),
    path('fetch-scholar-inbox-papers/', views.FetchScholarInboxPapers.as_view(), name='fetch-scholar-inbox-papers'),
    path('search-notes', views.SearchNotesView.as_view(), name=
         'search-notes')
]

urlpatterns += router.urls