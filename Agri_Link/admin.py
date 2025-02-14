from django.contrib import admin
from .models import *

# Register your models here.
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'is_buyer', 'is_farmer', 'date_joined']

class BuyerAdmin(admin.ModelAdmin):
    list_display =['id','user','FullName', 'Email', 'contact', 'is_buyer']

class FarmerAdmin(admin.ModelAdmin):
    list_display =['id', 'FullName', 'Email', 'contact','co_operativeID', 'is_farmer']

class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'image', 'verified', 'location']

class CropAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'specialisation', 'crop_name', 'image', 'weight', 'price_per_unit', 'availability']


class DiscountAdmin(admin.ModelAdmin):
    list_display = ['id', 'description', 'discount_percent', 'crop']

class SpecialAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

class deliveryAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'name', 'fee', 'duration']

class payMethodAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "methodType", "contact_phone", "contact_email", "contact_name"]

class paymentDetailsAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'fullname','phone_number','email','tx_ref','amount','network','status' ,'created_at']

admin.site.register(User, UserAdmin)
admin.site.register(Buyer, BuyerAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(Farmer, FarmerAdmin)
admin.site.register(Crop, CropAdmin)
admin.site.register(Discount, DiscountAdmin)
admin.site.register(Specialisation, SpecialAdmin)
admin.site.register(DeliveryOption, deliveryAdmin)
admin.site.register(PaymentMethod, payMethodAdmin)
admin.site.register(PaymentDetails, paymentDetailsAdmin)