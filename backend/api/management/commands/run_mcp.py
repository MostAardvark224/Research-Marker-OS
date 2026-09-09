from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the local Research Marker MCP server for ChatGPT Desktop, Codex, or Claude"

    def handle(self, *args, **options):
        from api.mcp.server import main

        main()
