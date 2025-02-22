from django.urls import re_path
from . import Perfomance_consumers, LogConsumer

websocket_urlpatterns = [
    re_path(r'ws/crop-performance/(?P<id>\d+)/$', Perfomance_consumers.CropPerformanceConsumer.as_asgi()),
    re_path(r'ws/user_logs/', LogConsumer.CropLogConsumer.as_asgi())
]
 #const ws = new WebSocket(`ws://${window.location.host}/ws/crop-performance/${cropId}/`);
