from django.urls import re_path
from . import Perfomance_consumers, LogConsumer, MarketTrendConsumer

websocket_urlpatterns = [
    re_path(r'ws/crop-performance/', Perfomance_consumers.CropPerformanceConsumer.as_asgi()),
    re_path(r'ws/user_logs/', LogConsumer.CropLogConsumer.as_asgi()),
    re_path(r'ws/market_trends/', MarketTrendConsumer.TrendsConsumer.as_asgi())
]

