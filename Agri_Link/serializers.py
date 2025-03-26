from .models import *
from rest_framework import serializers
from rest_framework_simplejwt.tokens import Token
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode

#your serializers
 
#paymentDetails
class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetails
        fields = ['id', 'order', 'amount', 'quantity', 'network', 'status', 'crop', 'created_at']

#userAddress
class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ['id', 'user', 'city', 'district','contact', 'active', 'timestamp']

class UserAddresses(serializers.ModelSerializer):
    useraddress = UserAddressSerializer(read_only=True, many=True)
    class Meta:
        model = User
        fields = ['id', 'get_full_name', 'useraddress']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'is_buyer', 'is_farmer', 'date_joined','username', 'get_full_name', 'fcm_token']

class ObtainSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['is_buyer'] = user.is_buyer
        token['is_farmer'] = user.is_farmer
        token['username'] = user.username
        token['email'] = user.email 

        return token

# buyer registration
class BuyerRegistration(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Buyer
        fields = ['id', 'FullName', 'Email', 'contact', 'is_buyer','password', 'confirm_password']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data
    
    def create(self, validated_data):
        user_data = {
            'username': validated_data['contact'],
            'email': validated_data['Email'], 
             'is_buyer':validated_data.get('is_buyer', False),
        }


    # Check if a user with the same username exists
        if User.objects.filter(username=user_data['username']).exists():
           raise serializers.ValidationError(
                {"contact": "A user with this contact number already exists."}
        )

        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        user = User.objects.create(**user_data)
        user.set_password(password)
        user.save()

        buyer = Buyer.objects.create(
            user=user,
            FullName=validated_data['FullName'],
            Email=validated_data['Email'],
            contact=validated_data['contact'],
            is_buyer = validated_data.get('is_buyer', False),
        )
        
        # Send welcome email
        # self.send_welcome_email(student)
        
        return buyer
    
# farmer registration
class FarmerRegistration(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Farmer
        fields = ['id', 'FullName', 'Email', 'contact','is_farmer', 'password', 'confirm_password']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data
    
    def create(self, validated_data):
        user_data = {
            'username': validated_data['contact'],
            'email': validated_data['Email'], 
             'is_farmer':validated_data.get('is_farmer', False),
        }

    # Check if a user with the same username exists
        if User.objects.filter(username=user_data['username']).exists():
           raise serializers.ValidationError(
                {"contact": "A user with this contact number already exists."}
        )

        password = validated_data.pop('password')
        validated_data.pop('confirm_password')
        user = User.objects.create(**user_data)
        user.set_password(password)
        user.save()

        farmer = Farmer.objects.create(
            user=user,
            FullName=validated_data['FullName'],
            Email=validated_data['Email'],
            contact=validated_data['contact'],
            is_farmer = validated_data.get('is_farmer', False),
        )
        
        # Send welcome email
        # self.send_welcome_email(student)

        return farmer
    
#RESET PASSWORD
#login password
class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    uidb64 = serializers.CharField(write_only=True, required=True)  # User ID encoded in base64
    token = serializers.CharField(write_only=True, required=True)  # Reset token

    class Meta:
        model = User
        fields = ('password', 'password2', 'uidb64', 'token')

    def validate(self, attrs):
        # Check if the new password and its confirmation match
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        # Decode user ID from uidb64 and check token validity
        try:
            uid = urlsafe_base64_decode(attrs['uidb64']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": "Invalid user."})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Invalid or expired token."})

        attrs['user'] = user  # Add user to attrs for later use
        return attrs

    def save(self, **kwargs):
        # Reset the user's password
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.save()
        return user

#farmer
class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = ['id', 'user', 'FullName', 'Email', 'contact'] 

#specialisation
class SpecialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialisation
        fields = ['id', 'name']
# profiles
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id', 'user','image','location', 'bio', 'farmName','farm_Image', 'timestamp', 'is_buyer', 'is_farmer', 'specialisation']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['specialisation'] = SpecialSerializer(instance.specialisation.all(), many=True).data
        return response

class UserProfileSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'email','is_buyer', 'is_farmer','username','get_full_name', 'profile']
# end profiles

#notifications
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user','message', 'timestamp', 'is_read']

class UserNotificationSerializer(serializers.ModelSerializer):
    notifications = NotificationSerializer(many=True, read_only=True)
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'notifications']
#end notifications

#ratings
class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'user', 'crop', 'value']

#reviews
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'user','message','profile','crop', 'timestamp']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        # Serialize the profile
        profile_data = ProfileSerializer(instance.profile).data
        user_data = UserSerializer(instance.user).data

        # Remove some fields from the profile data
        profile_data.pop('specialisation', None)
        profile_data.pop('location', None)
        profile_data.pop('bio', None)
        profile_data.pop('farmName', None)
        profile_data.pop('is_buyer', None)
        profile_data.pop('is_farmer', None)
        
        #remove some fields from user
        user_data.pop('email', None)
        user_data.pop('is_buyer', None)
        user_data.pop('is_farmer', None)
        user_data.pop('date_joined', None)
        user_data.pop('username', None)

        response['profile'] = profile_data
        response['user'] = user_data
        return response

#crop Perfomance
class CropPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropPerformance
        fields = ['id', 'orderCrop','get_crop_revenue', 'date','get_quantity_sold']

#farmer crop serializer
class CropfarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = ['id', 'user','crop_name', 'description', 'weight','unit', 'price_per_unit', 'availability', 'InitialAvailability', 'image','date_added','quantity', 'specialisation', 'get_average_rating', 'get_discounted_price']

#crops
class CropSerializer(serializers.ModelSerializer):
    ratings = RatingSerializer(many=True, read_only=True) #serialize related ratings
    crop_review = ReviewSerializer(many=True, read_only=True)
    # performance = CropPerformanceSerializer(many=True, read_only=True)
    class Meta:
        model = Crop
        fields = ['id', 'user','crop_name', 'description', 'weight','price_per_unit','unit','availability','InitialAvailability', 'image','date_added','quantity', 'ratings','specialisation', 'crop_review', 'get_average_rating', 'get_discounted_price']
    
#order crops
class OrderCropSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderCrop
        fields = ["id", "user", "buyer_id", "crop", "crop_name", "weights", "unit", "price_per_unit", "image", "quantity", "get_discounted_price"]

#farmerCrops
class FarmerCropsSerializer(serializers.ModelSerializer):
    crops = CropSerializer(many=True, read_only=True) #serialize related crops
    class Meta:
        model = User
        fields = ['id', 'email', 'is_buyer', 'is_farmer', 'crops']
   
#discount
class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ['id', 'description', 'discount_percent', 'crop','orderCrop', 'active']

#order detail
class OrderDetailSerailizer(serializers.ModelSerializer):
    class Meta:
        model = OrderDetail
        fields = ['id', 'order', 'crop']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['crop'] = OrderCropSerializer(instance.crop.all(), many=True).data
        return response

#orders
class OrderSerializer(serializers.ModelSerializer):
    order_detail = OrderDetailSerailizer(many=True, read_only=True)
    payment = PaymentDetailSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'modified_at', 'status', 'address','payment','order_detail', 'delivery_option', 'payment_method']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['address'] = UserAddressSerializer(instance.address).data
        return response
    
#userorder
class UserOrderSerializer(serializers.ModelSerializer):
    orders = OrderSerializer(many=True, read_only=True)
    class Meta:
        model = User
        fields = ['id', 'email', 'orders']

#made user orders
class AllUserOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'user', 'created_at', 'modified_at', 'status', 'address']

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['address'] = UserAddressSerializer(instance.address).data
        return response
    
class MadeOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'user', 'address', 'created_at', 'payment_method', 'delivery_option', 'status']
    
    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['address'] = UserAddressSerializer(instance.address).data
        return response
#end made user orders

# change password
class ChangePasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    old_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('old_password', 'password', 'password2')

    def validate(self, attrs):
        # Check if the new password and its confirmation match
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        # Verify that the provided old password matches the user's current password
        if not user.check_password(value):
            raise serializers.ValidationError({"old_password": "Old password is not correct"})
        return value

    def update(self, instance, validated_data):
        user = self.context['request'].user

        # make sure user is only able to update their own password
        if user.pk != instance.pk:
            raise serializers.ValidationError({"authorize": "You don't have permission for this user."})

        # Set the new password for the user instance
        instance.set_password(validated_data['password'])
        instance.save()

        return instance


#market trends
class MarketTrendSerializer(serializers.ModelSerializer):
    average_price_per_kg = serializers.SerializerMethodField()
    farmer_pricing = serializers.SerializerMethodField()
    crop_name = serializers.CharField(source='crop.crop_name', read_only=True)

    class Meta:
        model = MarketTrend
        fields = ['id', 'crop', 'updated_at', 'average_price_per_kg', 'farmer_pricing', 'crop_name']

    def get_average_price_per_kg(self, obj):
        return obj.average_price_per_kg

    def get_farmer_pricing(self, obj):
        return obj.farmer_pricing

#user interaction logging
class UserInteractionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInteractionLog
        fields = ['id', 'crop', 'action',  'monthly_stats', 'timestamp']

#Email serializer
class EmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailIntiation
        fields = '__all__'

# =================================================================== #
#Payment Options
class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "user", "methodType", "contact_name", "contact_email" ,"contact_phone"]

#user payment methods
class UserPayMethods(serializers.ModelSerializer):
    payment_method = PaymentMethodSerializer(read_only=True, many=True)
    profile = ProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'payment_method', 'profile']

#delivery options
class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOption
        fields = ["id", "user","name", "fee", "duration"]

#user delivery
class UserDeliveryMethods(serializers.ModelSerializer):
    delivery_options = DeliverySerializer(read_only=True, many=True)
    profile = ProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'delivery_options', 'profile']