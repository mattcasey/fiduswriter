import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.contrib.flatpages.models import FlatPage

from document.models import DocumentTemplate
from style.models import DocumentStyle, CitationStyle


class Command(BaseCommand):
    help = ('Setup Fidus Writer installation.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--restart',
            action='store_true',
            dest='restart',
            default=False,
            help='Flush database before initialization.',
        )
        parser.add_argument(
            '--no-static',
            action='store_true',
            dest='no-static',
            default=False,
            help='Do not collect static files.',
        )
        parser.add_argument(
            '--no-compress',
            action='store_true',
            dest='no-compress',
            default=False,
            help='Do not attempt to compress static files.',
        )

    def handle(self, *args, **options):
        if options["restart"]:
            call_command("flush")
            call_command("migrate", fake=True)
        else:
            call_command("migrate")
        if CitationStyle.objects.count() == 0:
            call_command(
                "loaddata",
                os.path.join(
                    settings.SRC_PATH,
                    "style/fixtures/citation_styles.json"
                )
            )
        if DocumentTemplate.objects.count() == 0:
            call_command(
                "loaddata",
                os.path.join(
                    settings.SRC_PATH,
                    "document/fixtures/initial_documenttemplates.json"
                )
            )
        if DocumentStyle.objects.count() == 0:
            call_command(
                "loaddata",
                os.path.join(
                    settings.SRC_PATH,
                    "style/fixtures/initial_styles.json"
                )
            )
        if FlatPage.objects.count() == 0:
            call_command(
                "loaddata",
                os.path.join(
                    settings.SRC_PATH,
                    "base/fixtures/initial_terms.json"
                )
            )
        if (
            os.environ.get('NO_COMPILEMESSAGES') or
            (
                os.path.isfile(os.path.join(
                    settings.SRC_PATH,
                    "locale/BASE/LC_MESSAGES/django.mo"
                )) and
                os.path.getmtime(os.path.join(
                    settings.SRC_PATH,
                    "locale/BASE/LC_MESSAGES/django.mo"
                )) > os.path.getmtime(os.path.join(
                    settings.SRC_PATH,
                    "locale/BASE/LC_MESSAGES/django.po"
                ))
            )

        ):
            pass
        else:
            call_command("compilemessages")
        call_command("transpile")
        if (
            not options["no-compress"] and
            settings.COMPRESS_OFFLINE and
            settings.COMPRESS_ENABLED
        ):
            try:
                call_command("compress")
            except CommandError:
                pass
        if (
            not options["no-static"] and
            not settings.DEBUG
        ):
            call_command("collectstatic", interactive=False)
