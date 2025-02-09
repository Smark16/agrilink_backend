from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
import math
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Avg
import nltk
from fuzzywuzzy import process
from django.core.exceptions import ValidationError

# Ensure you download necessary NLTK data
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('wordnet')
from nltk.stem import WordNetLemmatizer

lemmatizer = WordNetLemmatizer()

# Create your models here.
class User(AbstractUser):
    is_buyer = models.BooleanField(default=False, db_index=True)
    is_farmer = models.BooleanField(default=False, db_index=True)
    fcm_token = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # Add this field to store FCM tokens

    @property
    def get_full_name(self):
        # Fetch FullName from related Farmer or Buyer model
        if hasattr(self, 'farmer'):
            return self.farmer.FullName
        elif hasattr(self, 'buyer'):
            return self.buyer.FullName
        return self.username  # Fallback to username if no FullName is found

class Farmer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer')
    FullName = models.CharField(max_length=255, db_index=True)
    Email = models.EmailField(max_length=255, db_index=True)
    contact = models.PositiveBigIntegerField(db_index=True)
    co_operativeID = models.CharField(max_length=255, db_index=True)
    is_farmer = models.BooleanField(default=False, db_index=True)

    def clean(self):
        super().clean()
        # Check if FullName has at least two words
        if len(self.FullName.split()) < 2:
            raise ValidationError("Full Name must include at least a first name and last name.")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class Buyer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer')
    FullName = models.CharField(max_length=255, db_index=True)
    Email = models.EmailField(max_length=255, db_index=True)
    contact = models.PositiveBigIntegerField(db_index=True)
    is_buyer = models.BooleanField(default=False, db_index=True)

    def clean(self):
        super().clean()
        # Check if FullName has at least two words
        if len(self.FullName.split()) < 2:
            raise ValidationError("Full Name must include at least a first name and last name.")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

#specilaization
class Specialisation(models.Model):
    name = models.CharField(max_length=30)

# model profiles
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile') #select_related
    verified = models.BooleanField(default=False)
    image = models.ImageField(blank=True, null=True, upload_to='images/')
    location = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True) 
    farmName = models.CharField(max_length=100, null=True, blank=True)
    specialisation = models.ManyToManyField(Specialisation)
    is_farmer = models.BooleanField()
    is_buyer = models.BooleanField()
    #bio, social_links


def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, is_farmer=instance.is_farmer, is_buyer=instance.is_buyer, verified=True)

def save_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


post_save.connect(create_profile, sender=User)
post_save.connect(save_profile, sender=User)  

 
#payment method 
class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='payment_method')
    methodType = models.JSONField(default=list, max_length=100)
    contact_name = models.CharField(max_length=100, blank=True, null=True)  
    contact_email = models.EmailField(blank=True, null=True)  
    contact_phone = models.CharField(max_length=20, blank=True, null=True)  

#delivery options
class DeliveryOption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delivery_options')
    name = models.JSONField(default=list, max_length=100) 
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    duration = models.CharField(max_length=50, blank=True, null=True)  

# crop model
class Crop(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crops')
    specialisation = models.ForeignKey(Specialisation, on_delete=models.CASCADE, related_name='crop_category')
    crop_name = models.CharField(max_length=100)
    description = models.TextField(max_length=255)
    weight = models.JSONField(default=list, blank=True, null=True)
    price_per_unit = models.PositiveIntegerField()
    unit = models.CharField(max_length=100)
    InitialAvailability = models.PositiveIntegerField()
    availability = models.PositiveIntegerField(default='0')
    quantity = models.PositiveIntegerField(default='0') #tracks quantity taken by buyer
    image = models.ImageField(upload_to='crops/')
    date_added = models.DateTimeField(auto_now_add=True)
    
    @property
    def get_average_rating(self):
        ratings = self.ratings.all()
        if ratings:
           total_ratings = sum([rate.value for rate in ratings])
           average_rates = total_ratings / len(ratings)
           return math.ceil(average_rates)
        else:
            return 0
        
    @property
    def get_discounted_price(self):
        active_discounts = self.discounts.filter(active=True, crop=self)
        
        if active_discounts.exists():
            active_discount = active_discounts.first()
            discount_factor = 1 - (active_discount.discount_percent / 100)
            return round(self.price_per_unit * discount_factor, 2)
        
        return 0
        
#Rating
class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='ratings')
    value = models.PositiveIntegerField()

#Review
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    message = models.TextField(max_length=255)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='crop_review')
    timestamp = models.DateTimeField(auto_now_add=True)

# Notification
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True) 
    is_read = models.BooleanField(default=False)

# user address
class UserAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='useraddress')
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

# Order
class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(UserAddress, on_delete=models.SET_NULL, null=True, blank=True,) #select_related
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateField(auto_now=True)
    payment_method = models.CharField(max_length=100)
    delivery_option = models.CharField(max_length=100)
    status = models.CharField(max_length=50,default='Pending')

#the ordered crops
class OrderCrop(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='OrderCrop')
    quantity = models.PositiveIntegerField()
    weights = models.JSONField(default=list, blank=True, null=True)  
    price_per_unit = models.PositiveIntegerField() 
    unit = models.CharField(max_length=100)  
    image = models.ImageField(upload_to='crops/')
    crop_name = models.CharField(max_length=100)

    @property
    def get_discounted_price(self):
        active_discounts = self.order_discounts.filter(active=True, orderCrop=self)
        
        if active_discounts.exists():
            active_discount = active_discounts.first()
            discount_factor = 1 - (active_discount.discount_percent / 100)
            return round(self.price_per_unit * discount_factor, 2)
        return 0

# order Details
class OrderDetail(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_detail')
    crop = models.ManyToManyField(OrderCrop) 

# Discount
class Discount(models.Model):
    description = models.TextField(max_length=255)
    discount_percent = models.FloatField()
    active = models.BooleanField(default=False)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='discounts')
    orderCrop = models.ForeignKey(OrderCrop, on_delete=models.CASCADE, null=True, blank=True, related_name='order_discounts')

# payment details
class PaymentDetails(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment')
    fullname = models.CharField(max_length=255)
    phone_number = models.PositiveIntegerField()
    email = models.EmailField(max_length=255)
    tx_ref = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  
    network = models.CharField(max_length=255)
    status = models.CharField(max_length=100, default='not payed')
    created_at = models.DateTimeField(auto_now_add=True)


class CropPerformance(models.Model):
    orderCrop = models.ForeignKey(OrderCrop, on_delete=models.CASCADE, related_name='perfomance')
    date = models.DateField(auto_now_add=True)

    @property
    def get_quantity_sold(self):
        return self.orderCrop.quantity

    @property
    def get_crop_revenue(self):
        return self.get_quantity_sold  * self.orderCrop.price_per_unit

#market trends
class MarketTrend(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='market_trends')
    updated_at = models.DateTimeField(auto_now=True)
    total_demand = models.IntegerField(default=0)

    def normalize_name(self, crop_name):
        """
        Normalize the crop name using NLP techniques (tokenization, lemmatization).
        """
        tokens = nltk.word_tokenize(crop_name.lower())
        return " ".join([lemmatizer.lemmatize(token) for token in tokens])

    @property
    def average_price_per_kg(self):
        """
        Calculate the average price per kg for similar crops using NLP-based matching.
        """
        normalized_name = self.normalize_name(self.crop.crop_name)
        all_crops = Crop.objects.all()

        # Fuzzy match crop names to find similar ones
        crop_names = [crop.crop_name for crop in all_crops]
        similar_crops = process.extract(normalized_name, crop_names, limit=None, scorer=process.fuzz.partial_ratio)

        # Filter matches with a similarity threshold (e.g., 80%)
        matched_crops = [name for name, score in similar_crops if score >= 80]

        # Query the database for matched crop names
        return Crop.objects.filter(crop_name__in=matched_crops).aggregate(avg_price=Avg('price_per_kg'))['avg_price']

    @property
    def farmer_pricing(self):
        """
        Retrieve all pricing details for similar crops using NLP-based matching.
        """
        normalized_name = self.normalize_name(self.crop.crop_name)
        all_crops = Crop.objects.all()

        # Fuzzy match crop names to find similar ones
        crop_names = [crop.crop_name for crop in all_crops]
        similar_crops = process.extract(normalized_name, crop_names, limit=None, scorer=process.fuzz.partial_ratio)

        # Filter matches with a similarity threshold (e.g., 80%)
        matched_crops = [name for name, score in similar_crops if score >= 80]

        # Query the database for matched crop names
        similar_crops_queryset = Crop.objects.filter(crop_name__in=matched_crops)
        return [{"farmer": crop.user.username, "price_per_kg": crop.price_per_kg} for crop in similar_crops_queryset]

    def add_demand(self, demand_increase):
        """
        Increase the total demand for the crop.
        """
        self.total_demand += demand_increase
        self.save()
#userInteractionLog
class UserInteractionLog(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='interaction_logs')
    action = models.CharField(max_length=100)  
    timestamp = models.DateTimeField(auto_now_add=True)

    