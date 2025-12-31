from django.core.management.base import BaseCommand
from api.ai import embed_annotations

class Command(BaseCommand):
    help = 'Runs the batch embedding process for pending annotations'

    def handle(self, *args, **kwargs):
        embed_annotations()