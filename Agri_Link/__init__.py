# def export_data():
#     file_path = DATA_DIR / 'agrilink_data.csv'

#     # Fetch crop data
#     crops = Crop.objects.all()
#     df = read_frame(crops, fieldnames=['id', 'user__id', 'crop_name', 'price_per_unit', 'unit', 'availability'])
#     df = df.rename(columns={'user__id': 'farmer_id', 'crop_name': 'product_name'})

#     # Fetch successful payments and calculate quantity sold
#     payments = PaymentDetails.objects.filter(status='successful')
#     quantity_sold_dict = {}
#     for payment in payments:
#         for quantity_item in payment.quantity:
#             crop_id = quantity_item['id']
#             quantity = quantity_item['quantity']
#             quantity_sold_dict[crop_id] = quantity_sold_dict.get(crop_id, 0) + quantity

#     quantity_sold_df = pd.DataFrame(list(quantity_sold_dict.items()), columns=['crop_id', 'quantity_sold'])
#     df = df.merge(quantity_sold_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
#     df['quantity_sold'] = df['quantity_sold'].fillna(0)

#     # Fetch orders for buyer_id
#     orders = Order.objects.all()
#     order_df = read_frame(orders, fieldnames=['user__id', 'address'])
#     df['buyer_id'] = order_df['user__id'].reindex(df.index, fill_value='None')

#     # Fetch address for buyers
#     address = UserAddress.objects.all()
#     add_df = read_frame(address, fieldnames=['user__id', 'district'])
#     add_df = add_df.rename(columns={'user__id': 'buyer_id', 'district': 'buyer_location'})
#     df = df.merge(add_df[['buyer_id', 'buyer_location']], on='buyer_id', how='left')
#     df['buyer_location'] = df['buyer_location'].fillna('Unknown')

#     # Fetch profile for farmers
#     profile = Profile.objects.filter(is_farmer=True)
#     prof_df = read_frame(profile, fieldnames=['user__id', 'location'])
#     prof_df = prof_df.rename(columns={'user__id': 'farmer_id', 'location': 'farmer_location'})
#     df = df.merge(prof_df[['farmer_id', 'farmer_location']], on='farmer_id', how='left')
#     df['farmer_location'] = df['farmer_location'].fillna('Unknown')

#     # Fetch interaction logs
#     logs = UserInteractionLog.objects.all()
#     log_df = read_frame(logs, fieldnames=['crop__id', 'action', 'timestamp', 'monthly_stats'])
#     log_df = log_df.rename(columns={'crop__id': 'crop_id'})
#     log_df = log_df.dropna(subset=['crop_id'])
#     log_df['crop_id'] = pd.to_numeric(log_df['crop_id'], errors='coerce').astype('int64')

#     # Sort by timestamp for latest log
#     log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], utc=True)
#     latest_logs = log_df.loc[log_df.groupby('crop_id')['timestamp'].idxmax()]

#     # Calculate metrics
#     views_list = []
#     purchases_list = []
#     interaction_count_list = []
#     month_list = []

#     for _, log in latest_logs.iterrows():
#         crop_id = log['crop_id']
#         monthly_stats = log['monthly_stats']
#         total_views = sum(month['views'] for month in monthly_stats)
#         total_purchases = sum(month['purchases'] for month in monthly_stats)
#         highest_purchase_month = max(monthly_stats, key=lambda m: m['purchases'], default={'month': 0})['month']

#         views_list.append({'crop_id': crop_id, 'views': total_views})
#         purchases_list.append({'crop_id': crop_id, 'purchases': total_purchases})
#         interaction_count_list.append({'crop_id': crop_id, 'interaction_count': logs.filter(crop__id=crop_id).count()})
#         month_list.append({'crop_id': crop_id, 'highest_purchase_month': highest_purchase_month})

#     views_df = pd.DataFrame(views_list)
#     purchases_df = pd.DataFrame(purchases_list)
#     interaction_count_df = pd.DataFrame(interaction_count_list)
#     month_df = pd.DataFrame(month_list)

#     for temp_df in [views_df, purchases_df, interaction_count_df, month_df]:
#         temp_df['crop_id'] = pd.to_numeric(temp_df['crop_id'], errors='coerce').astype('int64')

#     # Merge into main DataFrame
#     df = df.merge(views_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
#     df = df.merge(purchases_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
#     df = df.merge(interaction_count_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
#     df = df.merge(month_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

#     # Add timestamp
#     timestamp_df = latest_logs[['crop_id', 'timestamp']].copy()
#     timestamp_df['crop_id'] = pd.to_numeric(timestamp_df['crop_id'], errors='coerce').astype('int64')
#     df = df.merge(timestamp_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

#     # Fill NaN values
#     df['views'] = df['views'].fillna(0)
#     df['purchases'] = df['purchases'].fillna(0)
#     df['interaction_count'] = df['interaction_count'].fillna(0)
#     df['highest_purchase_month'] = df['highest_purchase_month'].fillna(0).astype(int)
#     df['timestamp'] = df['timestamp'].fillna(pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))
#     df['buyer_id'] = df['buyer_id'].fillna('None')

#     # Calculate demand score and preserve raw value
#     df['demand_score_raw'] = (
#         0.4 * df['quantity_sold'] +
#         0.3 * df['purchases'] +
#         0.2 * df['views'] +
#         0.1 * df['interaction_count']
#     ).round(6)
#     df['demand_score'] = df['demand_score_raw']

#     # Define output columns
#     output_cols = ['id', 'farmer_id', 'product_name', 'price_per_unit', 'unit', 'availability', 
#                    'quantity_sold', 'buyer_id', 'buyer_location', 'farmer_location', 'views', 
#                    'purchases', 'interaction_count', 'highest_purchase_month', 'timestamp', 
#                    'demand_score', 'demand_score_raw']

#     # Save to CSV
#     df[output_cols].to_csv(file_path, index=False)
#     df[output_cols].to_csv('C:/Users/HP/Desktop/Datasets/agrilink_data.csv', index=False)
#     logger.info(f"Exported data to {file_path} with {len(df)} rows")
#     return f"Exported data to {file_path}"