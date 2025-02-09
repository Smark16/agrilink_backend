from fcm_django.models import FCMDevice
from firebase_admin.messaging import Message, Notification, UnregisteredError
import logging

logger = logging.getLogger(__name__)

def send_push_notification(fcm_token, notification_title, notification_body, notification_image=None):
    try:
        # Fetch the device using the FCM token
        device = FCMDevice.objects.get(registration_id=fcm_token)
        
        # Create the message
        message = Message(
            notification=Notification(
                title=notification_title,
                body=notification_body,
                image=notification_image
            )
        )
        
        # Send the message
        response = device.send_message(message)
        
        # Log the response for debugging
        logger.info(f"FCM Response: {response}")
        
        # Check if the message was sent successfully
        if hasattr(response, 'success_count') and response.success_count > 0:
            logger.info("Notification sent successfully")
            return True
        elif hasattr(response, 'success') and response.success:
            logger.info("Notification sent successfully")
            return True
        else:
            logger.error("Failed to send notification")
            return False
    
    except FCMDevice.DoesNotExist:
        logger.error(f"Device with token {fcm_token} not found")
        return False
    except UnregisteredError:
        logger.error(f"FCM token {fcm_token} is invalid or unregistered")
        # Remove the invalid token from the database
        FCMDevice.objects.filter(registration_id=fcm_token).delete()
        return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False