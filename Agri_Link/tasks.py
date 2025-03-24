from celery import shared_task
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
import joblib
from fuzzywuzzy import fuzz, process
from django_pandas.io import read_frame
from sklearn.preprocessing import MinMaxScaler
from Agri_Link.models import Crop, PaymentDetails, UserInteractionLog, Order, OrderDetail, OrderCrop, UserAddress, Profile
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

    # Fetch address for buyers
    address = UserAddress.objects.all()
    add_df = read_frame(address, fieldnames=['user__id', 'district'])
    add_df = add_df.rename(columns={'user__id': 'buyer_id', 'district': 'buyer_location'})
    df = df.merge(add_df[['buyer_id', 'buyer_location']], on='buyer_id', how='left')
    df['buyer_location'] = df['buyer_location'].fillna('Unknown')

    # Fetch profile for farmers
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

    # Sort by timestamp for latest log
    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], utc=True)
    latest_logs = log_df.loc[log_df.groupby('crop_id')['timestamp'].idxmax()]

    # Calculate metrics
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

    # Fill NaN values
    df['views'] = df['views'].fillna(0)
    df['purchases'] = df['purchases'].fillna(0)
    df['interaction_count'] = df['interaction_count'].fillna(0)
    df['highest_purchase_month'] = df['highest_purchase_month'].fillna(0).astype(int)
    df['timestamp'] = df['timestamp'].fillna(pd.Timestamp('2025-01-01 00:00:00', tz='UTC'))
    df['buyer_id'] = df['buyer_id'].fillna('None')

    # Calculate demand score and preserve raw value

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

         # Initialize the scaler
        scaler = MinMaxScaler()

        # List of numerical fields to normalize
        numerical_fields = [
            'demand_score', 'quantity_sold', 'purchases', 
            'views', 'interaction_count', 'price_per_unit', 'availability'
        ]

        # Normalize each field
        for field in numerical_fields:
            df[field] = scaler.fit_transform(df[field].values.reshape(-1, 1)).flatten()

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

        # df['demand_score'] = scaler.fit_transform(df['demand_score_raw'].values.reshape(-1, 1)).flatten()
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

        # Adjust interest_score with stronger location weighting
        df['location_weight'] = np.where(
        (df['buyer_location'] == 'Unknown') | (df['farmer_location'] == 'Unknown'),
        0.8,
        np.where(df['buyer_location'] == df['farmer_location'], 2.0, 1.0)
    )

        df['interest_score'] = (
        df['purchases'] * 0.5 +
        df['views'] * 0.3 +
        df['interaction_count'] * 0.2
    ) * df['location_weight']
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
        n_buyers, n_products = buyer_product_sparse.shape
        logger.info(f"Matrix dimensions: {n_buyers} buyers, {n_products} products")

        # Check if matrix is too small for SVD
        min_dim = min(n_buyers, n_products)
        if min_dim <= 1:
            logger.warning(f"Matrix too small for SVD: {n_buyers}x{n_products}")
            return f"Insufficient data for SVD: Matrix size {n_buyers}x{n_products}"

        # Dynamically set n_factors ensuring 0 < k < min_dim
        n_factors = max(1, min(10, min_dim - 1))  # Ensure k is at least 1 and less than min_dim
        logger.info(f"Using {n_factors} factors for SVD (min_dim: {min_dim})")

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