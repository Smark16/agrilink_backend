import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import OrderCrop, CropPerformance

class CropPerformanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Retrieve the crop ID from the URL route
        self.crop_id = self.scope['url_route']['kwargs']['id']
        self.room_group_name = f'crop_{self.crop_id}'

        # Add the user to the crop-specific group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from the crop-specific group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Process incoming messages if needed
        data = json.loads(text_data)
        action = data.get('action', None)

        if action == 'update_stats':
            # Fetch updated stats
            crop_stats = await self.get_crop_performance()
            # Broadcast the updated stats to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_update',
                    'crop_stats': crop_stats
                }
            )

    async def send_update(self, event):
        # Send the update to the WebSocket
        crop_stats = event['crop_stats']
        await self.send(text_data=json.dumps({
            'type': 'update',
            'data': crop_stats
        }))

    @database_sync_to_async
    def get_crop_performance(self):
        # Fetch crop performance statistics from the database
        try:
            crop = OrderCrop.objects.get(pk=self.crop_id)
            # Fetch the latest performance data for this crop
            latest_performance = CropPerformance.objects.filter(orderCrop=crop).latest('date')
            
            performance_data = {
                'quantity_sold': latest_performance.get_quantity_sold,
                'revenue': latest_performance.get_crop_revenue,
            }
            return performance_data
        except (OrderCrop.DoesNotExist, CropPerformance.DoesNotExist):
            return {}  # Return empty dict if crop or performance data not found
        
#     @database_sync_to_async
# def update_crop_performance(self):
#     try:
#         crop = OrderCrop.objects.get(pk=self.crop_id)
#         # Fetch current performance or create a new one
#         performance, created = CropPerformance.objects.get_or_create(
#             orderCrop=crop, 
#             defaults={'date': timezone.now()}
#         )
        
#         # Update performance data here based on new sales or other metrics
#         # Example:
#         performance.quantity_sold = crop.quantity  # Update based on new sale
#         performance.revenue = performance.quantity_sold * crop.price_per_unit
#         performance.save()
        
#         return {
#             'quantity_sold': performance.quantity_sold,
#             'revenue': performance.revenue,
#         }
#     except OrderCrop.DoesNotExist:
#         return {}

# # Then in your receive method:
# if action == 'update_stats':
#     crop_stats = await self.update_crop_performance()
#     await self.channel_layer.group_send(
#         self.room_group_name,
#         {
#             'type': 'send_update',
#             'crop_stats': crop_stats
#         }
#     )