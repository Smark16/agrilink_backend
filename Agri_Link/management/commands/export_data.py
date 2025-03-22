from django.core.management.base import BaseCommand
import pandas as pd
from django_pandas.io import read_frame
from Agri_Link.models import Crop, PaymentDetails, UserInteractionLog, Order, UserAddress, Profile
import os

class Command(BaseCommand):
    help = 'Exports data to CSV with buyer and farmer locations, avoiding duplicates'

    def handle(self, *args, **kwargs):
        file_path = r'C:/Users/HP/Desktop/Datasets/agrilink_data.csv'

        # Fetch crop data
        crops = Crop.objects.all()
        df = read_frame(crops, fieldnames=['id', 'user__id', 'crop_name', 'price_per_unit', 'unit', 'availability'])
        df = df.rename(columns={'user__id': 'farmer_id', 'crop_name': 'product_name'})

        # Fetch successful payments and calculate quantity sold
        payments = PaymentDetails.objects.filter(status='successful')
        quantity_sold_dict = {}
        for payment in payments:
            for quantity_item in payment.quantity:
                crop_id = quantity_item['id']
                quantity = quantity_item['quantity']
                quantity_sold_dict[crop_id] = quantity_sold_dict.get(crop_id, 0) + quantity

        quantity_sold_df = pd.DataFrame(list(quantity_sold_dict.items()), columns=['crop_id', 'quantity_sold'])
        df = df.merge(quantity_sold_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        df['quantity_sold'] = df['quantity_sold'].fillna(0)

        # Fetch orders for buyer_id
        orders = Order.objects.all()
        order_df = read_frame(orders, fieldnames=['user__id', 'address'])
        df['buyer_id'] = order_df['user__id'].reindex(df.index, fill_value='None')

        # Fetch address for buyers (from UserAddress)
        address = UserAddress.objects.all()
        add_df = read_frame(address, fieldnames=['user__id', 'district'])
        add_df = add_df.rename(columns={'user__id': 'buyer_id', 'district': 'buyer_location'})
        df = df.merge(add_df[['buyer_id', 'buyer_location']], on='buyer_id', how='left')
        df['buyer_location'] = df['buyer_location'].fillna('Unknown')

        # Fetch profile for farmers (filter for is_farmer=True)
        profile = Profile.objects.filter(is_farmer=True)  # Only farmers
        prof_df = read_frame(profile, fieldnames=['user__id', 'location'])
        prof_df = prof_df.rename(columns={'user__id': 'farmer_id', 'location': 'farmer_location'})
        df = df.merge(prof_df[['farmer_id', 'farmer_location']], on='farmer_id', how='left')
        df['farmer_location'] = df['farmer_location'].fillna('Unknown')

        # Fetch interaction logs
        logs = UserInteractionLog.objects.all()
        log_df = read_frame(logs, fieldnames=['crop__id', 'action', 'timestamp', 'monthly_stats'])
        log_df = log_df.rename(columns={'crop__id': 'crop_id'})
        log_df = log_df.dropna(subset=['crop_id'])
        log_df['crop_id'] = pd.to_numeric(log_df['crop_id'], errors='coerce').astype('int64')

        # Sort by timestamp to get the latest log per crop
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], utc=True)
        latest_logs = log_df.loc[log_df.groupby('crop_id')['timestamp'].idxmax()]

        # Calculate views, purchases, interaction count, and highest purchase month
        views_list = []
        purchases_list = []
        interaction_count_list = []
        month_list = []

        for _, log in latest_logs.iterrows():
            crop_id = log['crop_id']
            monthly_stats = log['monthly_stats']
            total_views = sum(month['views'] for month in monthly_stats)
            total_purchases = sum(month['purchases'] for month in monthly_stats)
            highest_purchase_month = max(monthly_stats, key=lambda m: m['purchases'], default={'month': 0})['month']

            views_list.append({'crop_id': crop_id, 'views': total_views})
            purchases_list.append({'crop_id': crop_id, 'purchases': total_purchases})
            interaction_count_list.append({'crop_id': crop_id, 'interaction_count': logs.filter(crop__id=crop_id).count()})
            month_list.append({'crop_id': crop_id, 'highest_purchase_month': highest_purchase_month})

        views_df = pd.DataFrame(views_list)
        purchases_df = pd.DataFrame(purchases_list)
        interaction_count_df = pd.DataFrame(interaction_count_list)
        month_df = pd.DataFrame(month_list)

        for temp_df in [views_df, purchases_df, interaction_count_df, month_df]:
            temp_df['crop_id'] = pd.to_numeric(temp_df['crop_id'], errors='coerce').astype('int64')

        # Merge into main DataFrame
        df = df.merge(views_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        df = df.merge(purchases_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        df = df.merge(interaction_count_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        df = df.merge(month_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

        # Add timestamp
        timestamp_df = latest_logs[['crop_id', 'timestamp']].copy()
        timestamp_df['crop_id'] = pd.to_numeric(timestamp_df['crop_id'], errors='coerce').astype('int64')
        df = df.merge(timestamp_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

        # Fill NaN timestamps with a default value (e.g., today's date or a placeholder)
        df['timestamp'] = df['timestamp'].fillna(pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))

        # Fill NaN values
        df['views'] = df['views'].fillna(0)
        df['purchases'] = df['purchases'].fillna(0)
        df['interaction_count'] = df['interaction_count'].fillna(0)
        df['highest_purchase_month'] = df['highest_purchase_month'].fillna(0).astype(int)
        df['timestamp'] = df['timestamp'].fillna(pd.NaT)
        df['buyer_id'] = df['buyer_id'].fillna('None')

        # Calculate demand score
        df['demand_score'] = (
            0.4 * df['quantity_sold'] +
            0.3 * df['purchases'] +
            0.2 * df['views'] +
            0.1 * df['interaction_count']
        ).round(6)

        # Define columns for output (include buyer_location and farmer_location)
        output_cols = ['id', 'farmer_id', 'product_name', 'price_per_unit', 'unit', 'availability', 
                       'quantity_sold', 'buyer_id', 'buyer_location', 'farmer_location', 'views', 
                       'purchases', 'interaction_count', 'highest_purchase_month', 'timestamp', 
                       'demand_score']

        # Handle CSV update
        if os.path.exists(file_path):
            existing_df = pd.read_csv(file_path)
            
            # Ensure consistent data types with existing_df
            existing_df['farmer_id'] = existing_df['farmer_id'].astype(str)
            existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'], utc=True, errors='coerce')
            existing_df['id'] = pd.to_numeric(existing_df['id'], errors='coerce').astype('int64')
            numeric_cols = ['quantity_sold', 'views', 'purchases', 'interaction_count', 'highest_purchase_month']
            for col in numeric_cols:
                existing_df[col] = pd.to_numeric(existing_df[col], errors='coerce').fillna(0).astype(int)
            if 'demand_score' in existing_df.columns:
                existing_df['demand_score'] = pd.to_numeric(existing_df['demand_score'], errors='coerce').fillna(0.0).round(6)
            else:
                existing_df['demand_score'] = 0.0
            existing_df['buyer_id'] = existing_df['buyer_id'].fillna('None')
            if 'buyer_location' not in existing_df.columns:
                existing_df['buyer_location'] = 'Unknown'
            if 'farmer_location' not in existing_df.columns:
                existing_df['farmer_location'] = 'Unknown'

            # Combine existing and new data, keep latest by 'id'
            combined_df = pd.concat([existing_df, df[output_cols]])
            updated_df = combined_df.drop_duplicates(subset=['id'], keep='last')

            # Debugging: Show what changed
            self.stdout.write(f"New rows: {len(df)}")
            self.stdout.write(f"Existing rows: {len(existing_df)}")
            changed_df = updated_df[~updated_df['id'].isin(existing_df['id']) | 
                                   (updated_df['demand_score'] != existing_df['demand_score'].reindex(updated_df.index).fillna(updated_df['demand_score']))]
            if not changed_df.empty:
                self.stdout.write(f"Updated/new rows: {changed_df[['id', 'product_name', 'demand_score']].to_dict('records')}")

            # Write updated DataFrame back to CSV
            updated_df.to_csv(file_path, index=False)
            self.stdout.write(self.style.SUCCESS(f'Updated {file_path} with {len(updated_df)} rows'))
        else:
            df[output_cols].to_csv(file_path, index=False)
            self.stdout.write(self.style.SUCCESS(f'Created {file_path} with {len(df)} rows'))