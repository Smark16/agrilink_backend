import json
from collections import defaultdict
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import ExtractMonth, ExtractYear
import httpx
from django.conf import settings
from .models import PaymentDetails, User, Order, OrderCrop, PaymentMethod, Crop

class CropPerformanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'performance'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            amount_data = data.get('amount')  # [{'id': 18, 'amount': 18000}]
            email = data.get('email')  # "sengendomark16@gmail.com"
            phone_number = data.get('phone_number')  # "256759079867"
            fullname = data.get('fullname')  # Expected in payload
            tx_ref = data.get('tx_ref')  # Expected in payload
            order_id = data.get('order')  # 12
            network = data.get('network')  # Expected in payload
            quantity = data.get('quantity')  # [{'id': 18, 'quantity': 2}]
            crop_ids = data.get('crop', [])  # [18]

            print('Performance data:', amount_data, email, phone_number, quantity, order_id, crop_ids)

            if not all([amount_data, email, phone_number, fullname, tx_ref, order_id, network, quantity, crop_ids]):
                await self.send_error("Missing required fields")
                return

            payment_result = await self.initiate_mobile_money_payment(
                amount_data, email, phone_number, fullname, tx_ref, order_id, network, quantity, crop_ids
            )

            # Send the payment result back to the client immediately
            await self.send(text_data=json.dumps({
                "type": "payment_result",
                "res": payment_result
            }))

            if payment_result.get("error"):
                await self.send_error(payment_result["error"])
                return

            for crop_id in crop_ids:
                order = await self.get_order(order_id)
                if not order:
                    await self.send_error("Order not found")
                    return

                order_crop = await self.get_order_crop(order)
                if not order_crop:
                    await self.send_error("No crops associated with this order")
                    return

                farmer_id = await database_sync_to_async(lambda: order_crop.user.id)()
                daily_monthly_sales = await self.get_daily_monthly_sales(farmer_id, crop_id)
                monthly_sales = await self.get_monthly_sales(crop_id)

                sales_data = {
                    "daily_monthly_sales": daily_monthly_sales,
                    "monthly_sales": monthly_sales
                }

                await self.send_update_to_clients(sales_data)

        except json.JSONDecodeError as e:
            await self.send_error("Invalid JSON data")
        except Exception as e:
            print(f"Error in receive: {str(e)}")
            await self.send_error(f"An error occurred: {str(e)}")

    async def send_error(self, message):
        await self.send(text_data=json.dumps({"error": message}))

    @database_sync_to_async
    def get_order(self, order_id):
        try:
            return Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return None

    @database_sync_to_async
    def get_order_crop(self, order):
        try:
            return OrderCrop.objects.filter(orderdetail__order=order).first()
        except OrderCrop.DoesNotExist:
            return None

    async def initiate_mobile_money_payment(self, amount_data, email, phone_number, fullname, tx_ref, order_id, network, quantity, crop_ids):
        try:
            order = await self.get_order(order_id)
            if not order:
                return {"error": "Order not found"}

            order_crop = await self.get_order_crop(order)
            if not order_crop:
                return {"error": "No crops associated with this order"}

            # Fetch farmer details asynchronously
            farmer = await database_sync_to_async(lambda: order_crop.user)()
            farmer_payment_method = await database_sync_to_async(PaymentMethod.objects.get)(user=farmer)
            farmer_phone_number = farmer_payment_method.contact_phone
            farmer_name = farmer_payment_method.contact_name

            total_amount = sum(item['amount'] for item in amount_data)
            commission = total_amount * 0.075  # 7.5% commission
            farmer_amount = total_amount - commission

            headers = {
                "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            charge_payload = {
                "tx_ref": tx_ref,
                "amount": str(total_amount),
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

            async with httpx.AsyncClient() as client:
                charge_response = await client.post("https://api.flutterwave.com/v3/payments", json=charge_payload, headers=headers)
                charge_data = charge_response.json()
                if charge_response.status_code != 200 or charge_data['status'] != 'success':
                    return {"error": f"Payment initiation failed: {charge_data.get('message', 'Unknown error')}"}

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
                transfer_response = await client.post("https://api.flutterwave.com/v3/transfers", json=transfer_payload, headers=headers)
                transfer_data = transfer_response.json()
                if transfer_response.status_code != 200 or transfer_data['status'] != 'success':
                    return {"error": f"Transfer to farmer failed: {transfer_data.get('message', 'Unknown error')}"}

                commission_payload = {
                    "account_bank": "AIRTEL",
                    "account_number": "+256759079867",
                    "amount": commission,
                    "currency": "UGX",
                    "beneficiary_name": "AgriLink",
                    "reference": f"{tx_ref}_commission",
                    "narration": "Platform commission",
                    "debit_currency": "UGX"
                }
                commission_response = await client.post("https://api.flutterwave.com/v3/transfers", json=commission_payload, headers=headers)
                commission_data = commission_response.json()
                if commission_response.status_code != 200 or commission_data['status'] != 'success':
                    return {"error": f"Commission transfer failed: {commission_data.get('message', 'Unknown error')}"}

            # Save payment details asynchronously with all operations wrapped
            @database_sync_to_async
            def save_payment():
                try:
                    payment = PaymentDetails(
                        amount=amount_data,  # JSONField assumed
                        email=email,
                        phone_number=phone_number,
                        fullname=fullname,
                        tx_ref=tx_ref,
                        order=order,
                        network=network,
                        quantity=quantity,  # JSONField assumed
                        status="successful"
                    )
                    payment.save()
                    payment.crop.set(crop_ids)
                    return payment
                except Exception as e:
                    raise Exception(f"Failed to save payment: {str(e)}")

            await save_payment()

            return {
                "message": "Payment processed successfully",
                "charge_response": charge_data,
                "transfer_response": transfer_data,
                "commission_response": commission_data
            }

        except PaymentMethod.DoesNotExist:
            return {"error": "Payment method for farmer not found"}
        except Exception as e:
            print(f"Payment processing error: {str(e)}")
            return {"error": str(e)}

    @database_sync_to_async
    def get_daily_monthly_sales(self, farmer_id, crop_id):
        try:
            farmer = User.objects.get(pk=farmer_id)
            user_joined_date = farmer.date_joined.date()
            today = timezone.now().date()

            payments = PaymentDetails.objects.filter(
                crop__id=crop_id,
                created_at__date__range=[user_joined_date, today]
            ).distinct()

            daily_sales = defaultdict(float)
            for payment in payments:
                payment_date = payment.created_at.date()
                total_amount = sum(item["amount"] for item in payment.amount)
                daily_sales[payment_date] += total_amount

            all_dates = []
            current_date = user_joined_date
            while current_date <= today:
                all_dates.append(current_date)
                current_date += timedelta(days=1)

            sales_data = []
            for date in all_dates:
                sales_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "amount": daily_sales.get(date, 0.0)
                })

            monthly_sales = defaultdict(list)
            for sale in sales_data:
                month_key = datetime.strptime(sale["date"], "%Y-%m-%d").strftime("%B %Y")
                monthly_sales[month_key].append(sale)

            monthly_sales_data = [
                {"month": month, "daily_sales": monthly_sales[month]}  # Fixed: Use monthly_sales[month]
                for month in sorted(monthly_sales.keys())
            ]

            # Handle get_full_name safely
            farmer_name = farmer.get_full_name() if callable(farmer.get_full_name) else farmer.get_full_name

            return {
                "farmer": farmer_name,
                "date_joined": user_joined_date.strftime("%Y-%m-%d"),
                "monthly_sales": monthly_sales_data
            }

        except Exception as e:
            return {"error": str(e)}

    @database_sync_to_async
    def get_monthly_sales(self, crop_id):
        try:
            current_year = timezone.now().year
            current_month = timezone.now().month

            payments = PaymentDetails.objects.filter(crop__id=crop_id).annotate(
                month=ExtractMonth('created_at'),
                year=ExtractYear('created_at')
            ).filter(
                Q(year=current_year, month__lte=current_month) | Q(year=current_year - 1)
            )

            monthly_data = {}
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

                amount_list = payment.amount
                quantity_list = payment.quantity

                for amount_entry in amount_list:
                    if str(amount_entry.get("id")) == str(crop_id):
                        monthly_data[key]["total_amount"] += float(amount_entry.get("amount", 0))

                for quantity_entry in quantity_list:
                    if str(quantity_entry.get("id")) == str(crop_id):
                        monthly_data[key]["total_quantity"] += int(quantity_entry.get("quantity", 0))

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

            for month in range(current_month, 13):
                key = f"{current_year - 1}-{month}"
                if key in monthly_data:
                    data.append({
                        "year": current_year - 1,
                        "month": month,
                        "total_quantity": monthly_data[key]["total_quantity"],
                        "total_amount": monthly_data[key]["total_amount"],
                    })

            data.sort(key=lambda x: (x['year'], x['month']))
            return data

        except Exception as e:
            return {"error": str(e)}

    async def send_update_to_clients(self, sales_data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "send_update", "data": sales_data}
        )

    async def send_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))