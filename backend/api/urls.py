from django.urls import path
import api.views as views  
import api.codex_views as codex_views
from rest_framework.routers import DefaultRouter
from .views import DocumentsViewSet # type: ignore
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
    path('documents/reorder/', views.ReorderDocumentsView.as_view(), name='documents-reorder'),
    path('folders/reorder/', views.ReorderFoldersView.as_view(), name='folders-reorder'),
    path('get-paper/<int:pk>/', views.getPaper.as_view(), name='get-paper'),
    path('user-preferences/', views.UserPreferencesView.as_view(), name='user-preferences'),
    path('env-vars/', views.EnvironmentVariablesView.as_view(), name='environment-variables'),
    path('ai-models/', views.AIModelsView.as_view(), name='ai-models'),
    path('ocr-providers/', views.OCRProvidersView.as_view(), name='ocr-providers'),
    path('documents/<int:pk>/ocr/', views.DocumentOCRView.as_view(), name='document-ocr'),
    path('fetch-scholar-inbox-papers/', views.FetchScholarInboxPapers.as_view(), name='fetch-scholar-inbox-papers'),
    path('arxiv-paper-metadata/', views.ArxivPaperMetadataView.as_view(), name='arxiv-paper-metadata'),
    path('import-arxiv-paper/', views.ImportArxivPaperView.as_view(), name='import-arxiv-paper'),
    path('search-notes/', views.SearchNotesView.as_view(), name=
         'search-notes'), 
    path('ask-ai/', views.AIChatView.as_view(), name='ask-ai'), 
    path('smart-collection/', views.SmartCollectionView.as_view(), name='smart-collection'),
    path('smart-collection/jobs/<uuid:job_id>/', views.SmartCollectionJobView.as_view(), name='smart-collection-job'),
    path('poll-smart-collection/<str:task_id>/', views.PollSmartCollection.as_view(), name='poll-smart-collection'),
    path('reading-recommendations/', views.ReadingRecommendationsView.as_view(), name='reading-recommendations'),
    path('codex/status/', codex_views.CodexStatusView.as_view(), name='codex-status'),
    path('codex/login/', codex_views.CodexLoginView.as_view(), name='codex-login'),
    path('codex/logout/', codex_views.CodexLogoutView.as_view(), name='codex-logout'),
    path('codex/rate-limits/', codex_views.CodexRateLimitsView.as_view(), name='codex-rate-limits'),
    path('codex/models/', codex_views.CodexModelsView.as_view(), name='codex-models'),
    path('codex/conversations/', codex_views.CodexConversationsView.as_view(), name='codex-conversations'),
    path(
        'codex/conversations/<int:conversation_id>/',
        codex_views.CodexConversationDetailView.as_view(),
        name='codex-conversation-detail',
    ),
    path(
        'codex/conversations/<int:conversation_id>/stream/',
        codex_views.CodexConversationStreamView.as_view(),
        name='codex-conversation-stream',
    ),
    path(
        'codex/conversations/<int:conversation_id>/cancel/',
        codex_views.CodexConversationCancelView.as_view(),
        name='codex-conversation-cancel',
    ),
    path(
        'paper-context/documents/<int:document_id>/',
        codex_views.PaperContextStatusView.as_view(),
        name='paper-context-status',
    ),
    path(
        'paper-context/documents/<int:document_id>/pages/<int:page_number>/',
        codex_views.PaperContextPageView.as_view(),
        name='paper-context-page',
    ),
    path(
        'paper-context/documents/<int:document_id>/preview/',
        codex_views.PaperContextPreviewView.as_view(),
        name='paper-context-preview',
    ),
    path('paper-context/active/', codex_views.ActiveContextView.as_view(), name='paper-context-active'),
    path('paper-context/clear/', codex_views.PaperContextClearView.as_view(), name='paper-context-clear'),
]

# serves files
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT, 
    }),
]

urlpatterns += router.urls