"""
Job: reprocesa eventos crudos de Wompi que quedaron sin procesar.

El webhook persiste cada evento en webhook_events (status="received")
antes de responder 200. Si el worker de background murió o el
procesamiento falló, este job reintenta los eventos con más de
WEBHOOK_EVENT_RETRY_DELAY_MINUTES de antigüedad hasta
WEBHOOK_EVENT_MAX_ATTEMPTS; al agotarlos quedan en "failed" para
revisión manual (se loguea a nivel ERROR).

Sugerencia de cron (junto al reconcile de suscripciones):
    python -m apps.api.jobs.reprocess_webhook_events
"""
from __future__ import annotations

import asyncio
import logging

from apps.api.routes.v1.webhooks import reprocess_stuck_webhook_events


async def main() -> dict[str, int]:
    return await reprocess_stuck_webhook_events()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    stats = asyncio.run(main())
    print(f"--- REPROCESAMIENTO DE WEBHOOK EVENTS ---")
    print(f"Eventos escaneados:   {stats['scanned']}")
    print(f"Reintentados:         {stats['reprocessed']}")
    print(f"Agotaron reintentos:  {stats['gave_up']}")
