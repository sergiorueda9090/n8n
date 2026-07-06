"""
Ejecuta la suite de auto-testing sobre los flujos críticos y guarda un ciclo
en el informe (que se ve en /testing/).

Uso:
    python manage.py run_autotests

Cada ejecución = un ciclo nuevo. Corre el ciclo 1, aplica en n8n las mejoras
sugeridas por la IA y vuelve a correr: la página /testing/ mostrará la
reducción de errores entre el último ciclo y el anterior.
"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from landing import autotesting


class Command(BaseCommand):
    help = 'Corre la suite de auto-testing de los flujos críticos y guarda un ciclo.'

    def handle(self, *args, **options):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING(
            f'Auto-testing Aurorita — {len(autotesting.CASOS)} casos sobre '
            f'{len(autotesting.FLUJOS_CRITICOS)} flujos críticos'))
        w(f'Webhook: {autotesting.settings.N8N_WEBHOOK_URL}')

        client = autotesting._crear_cliente_ia()
        if client:
            w(self.style.SUCCESS(
                f'Evaluación: juez IA OpenAI ({autotesting.settings.AUTOTEST_MODEL})'))
        else:
            w(self.style.WARNING(
                'Evaluación: por REGLAS (sin OPENAI_API_KEY). '
                'Define OPENAI_API_KEY en .env para el juez IA.'))
        w('')

        timestamp = datetime.now(timezone.utc).isoformat()
        ciclo = autotesting.correr_suite(timestamp, log=w)
        numero = autotesting.guardar_ciclo(ciclo)

        r = ciclo['resumen']
        w('')
        w(self.style.MIGRATE_HEADING(f'Ciclo #{numero} — resumen'))
        w(f'  Pasa:    {r["pasa"]}/{ciclo["total_casos"]}')
        w(f'  Parcial: {r["parcial"]}')
        w(f'  Falla:   {r["falla"]}')
        w(f'  Hallazgos → crítico: {r["critico"]}  mayor: {r["mayor"]}  '
          f'menor: {r["menor"]}  (latencia alta: {r["latencia"]})')
        w('')
        w(self.style.SUCCESS(
            f'Informe actualizado. Míralo en /testing/ (o {autotesting.settings.AUTOTEST_REPORT}).'))
