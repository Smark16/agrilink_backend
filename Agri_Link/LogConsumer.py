import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import *
from datetime import datetime
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth, ExtractYear

class CropLogConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # logs = 'user_logs'
        self.room_group_name = 'crop_logs'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        crop = data.get('crop')
        action = data.get('action')
       
        print(data, crop, action)

        await self.save_logs(action, crop)

        # Fetch updated counts after logging the action
        stats = await self.get_updated_stats(crop)

        # Update monthly_stats in UserInteractionLog
        await self.update_monthly_stats(crop, stats)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'crop_logs',
                'action': action,
                'crop': crop,
                'monthly_stats': stats  # Send updated stats
            }
        )

    async def crop_logs(self, event):
        action = event['action']
        crop_id = event['crop']
        stats = event['monthly_stats']  # Receive updated stats

        await self.send(text_data=json.dumps({
            'type': 'user_logs',
            'action': action,
            'crop': crop_id,
            'monthly_stats': stats  # Send updated stats to frontend
        }))

    @database_sync_to_async
    def save_logs(self, action: str, crop: int):
        """Save the interaction log (view or purchase)"""
        try:
            crop_obj = Crop.objects.get(pk=crop)
            UserInteractionLog.objects.create(action=action, crop=crop_obj)
        except Crop.DoesNotExist:
            print('Crop does not exist')

    @database_sync_to_async
    def get_updated_stats(self, crop_id):
            """Fetch the updated view and purchase counts in real-time"""
            current_year = datetime.now().year
            current_month = datetime.now().month

            interactions = UserInteractionLog.objects.filter(
                crop_id=crop_id,
                timestamp__year=current_year,
                timestamp__month__lte=current_month  # Only fetch up to the current month
            ) \
            .annotate(
                month=ExtractMonth('timestamp'),
                year=ExtractYear('timestamp')
            ) \
            .values('year', 'month') \
            .annotate(
                views=Count('id', filter=Q(action='view')),
                purchases=Count('id', filter=Q(action='purchase'))
            )

            # Convert interactions to dictionary for quick lookup
            existing_data = {f"{i['year']}-{i['month']}": i for i in interactions}

            # Prepare updated monthly data
            monthly_data = []
            for month in range(1, current_month + 1):  # Only up to the current month
                key = f"{current_year}-{month}"
                record = {
                    "year": current_year,
                    "month": month,
                    "views": 0,
                    "purchases": 0
                }
                if key in existing_data:
                    record.update({
                        "views": existing_data[key]["views"] or 0,
                        "purchases": existing_data[key]["purchases"] or 0
                    })
                monthly_data.append(record)

            return monthly_data  # Return updated stats

    @database_sync_to_async
    def update_monthly_stats(self, crop_id, stats):
        """Update the monthly_stats JSONField in UserInteractionLog"""
        try:
            # Fetch the latest UserInteractionLog for the crop
            latest_log = UserInteractionLog.objects.filter(crop_id=crop_id).latest('timestamp')

            # Update the monthly_stats field with the new stats
            latest_log.monthly_stats = stats
            latest_log.save()

            print(f"Updated monthly_stats for crop {crop_id}: {stats}")
        except UserInteractionLog.DoesNotExist:
            print('No interaction logs found for the crop')