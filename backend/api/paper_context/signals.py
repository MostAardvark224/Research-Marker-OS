from pathlib import Path
import shutil

from django.db.models.signals import post_delete
from django.dispatch import receiver

from api.models import Document
from api.utils import get_app_data_dir


@receiver(post_delete, sender=Document)
def delete_document_context_cache(sender, instance: Document, **kwargs) -> None:
    if not instance.document_hash:
        return
    if Document.objects.filter(document_hash=instance.document_hash).exists():
        return
    cache_dir = Path(get_app_data_dir()) / "paper_context" / instance.document_hash
    shutil.rmtree(cache_dir, ignore_errors=True)
