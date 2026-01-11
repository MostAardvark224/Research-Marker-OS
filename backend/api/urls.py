from django.urls import path
import api.views as views  
from rest_framework.routers import DefaultRouter
from .views import DocumentsViewSet
from django.conf import settings
from django.views.static import serve
from django.urls import re_path

router = DefaultRouter()

router.register(r'documents', DocumentsViewSet, basename='documents')
router.register(r'folders', views.FoldersViewSet, basename='folders')
router.register(r'annotations', views.AnnotationsViewSet, basename='annotations')
router.register(r'chatlogs', views.ChatLogsViewset, basename='chatlogs')


urlpatterns = [
    path('complete-fetch/', views.CompleteFetch.as_view(), name='complete-fetch'),
    path('get-paper/<int:pk>/', views.getPaper.as_view(), name='get-paper'),
    path('user-preferences/', views.UserPreferencesView.as_view(), name='user-preferences'),
    path('env-vars/', views.EnvironmentVariablesView.as_view(), name='environment-variables'),
    path('fetch-scholar-inbox-papers/', views.FetchScholarInboxPapers.as_view(), name='fetch-scholar-inbox-papers'),
    path('search-notes/', views.SearchNotesView.as_view(), name=
         'search-notes'), 
    path('ask-ai/', views.AIChatView.as_view(), name='ask-ai'), 
    path('smart-collection/', views.SmartCollectionView.as_view(), name='smart-collection'),
    path('poll-smart-collection/<str:task_id>/', views.PollSmartCollection.as_view(), name='poll-smart-collection'),
    path('reading-recommendations/', views.ReadingRecommendationsView.as_view(), name='reading-recommendations'),
]

# serves files
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT, 
    }),
]

urlpatterns += router.urls