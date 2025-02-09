from django.urls import path
from .views import *

urlpatterns = [
    path('', ObtainaPairView.as_view()),
    path('users', AllUsers.as_view()),
    path('update_user/<int:pk>', UpdateUser.as_view()),
    path('single_user/<int:pk>', SingleUser.as_view()),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('all_farmers', AllFarmers.as_view()),

    # registration urls
    path('buyer_register', BuyerRegistrationView.as_view()),
    path('farmer_register', FarmerRegistrationView.as_view()),
    path('save_fcm_token/<int:pk>', SaveFCMTokenView.as_view()),
    # end registration urls

    #reset password
    path('send_email', PasswordResetRequestView.as_view()),
    path("reset_password/<uidb64>/<token>/", PasswordResetConfirmView.as_view()),

    #end reset password

    # profile urls
    path('profile/<int:user_id>', UserProfile),
    path('single_profile/<int:user_id>', SingleProfile),
    path('update_profile/<int:user_id>', EditUserProfile.as_view()),
    path('farmer_profiles', FarmerProfiles.as_view()),
    # end profiles

    #special urls
    path('all_specialisations', AllSpecials.as_view()),
    path('farmer_specialisations/<int:special_id>', FarmerSpecialisations),

   #crops
   path('post_crops', PostCrops.as_view()),
   path('farmer/<int:farmer_id>', ListFarmerCrops),
   path('all_crops', ListCrops.as_view()),
   path('delete_farmer_crop/<int:pk>',DeleteFarmerCrop.as_view()),
   path('update_farmer_crop/<int:pk>', UpdateFarmerCrop.as_view()),
   path('crop_detail/<int:pk>', CropDetail.as_view()),
   path('update_quantity/<int:pk>', UpdateQuantity.as_view()),
   path('update_weight/<int:pk>', UpdateWeight.as_view()),

   #order crops
   path('post_order_crops', PostOrderCrop.as_view()),
   path('farmer-order-crops/<int:farmer_id>', ListOrderFarmerCrops),

   #ratings
   path('post_ratings', PostRatings.as_view()),
   path('update_rating/<int:pk>', UpdateRatings.as_view()),

   #reviews
   path('post_reviews', PostReviews.as_view()),
   path('all_reviews', AllReviews.as_view()),

   #notifications
   path('post_notifications', PostNotifications.as_view()),
   path('update_is_read/<int:pk>', IsReadStatus.as_view()),
   path('user_notifications/<int:user_id>', UserNotification),

   #discount
   path('all_discounts', AllDiscounts.as_view()),
   path('post_discount', PostDiscount.as_view()),
   path('edit_discount/<int:pk>', EditDiscount.as_view()),
   path('single_discount/<int:pk>', singleDiscount.as_view()),

   #orders
   path('post_orders', PostOrders.as_view()),
   path('DeleteOrder/<int:pk>', DeleteOrder.as_view()),
   path('user_orders/<int:user_id>',UserOrder),
   path('single_order/<int:pk>', SingleOrder.as_view()),
   path('orders_for_farmer/<int:farmer_id>', orders_for_farmer),
   path('update_status/<int:pk>', UpdateStatus.as_view()),

   #orderDetail
   path('post_order_detail', PostOrderDetail.as_view()),
  
   #paymentDetails
   path('post_payment_detail', PostPaymentDetails.as_view()),

   #userAddress
   path('user_addresses/<int:user_id>', ListUserAddress),
   path('edit_address/<int:pk>', EditUserAddress.as_view()),
   path('post_user_address', PostUserAddress.as_view()),
   path('edit_active/<int:pk>', UpdateActive.as_view()),
   path('edit_active/', EditActiveAddresses.as_view(), name='edit_active'),
   
   #farmer crop perfomance
   path('post_perfomance', PostCropPerformanceView.as_view()),
   path('monthly_sales_overview/<int:crop_id>', MonthlySalesView.as_view()),

    # Market Trends
    path('market-trends/', MarketTrendView.as_view(), name='market_trends'),
    path('market-insights/<int:farmer_id>/', MarketInsights.as_view(), name='market-insights'),
    path('crop_market_insights/<int:crop_id>', crop_market_insights),

    # User Interaction Logs
    path('post_user-interactions/', UserInteractionLogView.as_view(), name='user_interactions'),
    path('crop_actions/stats/<int:crop_id>', crop_actions),

    #payment methods
    path("post_payment_method", PostPaymentMethod.as_view()),
    path('list_payment_methods/<int:user_id>', ListPaymentMethods),
    path('edit_payment/<int:pk>', EditPaymentMethods.as_view()),
    
    #delivery options
    path("post_delivery_options", PostDeliveryOptions.as_view()),
    path('delivery_list/<int:user_id>', ListDeliveryOptions),
    path('edit_delivery/<int:pk>', UpdateDeliveryOption.as_view()),

    #flutter wave url
    path('initiate-mobile-money-payment/', initiate_mobile_money_payment, name='initiate_mobile_money_payment'),
]