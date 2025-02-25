import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import MarketTrend, Crop
from .serializers import MarketTrendSerializer

class TrendsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'trends'

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
        crop_id = data.get('crop')  # Expect crop_id from the client

        print('crop id', crop_id, data)

        if crop_id:
            # Save the crop_id to the database (if needed)
            await self.save_crop_id(crop_id)

            # Fetch market trends for the crop
            market_trend = await self.get_market_trend(crop_id)
        
            # Broadcast the updated market trends to all clients
            await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "market_trends",
                        "crop":crop_id,
                        "market_trend": market_trend
                    }
                )

    async def market_trends(self, event):
        market_trend = event["market_trend"]
        await self.send(text_data=json.dumps({
            "market_trend": market_trend
        }))

    @database_sync_to_async
    def save_crop_id(self, crop_id):
        """
        Save the crop_id to the database (if needed).
        """
        try:
            crop = Crop.objects.get(pk=crop_id)
            if crop:
                MarketTrend.objects.create(crop=crop, total_demand=0)
        except Crop.DoesNotExist:
            print('crop doesnot exist')

    @database_sync_to_async
    def get_market_trend(self, crop_id):
        """
        Fetch the latest market trend for a specific crop.
        """
        market_trend = MarketTrend.objects.select_related('crop').filter(crop_id=crop_id).first()
        if market_trend:
            serializer = MarketTrendSerializer(market_trend)
            return serializer.data
        return None

