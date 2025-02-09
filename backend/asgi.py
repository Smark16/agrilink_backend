import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to ensure the app is loaded
# before importing the channels routing
django_asgi_app = get_asgi_application()

# Now we can import the rest of the channels packages and the routing
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import Agri_Link.routing

# Define the application protocol type router
application = ProtocolTypeRouter({
    'http': django_asgi_app,  # Use the ASGI application we initialized earlier
    'websocket': AuthMiddlewareStack(
        URLRouter(
            Agri_Link.routing.websocket_urlpatterns
        )
    ),
})
