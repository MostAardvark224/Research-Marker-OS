from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0047_note_sync"),
    ]

    operations = [
        migrations.AddField(
            model_name="annotations",
            name="centrality",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="annotations",
            name="influence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="annotations",
            name="node_role",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="annotations",
            name="pinned_topic",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="smartcollections",
            name="topics",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartcollections",
            name="ghost_nodes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="smartcollections",
            name="heatmap",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="smartcollections",
            name="stats",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
