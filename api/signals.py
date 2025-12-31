from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import api.models as models
from api.ai import calculate_idf
import math
from collections import Counter
from django.db.models import F

@receiver(post_save, sender=models.Annotations)
def update_annotation_index(sender, instance, **kwargs):
    words = instance.get_meaningful_text_unformatted()
    
    token_count = len(words)
    models.Annotations.objects.filter(pk=instance.pk).update(token_count=token_count)

    """
    decrementing old terms 'docs_containing' and annotations index and then recomputing everything 
    - do this to catch terms that were deleted
    """

    # decrementing
    old_term_ids = models.AnnotationIndex.objects.filter(
        annotation=instance
    ).values_list('term_id', flat=True)
    
    if old_term_ids:
        models.SearchTerm.objects.filter(id__in=old_term_ids).update(
            docs_containing=F('docs_containing') - 1
        )

    models.AnnotationIndex.objects.filter(annotation=instance).delete()

    word_counts = Counter(words)

    new_entries = []
    for word, freq in word_counts.items():
        term_obj, created = models.SearchTerm.objects.get_or_create(word=word)
        
        if created:
            term_obj.docs_containing = 1 
        else:
            term_obj.docs_containing += 1
        
        term_obj.idf = calculate_idf(term_obj.docs_containing)
        term_obj.save()

        new_entries.append(models.AnnotationIndex(
            term=term_obj,
            annotation=instance,
            frequency=freq
        ))
    
    models.AnnotationIndex.objects.bulk_create(new_entries)