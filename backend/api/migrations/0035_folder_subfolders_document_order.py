from django.db import migrations, models
import django.db.models.deletion


def assign_initial_sort_orders(apps, schema_editor):
    Folder = apps.get_model("api", "Folder")
    Document = apps.get_model("api", "Document")

    for index, folder in enumerate(Folder.objects.order_by("created_at", "id")):
        folder.sort_order = index
        folder.save(update_fields=["sort_order"])

    for folder in Folder.objects.all():
        for index, document in enumerate(
            Document.objects.filter(folder_id=folder.id).order_by("uploaded_at", "id")
        ):
            document.sort_order = index
            document.save(update_fields=["sort_order"])

    for index, document in enumerate(
        Document.objects.filter(folder__isnull=True).order_by("uploaded_at", "id")
    ):
        document.sort_order = index
        document.save(update_fields=["sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0034_remove_folder_last_folder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="folder",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="folder",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subfolders",
                to="api.folder",
            ),
        ),
        migrations.AddField(
            model_name="folder",
            name="sort_order",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="document",
            name="sort_order",
            field=models.IntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                fields=("parent", "name"),
                name="unique_folder_name_per_parent",
            ),
        ),
        migrations.RunPython(assign_initial_sort_orders, migrations.RunPython.noop),
    ]
