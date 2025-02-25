from rest_framework.response import Response
from rest_framework import generics
from .models import *
from rest_framework.views import APIView
from .serializers import *
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import *
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser, FormParser
from datetime import date
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from .models import User
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.pagination import PageNumberPagination
from django.db.models import Prefetch
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum, F, When, Case, Value
from django.db.models.functions import ExtractMonth, ExtractYear, ExtractDay
from datetime import datetime
# from calendar import monthrange
from fcm_django.models import FCMDevice
from .utils import send_push_notification
from django.db import transaction
import requests
import uuid
import user_agents
from datetime import timedelta, datetime
from collections import defaultdict
from django.utils import timezone

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Create your views here.
class ObtainaPairView(TokenObtainPairView):
    serializer_class = ObtainSerializer

#list all users
class AllUsers(generics.ListAPIView):
    queryset = User.objects.select_related('profile')
    serializer_class = UserSerializer

#list all farmers
class AllFarmers(generics.ListAPIView):
    queryset = Farmer.objects.all()
    serializer_class = FarmerSerializer

#Update user 
class UpdateUser(generics.UpdateAPIView):
    queryset = User.objects.select_related('profile')
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

#list single user
class SingleUser(generics.RetrieveAPIView):
      queryset = User.objects.select_related('profile')
      serializer_class = UserSerializer

      def retrieve(self, request, *args, **kwargs):
          instance = self.get_object()
          serializer = self.get_serializer(instance)
          return Response(serializer.data, status=status.HTTP_200_OK)
      

class SaveFCMTokenView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        
        # Ensure the user is updating their own FCM token
        if user != request.user:
            return Response(
                {"error": "You do not have permission to update this user's FCM token."},
                status=status.HTTP_403_FORBIDDEN
            )

        fcm_token = request.data.get('fcm_token')
        if not fcm_token:
            return Response(
                {"error": "FCM token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Check if the token already exists in the database (for any user)
            existing_device = FCMDevice.objects.filter(registration_id=fcm_token).first()

            if existing_device:
                # If the token exists, update the associated user
                if existing_device.user != user:
                    existing_device.user = user
                    existing_device.save()
                    return Response(
                        {"message": "FCM token updated successfully (reassigned to current user)"},
                        status=status.HTTP_200_OK
                    )
                else:
                    return Response(
                        {"message": "FCM token is already associated with this user"},
                        status=status.HTTP_200_OK
                    )
            else:
                # If the token doesn't exist, create a new FCMDevice for the user
                FCMDevice.objects.create(
                    registration_id=fcm_token,
                    user=user,
                    type='web'  # or 'ios' or 'web', depending on your app
                )
                return Response(
                    {"message": "FCM token saved successfully"},
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            return Response(
                {"error": f"An error occurred while saving the token: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# class SaveFCMTokenView(generics.UpdateAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [IsAuthenticated]

#     def patch(self, request, *args, **kwargs):
#         user = self.get_object()
        
#         # Log request details for debugging
#         logger.info(f"Request received from: {request.META.get('HTTP_USER_AGENT')}")
#         logger.info(f"FCM Token: {request.data.get('fcm_token')}")

#         if user != request.user:
#             return Response(
#                 {"error": "You do not have permission to update this user's FCM token."},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         fcm_token = request.data.get('fcm_token')
#         if not fcm_token:
#             return Response(
#                 {"error": "FCM token is required"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             existing_device = FCMDevice.objects.filter(registration_id=fcm_token).first()

#             if existing_device:
#                 if existing_device.user != user:
#                     existing_device.user = user
#                     existing_device.save()
#                     return Response(
#                         {"message": "FCM token updated successfully (reassigned to current user)"},
#                         status=status.HTTP_200_OK
#                     )
#                 else:
#                     return Response(
#                         {"message": "FCM token is already associated with this user"},
#                         status=status.HTTP_200_OK
#                     )
#             else:
#                 # Detect if the request is from a mobile browser
#                 user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
#                 if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
#                     device_type = 'web_mobile'
#                 else:
#                     device_type = 'web'

#                 # Create a new FCM device
#                 FCMDevice.objects.create(
#                     registration_id=fcm_token,
#                     user=user,
#                     type=device_type  # Set to web_mobile for mobile browsers
#                 )
#                 return Response(
#                     {"message": "FCM token saved successfully"},
#                     status=status.HTTP_200_OK
#                 )

#         except Exception as e:
#             logger.error(f"Error saving FCM token: {str(e)}")
#             return Response(
#                 {"error": f"An error occurred while saving the token: {str(e)}"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
            
#END USER VIEWS

# registration views
class BuyerRegistrationView(generics.CreateAPIView):
    queryset = Buyer.objects.all()
    serializer_class = BuyerRegistration
    permission_classes = [AllowAny]

class FarmerRegistrationView(generics.CreateAPIView):
    queryset = Farmer.objects.all()
    serializer_class = FarmerRegistration
    permission_classes = [AllowAny]
# end registration views

#RESET PASSWORD VIEWS
# Send Password Reset Email
class PasswordResetRequestView(APIView):
    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"email": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_url = f"https://agrilink-backend-hjzl.onrender.com/reset-password/{uidb64}/{token}/"
        subject = "Password Reset Request"
        message = render_to_string('password_reset_email.html', {
            'user': user,
            'reset_url': reset_url,
        })

        send_email(user, subject, message)

        return Response({"message": "Password reset email sent."}, status=status.HTTP_200_OK)

def send_email(user, subject, message):
    try:
        from_email = settings.EMAIL_HOST_USER
        to_email = [user.email]
        send_mail(
            subject,        # Email subject
            message,        # Email message body
            from_email,     # Sender email
            to_email, # List of recipient emails
            fail_silently=False,  # Don't suppress exceptions if the email fails to send
        )
    except Exception as e:
        print(f"Failed to send email: {str(e)}")  # Log the error or handle it appropriately

# Password Reset Confirm (Update password with token)
class PasswordResetConfirmView(APIView):
    def post(self, request, uidb64, token):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"uidb64": "Invalid token or user."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"token": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        # Update password if token is valid
        user.set_password(serializer.validated_data['password'])
        user.save()

        return Response({"message": "Password has been reset."}, status=status.HTTP_200_OK)
#END RESET PASSWORD VIEWS

#SPECIALISATION VIEWS
class AllSpecials(generics.ListAPIView):
    queryset = Specialisation.objects.all()
    serializer_class = SpecialSerializer
    pagination_class = None

@api_view(['GET'])
def FarmerSpecialisations(request, special_id):
    try:
     farmer = Profile.objects.filter(specialisation=special_id)
    except Profile.DoesNotExist():
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = ProfileSerializer(farmer, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# PROFILE VIEWS
class FarmerProfiles(generics.ListAPIView):
    queryset = Profile.objects.filter(is_farmer=True)
    serializer_class = ProfileSerializer

#retrieve user nested profile
@api_view(['GET'])
def UserProfile(request, user_id):
    try:
        user = User.objects.select_related('profile').get(id=user_id)
    except User.DoesNotExist:
         return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
def SingleProfile(request, user_id):
    try:
        user = Profile.objects.get(user=user_id)
    except Profile.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = ProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
#edit profile
class EditUserProfile(generics.UpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    lookup_field = 'user_id'  

    def update(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')  # Extract user_id from the URL
        try:
            # Get the Profile instance for the specific user_id
            instance = self.get_object()
        except Profile.DoesNotExist:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Update the instance with the provided data
        serializer = self.serializer_class(instance, data=request.data, partial=True)  
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#end profile view


#CROP VIEWS
#list crops
class ListCrops(generics.ListAPIView):
    queryset = Crop.objects.prefetch_related('ratings', 'crop_review').order_by('-date_added')
    serializer_class = CropSerializer

#post crops
class PostCrops(generics.ListCreateAPIView):
    queryset = Crop.objects.prefetch_related('ratings', 'crop_review')
    serializer_class = CropSerializer

#pagination

class CustomPagination(PageNumberPagination):
    page_size = 9  # Items per page
    page_size_query_param = 'page_size'
    max_page_size = 100

#list farmer crops
@api_view(['GET'])
def ListFarmerCrops(request, farmer_id):
    try:
        farmer = User.objects.prefetch_related(
            'crops',
            'crops__ratings', #ratings of the crop
            'crops__crop_review',
            # 'payment_method',
            # 'delivery_options'
            # 'crops__performance'
        ).get(id=farmer_id, is_farmer=True)
    except User.DoesNotExist:
        return Response({'detail': 'Farmer not found'}, status=status.HTTP_404_NOT_FOUND)

    # Order crops by date added in descending order (most recent first)
    crops = farmer.crops.order_by('-date_added')  

    paginator = CustomPagination()
    paginated_crops = paginator.paginate_queryset(crops, request)

    farmer_serializer = FarmerCropsSerializer(farmer)
    crops_serializer = CropfarmerSerializer(paginated_crops, many=True)

    response_data = farmer_serializer.data
    response_data['crops'] = crops_serializer.data  # Replace crops with paginated crops

    return paginator.get_paginated_response(response_data)

# def ListFarmerCrops(request, farmer_id):
#     # Fetch the crops based on the farmer_id
#     crops = Crop.objects.filter(user=farmer_id).select_related('specialisation').order_by('-date_added')
    
#     if not crops.exists():  # Check if there are no crops
#         return Response([], status=status.HTTP_404_NOT_FOUND)  # Return empty list with 404 if no crops

#     if request.method == 'GET':
#         # Initialize pagination
#         paginator = CustomPagination()
#         # Paginate the queryset
#         paginated_crops = paginator.paginate_queryset(crops, request)
#         # Serialize the paginated crops
#         serializer = CropfarmerSerializer(paginated_crops, many=True)
#         # Return paginated data
#         return paginator.get_paginated_response(serializer.data)
    
#delete farmer crop
class DeleteFarmerCrop(generics.RetrieveDestroyAPIView):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response("Deleted Successfully", status=status.HTTP_200_OK)
    
#edit crop
class UpdateFarmerCrop(generics.UpdateAPIView):
      queryset = Crop.objects.prefetch_related('ratings', 'crop_review')
      serializer_class = CropSerializer

      permission_classes = [AllowAny]
      parser_classes = [MultiPartParser, FormParser]

      def update(self, request, *args, **kwargs):
          instance = self.get_object()
          serializer = self.serializer_class(instance, data=request.data)
          serializer.is_valid(raise_exception=True)
          serializer.save()
          return Response(serializer.data, status=status.HTTP_201_CREATED)
      
#single crop detail
class CropDetail(generics.RetrieveAPIView):
    serializer_class = CropSerializer

    def get_queryset(self):
        # Prefetch reviews (ratings) ordered by the most recent first
        return Crop.objects.prefetch_related(
            Prefetch(
                'crop_review', 
                queryset=Review.objects.order_by('-timestamp')
            ),
            'ratings',  # Assuming this is another related field for reviews, adjust if necessary
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
#update quantity
class UpdateQuantity(APIView):
    serializer_class = CropSerializer

    def patch(self, request, *args, **kwargs):
        crop_id = kwargs.get('pk')
        availability = request.data.get('availability')

        try:
            crop = Crop.objects.get(pk=crop_id)
            crop.availability =  availability
            crop.save()
            
            serializer = self.serializer_class(crop)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Crop.DoesNotExist:
             return Response({'error': 'Not updated'}, status=status.HTTP_404_NOT_FOUND)  

#edit weight field
class UpdateWeight(generics.UpdateAPIView):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

    def patch(self, request, *args, **kwargs):
        crop = get_object_or_404(Crop, pk=kwargs.get('pk'))
        
        # Validate and update using the serializer
        serializer = self.serializer_class(crop, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#END CROP VIEWS

#ORDER CROP VIEWS
class PostOrderCrop(generics.CreateAPIView):
    queryset = OrderCrop.objects.all()
    serializer_class = OrderCropSerializer

#list farmer order crops
@api_view(['GET'])
def ListOrderFarmerCrops(request, farmer_id):
    try:
        farmer = User.objects.prefetch_related(
            'OrderCrop',
        ).get(id=farmer_id, is_farmer=True)
    except User.DoesNotExist:
        return Response({'detail': 'Farmer not found'}, status=status.HTTP_404_NOT_FOUND)

    crops = farmer.OrderCrop.all()
    serializer = OrderCropSerializer(crops, many=True)
    return Response(serializer.data)
    
#RATINGS VIEW

#post ratings
class PostRatings(generics.ListCreateAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

#update ratings
class UpdateRatings(generics.UpdateAPIView):
      queryset = Rating.objects.all()
      serializer_class = RatingSerializer

      permission_classes = [AllowAny]

      def update(self, request, *args, **kwargs):
          instance = self.get_object()
          serializer = self.serializer_class(instance, data=request.data)
          if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
#END RATINGS VIEW
          
# #CATEGORY VIEWS

# #post categories
# class PostCategories(generics.ListCreateAPIView):
#     queryset =  queryset = Category.objects.prefetch_related(
#         Prefetch(
#             'crop_category',
#             queryset=Crop.objects.select_related('user', 'category').prefetch_related('ratings', 'performance', 'crop_review')
#         )
#     )
#     serializer_class = CategorySerializer

# #list categories
# class AllCategories(generics.ListAPIView):
#     queryset = Category.objects.prefetch_related(
#         Prefetch(
#             'crop_category',
#             queryset=Crop.objects.select_related('user', 'category').prefetch_related('ratings', 'crop_review')
#         )
#     )
#     serializer_class = CategorySerializer
#     pagination_class = None  # Disable pagination by default

    
#END CATEGORY VIEWS


#REVIEW VIEWS

#post reviews
class PostReviews(generics.ListCreateAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

#list reviews
class AllReviews(generics.ListAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
#END REVIEW VIEWS

#NOTIFICATION VIEWS

#post notifications
class PostNotifications(generics.ListCreateAPIView):
    queryset =  Notification.objects.all()
    serializer_class = NotificationSerializer

#user notifications
@api_view(['GET'])
def UserNotification(request, user_id):
    try:
        user = User.objects.prefetch_related('notifications').get(id=user_id) #more corections
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
       serializer = UserNotificationSerializer(user)
       return Response(serializer.data, status=status.HTTP_200_OK)

#update is_read_field
class IsReadStatus(APIView):
    serializer_class = NotificationSerializer

    def patch(self, request, *args, **kwargs):
        notify_id = kwargs.get('pk')
        is_read = request.data.get('is_read')

        try:
            notify = Notification.objects.get(pk=notify_id)
            notify.is_read = is_read
            notify.save()

            serializer = self.serializer_class(notify)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
             return Response({'error': 'Not updated'}, status=status.HTTP_404_NOT_FOUND)
#END NOTIFICATION VIEWS

#DISCOUNT VIEWS

#post discounts
class PostDiscount(generics.ListCreateAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer

#edit discount
class EditDiscount(generics.UpdateAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

# single discount
class singleDiscount(generics.RetrieveAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
#all discounts
class AllDiscounts(generics.ListAPIView):
    queryset = Discount.objects.filter(active=True)
    serializer_class = DiscountSerializer
    pagination_class = None 

#END DISCOUNT VIEW
        
#ORDER VIEWS

#post orders
class PostOrders(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

#list buyer orders
@api_view(['GET'])
def UserOrder(request, user_id):
    try:
        orders = Order.objects.filter(user=user_id).select_related(
            'address'
        ).prefetch_related(
            'order_detail__crop'  # Prefetch crops related to order details
        ).order_by('-created_at')  # Order by latest first
    except Order.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = MadeOrderSerializer(orders, many=True)  # Serialize multiple orders
        return Response(serializer.data, status=status.HTTP_200_OK)

# Update order status
class UpdateStatus(APIView):
    serializer_class = OrderSerializer

    def patch(self, request, *args, **kwargs):
        order_id = kwargs.get('pk')
        new_status = request.data.get('status')

        try:
            with transaction.atomic():  # Use atomic transaction for data consistency
                order = Order.objects.get(pk=order_id)
                order.status = new_status
                order.save()

                serializer = self.serializer_class(order)

                order_user = order.user
                devices = FCMDevice.objects.filter(user=order_user)  # Get all devices for user

                notification_title = "AgriLink"
                notification_body = f"{order_user.get_full_name}, your Order has been {order.status}"

                # Send notification to all devices of the user
                for device in devices:
                    try:
                        send_push_notification(device.registration_id, notification_title, notification_body)
                    except Exception as e:
                        # Log error more formally
                        # logger.error(f"Failed to send push notification to {device.registration_id}: {e}")
                        return Response({"error": "Failed to send notification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Save notification in database
                Notification.objects.create(
                    user=order_user,
                    message=notification_body
                )

                return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

#  single order 
class SingleOrder(generics.RetrieveAPIView):
    queryset = (
        Order.objects.select_related('address')  # Optimize foreign key 'address'
        .prefetch_related(
            'order_detail__crop',  # Optimize many-to-many 'crop' in 'order_detail'
            'payment',  # Optimize related 'payment'
        )
    )
    serializer_class = OrderSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

#farmer orders
@api_view(['GET'])
def orders_for_farmer(request, farmer_id):
    try:
        farmer = User.objects.get(pk=farmer_id)
        farmer_crops = OrderCrop.objects.filter(user=farmer)
        
        # Fetch unique orders for the crops, ordered by creation date
        orders = Order.objects.filter(order_detail__crop__in=farmer_crops).distinct().order_by('-created_at')
        
        orders_data = []
        for order in orders:
            order_details = OrderDetail.objects.filter(order=order).prefetch_related('crop')
            
            crops_data = []
            for detail in order_details:
                for crop in detail.crop.all():
                    crops_data.append({
                        "crop_name": crop.crop_name,
                        "quantity": crop.quantity,
                        "price_per_unit": crop.price_per_unit,
                        "unit": crop.unit,
                        "image": crop.image.url if crop.image else None,
                    })

            # Fetch payment details for the order
            payment_details = PaymentDetails.objects.filter(order=order).first()
            
            orders_data.append({
                "order_id": order.id,
                "buyer_name": order.user.get_full_name,
                "status": order.status,
                "city": order.address.city if order.address else "No city provided",
                "contact": order.address.contact if order.address else "No contact",
                "district": order.address.district if order.address else "No district provided",
                "delivery_Option":order.delivery_option,
                "crops": crops_data,
                "payment_method":order.payment_method,
                "payment": {
                    "amount": payment_details.amount if payment_details else "No",
                    "provider": payment_details.network if payment_details else "No provider",
                    "status": payment_details.status if payment_details else "none",
                },
                "created_at": order.created_at,
            })

        return Response({
            "farmer": farmer.get_full_name,
            "orders": orders_data
        })

    except User.DoesNotExist:
        return Response({"error": "Farmer not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


#daily order trends
@api_view(['GET'])
def daily_order_trends(request, farmer_id):
    try:
        # Fetch the farmer
        farmer = User.objects.get(pk=farmer_id)

        # Get the date the user joined
        user_joined_date = farmer.date_joined.date()

        # Get the current date
        today = timezone.now().date()

        # Fetch orders for the farmer from the date they joined until today
        orders = Order.objects.filter(
            order_detail__crop__user=farmer,
            created_at__date__range=[user_joined_date, today]  # Use `date__range` for date filtering
        ).distinct()

        # Aggregate orders by day
        daily_trends = defaultdict(int)
        for order in orders:
            order_date = order.created_at.date()  # Extract the date part
            daily_trends[order_date] += 1

        # Generate a list of all dates from the user's join date to today
        all_dates = []
        current_date = user_joined_date
        while current_date <= today:
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Build the daily trends data, ensuring every day is included
        trends_data = []
        for date in all_dates:
            trends_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "count": daily_trends.get(date, 0)  # Default to 0 if no orders on that day
            })

        # Group daily trends by month
        monthly_trends = defaultdict(list)
        for trend in trends_data:
            month_key = datetime.strptime(trend["date"], "%Y-%m-%d").strftime("%B %Y")  # e.g., "February 2025"
            monthly_trends[month_key].append(trend)

        # Convert the monthly trends to a list of {month: month, daily_trends: daily_trends} objects
        monthly_trends_data = [
            {"month": month, "daily_trends": daily_trends}
            for month, daily_trends in sorted(monthly_trends.items())
        ]

        return Response({
            "farmer": farmer.get_full_name,
            "date_joined": user_joined_date.strftime("%Y-%m-%d"),
            "monthly_trends": monthly_trends_data
        })

    except User.DoesNotExist:
        return Response({"error": "Farmer not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

#delete order
class DeleteOrder(generics.RetrieveDestroyAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response("Deleted Successfully", status=status.HTTP_200_OK)

#ORDER DETAIL VIEW

#Post order detail
class PostOrderDetail(generics.ListCreateAPIView):
    queryset = OrderDetail.objects.all()
    serializer_class = OrderDetailSerailizer
    
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create the order detail
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                order_detail = serializer.save()

                # Collect unique farmers for this order detail
                farmers = set()
                for crop in order_detail.crop.all():
                    farmers.add(crop.user)

                # Send notifications to all relevant farmers
                for farmer in farmers:
                    # Get all devices for this farmer
                    devices = FCMDevice.objects.filter(user=farmer)
                    notification_title = "AgriLink"
                    notification_body = f"Yo yo {farmer.get_full_name}, One of your products has been ordered. Check your orders."

                    # Debugging: Print farmer and devices
                    print(f"Sending notifications to farmer: {farmer.get_full_name}")
                    print(f"Devices found: {devices.count()}")

                    # Send notification to all devices of the farmer
                    for device in devices:
                        print(f"Sending notification to device: {device.registration_id}")
                        try:
                            success = send_push_notification(device.registration_id, notification_title, notification_body)
                            if not success:
                                print(f"Failed to send notification to device: {device.registration_id}")
                        except Exception as e:
                            print(f"Failed to send notification: {e}")
                            return Response({"error": f"Failed to send notification to farmer {farmer.get_full_name}: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    # Save notification in the database
                    Notification.objects.create(
                        user=farmer,
                        message=notification_body
                    )

                # Return the created order detail
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"Error in create method: {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

#END ORDER DETAIL VIEW

#PAYMENT DETAIL VIEW

#post paymentDetails
class PostPaymentDetails(generics.ListCreateAPIView):
    queryset = PaymentDetails.objects.all()
    serializer_class = PaymentDetailSerializer
#END PAYMENT DETAIL VIEW

#USER ADDRESS VIEW

#Post useraddress
class PostUserAddress(generics.ListCreateAPIView):
    queryset = UserAddress.objects.all()
    serializer_class = UserAddressSerializer

@api_view(['GET'])
def ListUserAddress(request, user_id):
    try:
      user = User.objects.prefetch_related('useraddress').get(id=user_id)
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = UserAddresses(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# edit userAddress
class EditUserAddress(generics.UpdateAPIView):
    queryset = UserAddress.objects.all()
    serializer_class = UserAddressSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

# edit active
class UpdateActive(APIView):
    serializer_class = UserAddressSerializer

    def patch(self, request, *args, **kwargs):
        address_id = kwargs.get('pk')
        active = request.data.get('active')

        try:
            address = UserAddress.objects.get(pk=address_id)
            address.active = active
            address.save()
            
            serializer = self.serializer_class(address)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserAddress.DoesNotExist:
             return Response({'error': 'Not updated'}, status=status.HTTP_404_NOT_FOUND)
        
# edit active addresses
class EditActiveAddresses(APIView):
    def put(self, request):
        # If no address ID is provided, deactivate all addresses
        if not request.data.get('id'):
            UserAddress.objects.update(active=False)
            return Response({"message": "All addresses deactivated."}, status=status.HTTP_200_OK)
        
        # If an ID is provided, make sure only that address is active
        address_id = request.data.get('id')
        try:
            address = UserAddress.objects.get(id=address_id)
            UserAddress.objects.update(active=False)  # Deactivate all
            address.active = True
            address.save()
            return Response({"message": "Address set as active."}, status=status.HTTP_200_OK)
        except UserAddress.DoesNotExist:
            return Response({"error": "Address not found."}, status=status.HTTP_404_NOT_FOUND)
        
#END USER ADDRESS VIEW

#CHANGE PASSWORD VIEW

# change password
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def put(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.update(user, serializer.validated_data)
            return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ====================================MARKET INSIGHTS ==========================================================#

#CROP PERFOMANCE VIEW

# Post crop performance (Create)
class PostCropPerformanceView(generics.ListCreateAPIView):
    queryset = CropPerformance.objects.all()
    serializer_class = CropPerformanceSerializer

#monthly daily  sales
@api_view(['GET'])
def DailyMonthlySalesView(request, crop_id, farmer_id):
    try:
        # Fetch the crop
        crop = Crop.objects.get(pk=crop_id)

        # Fetch the farmer
        farmer = User.objects.get(pk=farmer_id)

        # Get the date the user joined
        user_joined_date = farmer.date_joined.date()

        # Get the current date
        today = timezone.now().date()

        # Fetch payment details for the farmer's crop from the date they joined until today
        payments = PaymentDetails.objects.filter(
            crop__id=crop_id,  # Filter by crop_id
            created_at__date__range=[user_joined_date, today]
        ).distinct()

        # Aggregate sales by day
        daily_sales = defaultdict(float)
        for payment in payments:
            payment_date = payment.created_at.date()  # Extract the date part
            total_amount = sum(item["amount"] for item in payment.amount)  # Sum amounts in the JSONField
            daily_sales[payment_date] += total_amount

        # Generate a list of all dates from the user's join date to today
        all_dates = []
        current_date = user_joined_date
        while current_date <= today:
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Build the daily sales data, ensuring every day is included
        sales_data = []
        for date in all_dates:
            sales_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "amount": daily_sales.get(date, 0.0)  # Default to 0.0 if no sales on that day
            })

        # Group daily sales by month
        monthly_sales = defaultdict(list)
        for sale in sales_data:
            month_key = datetime.strptime(sale["date"], "%Y-%m-%d").strftime("%B %Y")  # e.g., "February 2025"
            monthly_sales[month_key].append(sale)

        # Convert the monthly sales to a list of {month: month, daily_sales: daily_sales} objects
        monthly_sales_data = [
            {"month": month, "daily_sales": daily_sales}
            for month, daily_sales in sorted(monthly_sales.items(), key=lambda x: datetime.strptime(x[0], "%B %Y"))
        ]

        return Response({
            "crop": crop.crop_name,
            "monthly_sales": monthly_sales_data
        })

    except Crop.DoesNotExist:
        return Response({"error": "Crop not found"}, status=status.HTTP_404_NOT_FOUND)
    except User.DoesNotExist:
        return Response({"error": "Farmer not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#monthly sales  
class MonthlySalesView(APIView):
    def get(self, request, crop_id):
        current_year = timezone.now().year
        current_month = timezone.now().month

        # Fetch payment details for the specified crop_id
        payments = PaymentDetails.objects.filter(crop__id=crop_id).annotate(
            month=ExtractMonth('created_at'),
            year=ExtractYear('created_at')
        ).filter(
            Q(year=current_year, month__lte=current_month) | Q(year=current_year - 1)
        )

        # Initialize data structure for aggregation
        monthly_data = {}

        # Process each payment record
        for payment in payments:
            year = payment.year
            month = payment.month
            key = f"{year}-{month}"

            if key not in monthly_data:
                monthly_data[key] = {
                    "year": year,
                    "month": month,
                    "total_quantity": 0,
                    "total_amount": 0.0
                }

            # Extract amount and quantity for the specific crop_id from JSON
            amount_list = payment.amount  # List of {"id": crop_id, "amount": value}
            quantity_list = payment.quantity  # List of {"id": crop_id, "quantity": value}

            for amount_entry in amount_list:
                if str(amount_entry.get("id")) == str(crop_id):
                    monthly_data[key]["total_amount"] += float(amount_entry.get("amount", 0))

            for quantity_entry in quantity_list:
                if str(quantity_entry.get("id")) == str(crop_id):
                    monthly_data[key]["total_quantity"] += int(quantity_entry.get("quantity", 0))

        # Prepare data for the current year up to the current month
        data = []
        for month in range(1, current_month + 1):
            key = f"{current_year}-{month}"
            record = {
                "year": current_year,
                "month": month,
                "total_quantity": monthly_data.get(key, {}).get("total_quantity", 0),
                "total_amount": monthly_data.get(key, {}).get("total_amount", 0.0),
            }
            data.append(record)

        # Include previous year's data for months from the current month to December
        for month in range(current_month, 13):
            key = f"{current_year - 1}-{month}"
            if key in monthly_data:
                data.append({
                    "year": current_year - 1,
                    "month": month,
                    "total_quantity": monthly_data[key]["total_quantity"],
                    "total_amount": monthly_data[key]["total_amount"],
                })

        # Sort the data by year and month
        data.sort(key=lambda x: (x['year'], x['month']))

        return Response(data)
    
#END CROP PERFOMANCE VIEW

#MARKET TREND VIEW

# Get Aggregated Market Insights
class MarketInsights(generics.ListAPIView):
    serializer_class = MarketTrendSerializer
    pagination_class = None 

    def get_queryset(self):
        farmer_id = self.kwargs.get('farmer_id')
        try:
            # Get the user (farmer) by ID
            farmer = User.objects.get(id=farmer_id, is_farmer=True)
            # Filter crops that belong to this farmer
            crops = Crop.objects.filter(user=farmer)
            # Now filter market trends for these crops
            return MarketTrend.objects.filter(crop__in=crops)
        except User.DoesNotExist:
            # If the farmer does not exist, return an empty queryset
            return MarketTrend.objects.none()

class MarketTrendView(generics.ListCreateAPIView):
    queryset = MarketTrend.objects.all()
    serializer_class = MarketTrendSerializer

#market insights
@api_view(['GET'])
def crop_market_insights(request, crop_id):
    #Retrieve aggregated insights for a specific crop's market trends.
    try:
        market_trend = MarketTrend.objects.select_related('crop').filter(crop_id=crop_id).first()
        if not market_trend:
            return Response({"error": "Crop not found or no market trends available."}, 
                            status=status.HTTP_404_NOT_FOUND)

        serializer = MarketTrendSerializer(market_trend)

        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#END MARKET TREND VIEWS

#USER INTERACTIONS VIEWS

#crop_actions for the crop
@api_view(['GET'])
def GetCropActions(request, crop_id):
    try:
        cropAction = UserInteractionLog.objects.filter(crop=crop_id).order_by('-timestamp')
    except UserInteractionLog.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = UserInteractionLogSerializer(cropAction, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# user interaction logs
# @api_view(['GET'])
# def crop_actions(request, crop_id):
#     try:
#         # Get current year and month
#         current_year = datetime.now().year
#         current_month = datetime.now().month

#         # Fetch interaction data
#         crop_interactions = UserInteractionLog.objects.filter(crop_id=crop_id) \
#             .annotate(
#                 month=ExtractMonth('timestamp'),
#                 year=ExtractYear('timestamp')
#             ) \
#             .values('year', 'month') \
#             .annotate(
#                 views=Count('id', filter=Q(action='view')),
#                 purchases=Count('id', filter=Q(action='purchase'))
#             )

#         # Convert interactions to dictionary for quick lookup
#         existing_data = {f"{interaction['year']}-{interaction['month']}": interaction for interaction in crop_interactions}

#         # Prepare data with defaults for current year up to current month
#         monthly_data = []
#         for month in range(1, current_month + 1):  # Only up to the current month
#             key = f"{current_year}-{month}"
#             record = {
#                 "year": current_year,
#                 "month": month,
#                 "views": 0,
#                 "purchases": 0
#             }
#             if key in existing_data:
#                 record.update({
#                     "views": existing_data[key]["views"] or 0,
#                     "purchases": existing_data[key]["purchases"] or 0
#                 })
#             monthly_data.append(record)

#         # Include last year's data for the months that match or exceed the current month
#         for month in range(current_month, 13):  # From current month to December of last year
#             key = f"{current_year - 1}-{month}"
#             if key in existing_data:
#                 monthly_data.append({
#                     "year": current_year - 1,
#                     "month": month,
#                     "views": existing_data[key]["views"] or 0,
#                     "purchases": existing_data[key]["purchases"] or 0
#                 })

#         # Sort by date
#         monthly_data.sort(key=lambda x: (x['year'], x['month']))

#         if not monthly_data:
#             return Response(status=status.HTTP_404_NOT_FOUND)

#         return Response({
#             'monthly_stats': monthly_data
#         }, status=status.HTTP_200_OK)

#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
#END USER INTERACTION VIEWS

#=================================================================================================#
#Payment options
class PostPaymentMethod(generics.CreateAPIView):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer

#list payment methods
@api_view(['GET'])
def ListPaymentMethods(request, user_id):
    try:
        user = User.objects.prefetch_related('payment_method', 'profile').get(id=user_id)
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = UserPayMethods(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

#edit payment
class EditPaymentMethods(generics.UpdateAPIView):
      queryset = PaymentMethod.objects.all()
      serializer_class = PaymentMethodSerializer

      def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
          
   
#DELIVERY OPTIONS
class PostDeliveryOptions(generics.CreateAPIView):
    queryset = DeliveryOption.objects.all()
    serializer_class = DeliverySerializer


#list delivery options
@api_view(['GET'])
def ListDeliveryOptions(request, user_id):
   try:
        user = User.objects.prefetch_related('delivery_options', 'profile').get(id=user_id)
   except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
   if request.method == 'GET':
        serializer = UserDeliveryMethods(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

#edit delivery option
class UpdateDeliveryOption(generics.UpdateAPIView):
    queryset = DeliveryOption.objects.all()
    serializer_class = DeliverySerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
#========================================================================================#
#flutter wave payment
@api_view(['POST'])
def initiate_mobile_money_payment(request):
    if request.method != 'POST':
        return Response({"error": "Invalid request method"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = request.data  
    
    required_fields = ['amount', 'email', 'phone_number', 'fullname', 'tx_ref', 'order', 'network']
    if not all(field in data for field in required_fields):
        return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

    amount_data = data['amount']  # This is a list of objects: [{id: 3, amount: 2000}, {id: 2, amount: 6000}, {id: 1, amount: 5000}]
    email = data['email']
    phone_number = data['phone_number']
    fullname = data['fullname']
    tx_ref = data['tx_ref']
    order_id = data['order']
    network = data['network']
    quantity = data['quantity']
    crop_ids = data.get('crop', [])  # Assuming `crop` is a list of crop IDs

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        order_crop = OrderCrop.objects.filter(orderdetail__order=order).first()
        if not order_crop:
            return Response({"error": "No crops associated with this order"}, status=status.HTTP_404_NOT_FOUND)
    
        farmer = order_crop.user
        farmer_payment_method = PaymentMethod.objects.get(user=farmer)
        farmer_phone_number = farmer_payment_method.contact_phone
        farmer_name = farmer_payment_method.contact_name
    except PaymentMethod.DoesNotExist:
        return Response({"error": "Payment method for farmer not found"}, status=status.HTTP_404_NOT_FOUND)

    # Calculate the total amount by summing up the amounts from the list
    total_amount = sum(item['amount'] for item in amount_data)

    # Calculate commission and farmer amount
    commission = total_amount * 0.075  # 7.5% commission
    farmer_amount = total_amount - commission

    headers = {
        "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    charge_payload = {
        "tx_ref": tx_ref,
        "amount": str(total_amount),  # Use the total amount here
        "currency": "UGX",
        "payment_options": "mobilemoneyuganda",
        "redirect_url": "https://agrilink-backend-hjzl.onrender.com/buyer/payment-callback/",
        "customer": {
            "email": email,
            "phone_number": phone_number,
            "name": fullname
        },
        "customizations": {
            "title": "Farmers Platform",
            "description": "Payment for farm products",
            "logo": "https://yourwebsite.com/logo.png"
        }
    }

    try:
        with transaction.atomic():
            # Step 1: Charge the buyer
            charge_response = requests.post("https://api.flutterwave.com/v3/payments", json=charge_payload, headers=headers)
            if charge_response.status_code != 200:
                raise Exception(f"Charge failed: {charge_response.text}")

            charge_data = charge_response.json()
            if charge_data['status'] != 'success':
                raise Exception(f"Payment initiation failed: {charge_data['message']}")

            # Step 2: Transfer to farmer
            transfer_payload = {
                "account_bank": network,
                "account_number": farmer_phone_number,
                "amount": farmer_amount,
                "currency": "UGX",
                "beneficiary_name": farmer_name,
                "reference": f"{tx_ref}_farmer",
                "narration": "Payment for farm products",
                "debit_currency": "UGX"
            }
            transfer_response = requests.post("https://api.flutterwave.com/v3/transfers", json=transfer_payload, headers=headers)
            if transfer_response.status_code != 200:
                raise Exception(f"Transfer to farmer failed: {transfer_response.text}")

            transfer_data = transfer_response.json()
            if transfer_data['status'] != 'success':
                raise Exception(f"Transfer to farmer failed: {transfer_data['message']}")

            # Step 3: Transfer the commission
            commission_payload = {
                "account_bank": "AIRTEL",  # Replace with your actual bank code
                "account_number": "+256759079867",  # Replace with your actual account number
                "amount": commission,
                "currency": "UGX",
                "beneficiary_name": "AgriLink",
                "reference": f"{tx_ref}_commission",
                "narration": "Platform commission",
                "debit_currency": "UGX"
            }
            commission_response = requests.post("https://api.flutterwave.com/v3/transfers", json=commission_payload, headers=headers)
            if commission_response.status_code != 200:
                raise Exception(f"Commission transfer failed: {commission_response.text}")

            commission_data = commission_response.json()
            if commission_data['status'] != 'success':
                raise Exception(f"Commission transfer failed: {commission_data['message']}")

            # All steps completed successfully, now update database
            payment_details = PaymentDetails.objects.create(
                amount=amount_data,  # Use the total amount here
                email=email,
                phone_number=phone_number,
                fullname=fullname,
                tx_ref=tx_ref,
                order=order,
                network=network,
                quantity=quantity,
                status="successful"
            )

            # Assign crops to the payment_details object using .set()
            payment_details.crop.set(crop_ids)

            return Response({
                "message": "Payment processed successfully",
                "charge_response": charge_data,
                "transfer_response": transfer_data,
                "commission_response": commission_data
            }, status=status.HTTP_200_OK)

    except Exception as e:
        # Log the error for debugging and manual intervention if needed
        print(f"Payment processing error: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

#get payment details
class GetPaymentDetails(generics.ListAPIView):
    queryset = PaymentDetails.objects.all()
    serializer_class = PaymentDetailSerializer

#daily sales trend
@api_view(['GET'])
def daily_sales_trends(request, farmer_id):
    try:
        # Fetch the farmer
        farmer = User.objects.get(pk=farmer_id)

        # Get the date the user joined
        user_joined_date = farmer.date_joined.date()

        # Get the current date
        today = timezone.now().date()

        # Fetch payment details for the farmer's crops from the date they joined until today
        payments = PaymentDetails.objects.filter(
            crop__user=farmer,  # Assuming `Crop` has a `user` field
             created_at__date__range=[user_joined_date, today]
        ).distinct()

        # Aggregate sales by day
        daily_sales = defaultdict(float)
        for payment in payments:
            payment_date = payment.created_at.date()  # Extract the date part
            total_amount = sum(item["amount"] for item in payment.amount)  # Sum amounts in the JSONField
            daily_sales[payment_date] += total_amount

        # Generate a list of all dates from the user's join date to today
        all_dates = []
        current_date = user_joined_date
        while current_date <= today:
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Build the daily sales data, ensuring every day is included
        sales_data = []
        for date in all_dates:
            sales_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "amount": daily_sales.get(date, 0.0)  # Default to 0.0 if no sales on that day
            })

        # Group daily sales by month
        monthly_sales = defaultdict(list)
        for sale in sales_data:
            month_key = datetime.strptime(sale["date"], "%Y-%m-%d").strftime("%B %Y")  # e.g., "February 2025"
            monthly_sales[month_key].append(sale)

        # Convert the monthly sales to a list of {month: month, daily_sales: daily_sales} objects
        monthly_sales_data = [
            {"month": month, "daily_sales": daily_sales}
            for month, daily_sales in sorted(monthly_sales.items())
        ]

        return Response({
            "farmer": farmer.get_full_name,
            "date_joined": user_joined_date.strftime("%Y-%m-%d"),
            "monthly_sales": monthly_sales_data
        })

    except User.DoesNotExist:
        return Response({"error": "Farmer not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

# sales by crop
@api_view(['GET'])
def monthly_sales_trends_by_crop(request, farmer_id):
    try:
        # Fetch the farmer
        farmer = User.objects.get(pk=farmer_id)

        # Get the date the user joined
        user_joined_date = farmer.date_joined.date()

        # Get the current date
        today = timezone.now().date()

        # Fetch payment details for the farmer's crops from the date they joined until today
        payments = PaymentDetails.objects.filter(
            crop__user=farmer,  # Assuming `Crop` has a `user` field
            created_at__date__range=[user_joined_date, today]
        ).distinct()

        # Aggregate sales by crop and by month
        crop_sales = defaultdict(lambda: defaultdict(float))
        for payment in payments:
            payment_month = payment.created_at.date().replace(day=1)  # Group by month
            for crop in payment.crop.all():
                total_amount = sum(item["amount"] for item in payment.amount)  # Sum amounts in the JSONField
                crop_sales[crop.crop_name][payment_month] += total_amount

        # Generate a list of all months from the user's join date to the current month
        all_months = []
        current_month = user_joined_date.replace(day=1)
        while current_month <= today.replace(day=1):
            all_months.append(current_month)
            # Move to the next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)

        # Build the monthly sales data for each crop
        sales_data = []
        for crop_name, monthly_sales in crop_sales.items():
            crop_trends = []
            for month in all_months:
                crop_trends.append({
                    "month": month.strftime("%B %Y"),  # e.g., "February 2025"
                    "amount": monthly_sales.get(month, 0.0)  # Default to 0.0 if no sales in that month
                })
            sales_data.append({
                "crop_name": crop_name,
                "monthly_sales": crop_trends
            })

        return Response({
            "farmer": farmer.get_full_name,
            "date_joined": user_joined_date.strftime("%Y-%m-%d"),
            "crop_sales": sales_data
        })

    except User.DoesNotExist:
        return Response({"error": "Farmer not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)