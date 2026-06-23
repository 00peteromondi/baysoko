from channels.generic.websocket import AsyncWebsocketConsumer
import json
import asyncio
from asgiref.sync import sync_to_async

from .models import Store
from .models_bulk import BatchJob


class BulkJobProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.store_slug = self.scope['url_route']['kwargs'].get('slug')
        self.job_id = int(self.scope['url_route']['kwargs'].get('job_id'))

        user = self.scope.get('user')
        # Basic auth check: require authenticated user
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Accept connection
        await self.accept()

        # Start streaming updates
        self._stop = False
        try:
            await self.stream_progress()
        except asyncio.CancelledError:
            pass

    async def disconnect(self, close_code):
        self._stop = True

    @sync_to_async
    def _get_job(self):
        store = Store.objects.get(slug=self.store_slug)
        return BatchJob.objects.get(id=self.job_id, store=store)

    async def stream_progress(self):
        last_status = None
        while not self._stop:
            try:
                job = await self._get_job()
            except Exception:
                await self.send(json.dumps({'error': 'job_not_found'}))
                await self.close()
                return

            payload = {
                'id': job.id,
                'status': job.status,
                'progress_percentage': getattr(job, 'progress_percentage', None),
                'processed_items': getattr(job, 'processed_items', None),
                'total_items': getattr(job, 'total_items', None),
                'success_count': getattr(job, 'success_count', None),
                'error_count': getattr(job, 'error_count', None),
            }

            # Send if status changed or always (lightweight)
            await self.send(json.dumps(payload, default=str))

            if job.status in ['completed', 'completed_with_errors', 'failed', 'cancelled']:
                await self.close()
                return

            await asyncio.sleep(1)
