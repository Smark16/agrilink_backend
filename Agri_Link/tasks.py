from celery import shared_task
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
import joblib
from fuzzywuzzy import fuzz, process
from django_pandas.io import read_frame
from sklearn.preprocessing import MinMaxScaler
from Agri_Link.models import Crop, PaymentDetails, UserInteractionLog, Order, UserAddress, Profile
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

# Define base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'  # Directory for CSV and model files

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

@shared_task
def export_data():
    file_path = DATA_DIR / 'agrilink_data.csv'

    # Fetch crop data
    crops = Crop.objects.all()
    df = read_frame(crops, fieldnames=['id', 'user__id', 'crop_name', 'price_per_unit', 'unit', 'availability'])
    df = df.rename(columns={'user__id': 'farmer_id', 'crop_name': 'product_name'})

    # Fetch orders and calculate purchases per crop
    orders = Order.objects.select_related('user', 'address').prefetch_related('orderitem_set__crop')
    order_data = []
    for order in orders:
        buyer_id = order.user.id
        for item in order.orderitem_set.all():  # Assuming Order has OrderItem with crop and quantity
            order_data.append({
                'buyer_id': buyer_id,
                'crop_id': item.crop.id,
                'quantity': item.quantity,
                'timestamp': order.created_at
            })
    order_df = pd.DataFrame(order_data)

    # Aggregate quantity_sold from orders
    quantity_sold_df = order_df.groupby('crop_id')['quantity'].sum().reset_index()
    quantity_sold_df = quantity_sold_df.rename(columns={'quantity': 'quantity_sold'})
    df = df.merge(quantity_sold_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
    df['quantity_sold'] = df['quantity_sold'].fillna(0)

    # Assign buyer_id per crop based on most recent order
    latest_order_per_crop = order_df.loc[order_df.groupby('crop_id')['timestamp'].idxmax()]
    buyer_mapping = latest_order_per_crop[['crop_id', 'buyer_id']].set_index('crop_id')['buyer_id']
    df['buyer_id'] = df['id'].map(buyer_mapping).fillna('None')

    # Fetch buyer locations
    address = UserAddress.objects.all()
    add_df = read_frame(address, fieldnames=['user__id', 'district'])
    add_df = add_df.rename(columns={'user__id': 'buyer_id', 'district': 'buyer_location'})
    df = df.merge(add_df[['buyer_id', 'buyer_location']], on='buyer_id', how='left')
    df['buyer_location'] = df['buyer_location'].fillna('Unknown')

    # Fetch farmer locations
    profile = Profile.objects.filter(is_farmer=True)
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
    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], utc=True)

    # Calculate views, purchases, and interaction_count from logs
    views_df = log_df[log_df['action'] == 'view'].groupby('crop_id').size().reset_index(name='views')
    purchases_df = log_df[log_df['action'] == 'purchase'].groupby('crop_id').size().reset_index(name='purchases')
    interaction_count_df = log_df.groupby('crop_id').size().reset_index(name='interaction_count')

    # Merge interaction data
    df = df.merge(views_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
    df = df.merge(purchases_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
    df = df.merge(interaction_count_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

    # Get latest timestamp and highest purchase month
    latest_logs = log_df.loc[log_df.groupby('crop_id')['timestamp'].idxmax()]
    timestamp_df = latest_logs[['crop_id', 'timestamp']]
    month_df = latest_logs.apply(
        lambda row: pd.Series({
            'crop_id': row['crop_id'],
            'highest_purchase_month': max(row['monthly_stats'], key=lambda m: m['purchases'], default={'month': 0})['month']
        }), axis=1
    )
    df = df.merge(timestamp_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
    df = df.merge(month_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

    # Fill NaN values
    df['views'] = df['views'].fillna(0)
    df['purchases'] = df['purchases'].fillna(0)
    df['interaction_count'] = df['interaction_count'].fillna(0)
    df['highest_purchase_month'] = df['highest_purchase_month'].fillna(0).astype(int)
    df['timestamp'] = df['timestamp'].fillna(pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))
    df['buyer_id'] = df['buyer_id'].replace('None', pd.NA).fillna('None')

    # Calculate demand score
    df['demand_score_raw'] = (
        0.4 * df['quantity_sold'] +
        0.3 * df['purchases'] +
        0.2 * df['views'] +
        0.1 * df['interaction_count']
    ).round(6)
    df['demand_score'] = df['demand_score_raw']

    # Define output columns
    output_cols = ['id', 'farmer_id', 'product_name', 'price_per_unit', 'unit', 'availability', 
                   'quantity_sold', 'buyer_id', 'buyer_location', 'farmer_location', 'views', 
                   'purchases', 'interaction_count', 'highest_purchase_month', 'timestamp', 
                   'demand_score', 'demand_score_raw']

    # Save to CSV
    df[output_cols].to_csv(file_path, index=False)
    df[output_cols].to_csv('C:/Users/HP/Desktop/Datasets/agrilink_data.csv', index=False)
    logger.info(f"Exported data to {file_path} with {len(df)} rows")
    return f"Exported data to {file_path}"

@shared_task
def train_recommendation_model():
    try:
        csv_path = DATA_DIR / 'agrilink_data.csv'
        model_path = DATA_DIR / 'svd_recommendation_model.pkl'
        logger.info(f"Loading data from {csv_path}")
        df = pd.read_csv(csv_path)
        if df.empty:
            logger.warning("No data in CSV")
            return "No data to train on"

        df.fillna(0, inplace=True)
        logger.info(f"CSV columns: {df.columns.tolist()}")

        # Engineer demand_score_raw
        required_cols = ['quantity_sold', 'purchases', 'views', 'interaction_count']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            logger.error(f"Missing columns for demand_score_raw: {missing}")
            raise ValueError(f"CSV missing required columns: {missing}")
        df['demand_score_raw'] = (
            0.4 * df['quantity_sold'] +
            0.3 * df['purchases'] +
            0.2 * df['views'] +
            0.1 * df['interaction_count']
        ).round(6)
        logger.info("demand_score_raw engineered")

        # Normalize demand_score
        scaler = MinMaxScaler()
        df['demand_score'] = scaler.fit_transform(df['demand_score_raw'].values.reshape(-1, 1)).flatten()
        logger.info("demand_score normalized")

        # Categorize demand_score
        def market_demand(score):
            if score < 0.4:
                return 'low'
            elif 0.4 <= score <= 0.7:
                return 'moderate'
            else:
                return 'high'

        df['demand_score_category'] = df['demand_score'].apply(market_demand)
        logger.info("demand_score categorized")

        # Engineer general_name
        def preprocess_text(text):
            return str(text).lower().strip()

        def group_similar_names(product_names, threshold=80):
            groups = {}
            product_names = list(set(product_names))
            for name in product_names:
                if not isinstance(name, str) or name.strip() == "":
                    continue
                name = preprocess_text(name)
                if not groups:
                    groups[name] = name
                    continue
                match_result = process.extractOne(name, list(groups.keys()), scorer=fuzz.partial_ratio)
                if match_result and match_result[1] >= threshold:
                    groups[name] = groups[match_result[0]]
                else:
                    groups[name] = name
            return groups

        product_names = df['product_name'].unique()
        similar_names = group_similar_names(product_names, threshold=80)
        df['general_name'] = df['product_name'].apply(lambda x: similar_names.get(preprocess_text(x), x))
        logger.info("general_name engineered")

        # Feature engineering
        df['interest_score'] = (
            df['purchases'] * 0.5 +
            df['views'] * 0.3 +
            df['interaction_count'] * 0.2
        )
        logger.info("interest_score engineered")

        # Build matrix with farmer_id, product_name tuples
        buyer_product = df.pivot_table(
            index='buyer_id',
            columns=['farmer_id', 'product_name'],
            values='interest_score',
            fill_value=0
        )
        if not all(isinstance(col, tuple) and len(col) == 2 for col in buyer_product.columns):
            logger.error("Columns are not all 2-element tuples!")
            raise ValueError("Pivot table columns must be (farmer_id, product_name) tuples")
        logger.info(f"Buyer-product matrix shape: {buyer_product.shape}, columns sample: {buyer_product.columns[:5].tolist()}")

        buyer_product_sparse = csr_matrix(buyer_product.values)

        # Dynamic n_factors
        n_buyers = buyer_product.shape[0]
        n_products = buyer_product.shape[1]
        n_factors = max(2, min(10, int(min(n_buyers, n_products) / 2)))
        logger.info(f"Using {n_factors} factors for SVD")

        # Train SVD
        U, sigma, Vt = svds(buyer_product_sparse, k=n_factors)
        sigma = np.diag(sigma)

        # Save model
        model_data = {
            'U': U,
            'sigma': sigma,
            'Vt': Vt,
            'buyer_ids': buyer_product.index.tolist(),
            'product_names': buyer_product.columns.tolist()
        }
        joblib.dump(model_data, model_path)
        logger.info(f"Model trained and saved to {model_path}")

        # Verify saved model
        loaded_data = joblib.load(model_path)
        logger.info(f"Saved product names (first 5): {loaded_data['product_names'][:5]}")

        return "Training completed successfully"
    except Exception as e:
        logger.error(f"Error in train_recommendation_model: {str(e)}")
        raise