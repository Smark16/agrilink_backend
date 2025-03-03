import json
from collections import defaultdict
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import ExtractMonth, ExtractYear
from .models import PaymentDetails, Crop, User, Order, PaymentMethod, OrderCrop

class CropPerformanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'performance'

        # Add the user to the performance group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from the performance group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Process incoming messages (e.g., payment events)
        try:
            data = json.loads(text_data)
            event_type = data.get('type')

            if event_type == 'payment_update':
                # Extract update details (no payment data)
                farmer_id = data.get('farmer_id')
                order_id = data.get('order_id')
                crop_ids = data.get('crop_ids')
                amount = data.get('amount')

                # Calculate and send real-time performance metrics
                daily_monthly_sales = await self.get_daily_monthly_sales(farmer_id, crop_ids)
                monthly_sales = await self.get_monthly_sales(crop_ids)

                # Combine both daily/monthly and monthly sales data
                sales_data = {
                    "daily_monthly_sales": daily_monthly_sales,
                    "monthly_sales": monthly_sales
                }

                # Send updates to clients
                await self.send_update_to_clients(sales_data)

        except Exception as e:
            print(f"Error processing WebSocket message: {str(e)}")
            await self.send(text_data=json.dumps({"error": str(e)}))

    @database_sync_to_async
    def get_daily_monthly_sales(self, farmer_id, crop_ids):
        try:
            # Fetch the farmer
            farmer = User.objects.get(pk=farmer_id)

            # Get the date the user joined
            user_joined_date = farmer.date_joined.date()

            # Get the current date
            today = timezone.now().date()

            # Fetch payment details for the farmer's crops from the date they joined until today
            payments = PaymentDetails.objects.filter(
                crop__id__in=crop_ids,  # Filter by crop IDs
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

            return {
                "farmer": farmer.get_full_name(),
                "date_joined": user_joined_date.strftime("%Y-%m-%d"),
                "monthly_sales": monthly_sales_data
            }

        except Exception as e:
            return {"error": str(e)}

    @database_sync_to_async
    def get_monthly_sales(self, crop_ids):
        try:
            current_year = timezone.now().year
            current_month = timezone.now().month

            # Fetch payment details for the specified crop_ids
            payments = PaymentDetails.objects.filter(crop__id__in=crop_ids).annotate(
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

                # Extract amount and quantity for the specific crop_ids from JSON
                amount_list = payment.amount  # List of {"id": crop_id, "amount": value}
                quantity_list = payment.quantity  # List of {"id": crop_id, "quantity": value}

                for amount_entry in amount_list:
                    if str(amount_entry.get("id")) in [str(crop_id) for crop_id in crop_ids]:
                        monthly_data[key]["total_amount"] += float(amount_entry.get("amount", 0))

                for quantity_entry in quantity_list:
                    if str(quantity_entry.get("id")) in [str(crop_id) for crop_id in crop_ids]:
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

            return data

        except Exception as e:
            return {"error": str(e)}

    async def send_update_to_clients(self, sales_data):
        # Send updates to all connected clients
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_update",
                "data": sales_data
            }
        )

    async def send_update(self, event):
        # Send updates to the client
        await self.send(text_data=json.dumps(event["data"]))