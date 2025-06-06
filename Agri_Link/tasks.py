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
from datetime import datetime

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
    
    try:
        # 1. Fetch basic crop data
        crops = Crop.objects.all()
        df = read_frame(crops, fieldnames=['id', 'user__id', 'crop_name', 'price_per_unit', 'unit', 'availability'])
        df = df.rename(columns={'user__id': 'farmer_id', 'crop_name': 'product_name'})

        # 2. Get all order data with timestamps (ensure UTC timezone)
        order_crops = OrderCrop.objects.select_related('crop', 'buyer_id').values(
            'crop__id',
            'buyer_id__id',
            'quantity',
            'timestamp'
        )
        order_crops_df = pd.DataFrame(list(order_crops))
        order_crops_df = order_crops_df.rename(columns={
            'crop__id': 'crop_id',
            'buyer_id__id': 'buyer_id'
        })
        # Ensure timestamp is timezone-aware UTC
        order_crops_df['timestamp'] = pd.to_datetime(order_crops_df['timestamp'], utc=True)

        # 3. Calculate buyer purchase metrics
        # Current date in UTC to match order timestamps
        current_date = pd.Timestamp.now(tz='UTC')
        
        purchase_freq_df = order_crops_df.groupby(['crop_id', 'buyer_id']).agg(
            purchase_frequency=('timestamp', 'count'),
            last_purchase_date=('timestamp', 'max'),
            total_quantity=('quantity', 'sum')
        ).reset_index()
        
        # Calculate days since last purchase (both timestamps in UTC)
        purchase_freq_df['days_since_last_purchase'] = (
            (current_date - purchase_freq_df['last_purchase_date']).dt.total_seconds() / (24 * 60 * 60)
        ).round().astype(int)

        # 4. Calculate product-level quantity metrics
        quantity_sold_df = order_crops_df.groupby('crop_id')['quantity'].sum().reset_index()
        quantity_sold_df.columns = ['crop_id', 'quantity_sold']

        # 5. Merge all data
        df = df.merge(quantity_sold_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        df = df.merge(purchase_freq_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])
        
        # 6. Fill NA values
        fill_values = {
            'quantity_sold': 0,
            'purchase_frequency': 0,
            'total_quantity': 0,
            'days_since_last_purchase': 9999,  # Large number for never purchased
            'last_purchase_date': pd.NaT
        }
        df = df.fillna(fill_values)

        # 7. Add location data
        address_df = read_frame(
            UserAddress.objects.all(),
            fieldnames=['user__id', 'district']
        ).rename(columns={'user__id': 'buyer_id', 'district': 'buyer_location'})
        df = df.merge(address_df, on='buyer_id', how='left')
        
        profile_df = read_frame(
            Profile.objects.filter(is_farmer=True),
            fieldnames=['user__id', 'location']
        ).rename(columns={'user__id': 'farmer_id', 'location': 'farmer_location'})
        df = df.merge(profile_df, on='farmer_id', how='left')

        # 8. Add interaction data (ensure UTC timezone)
        logs = UserInteractionLog.objects.all()
        log_df = read_frame(logs, fieldnames=['crop__id', 'action', 'timestamp', 'monthly_stats'])
        log_df = log_df.rename(columns={'crop__id': 'crop_id'})
        log_df = log_df.dropna(subset=['crop_id'])
        log_df['crop_id'] = pd.to_numeric(log_df['crop_id'], errors='coerce').astype('int64')
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], utc=True)
        
        latest_logs = log_df.loc[log_df.groupby('crop_id')['timestamp'].idxmax()]

        interaction_data = []
        for _, log in latest_logs.iterrows():
            monthly_stats = log['monthly_stats']
            interaction_data.append({
                'crop_id': log['crop_id'],
                'views': sum(month['views'] for month in monthly_stats),
                'purchases': sum(month['purchases'] for month in monthly_stats),
                'interaction_count': logs.filter(crop__id=log['crop_id']).count(),
                'highest_purchase_month': max(monthly_stats, key=lambda m: m['purchases'], default={'month': 0})['month'],
                'timestamp': log['timestamp']
            })
        
        interaction_df = pd.DataFrame(interaction_data)
        df = df.merge(interaction_df, left_on='id', right_on='crop_id', how='left').drop(columns=['crop_id'])

        # 9. Fill remaining NA values
        additional_fill_values = {
            'buyer_location': 'Unknown',
            'farmer_location': 'Unknown',
            'views': 0,
            'purchases': 0,
            'interaction_count': 0,
            'highest_purchase_month': 0,
            'timestamp': pd.Timestamp('2025-01-01 00:00:00', tz='UTC')  # Ensure timezone
        }
        df = df.fillna(additional_fill_values)

        # 10. Calculate demand scores
        df['demand_score_raw'] = (
            0.3 * df['quantity_sold'] +
            0.25 * df['purchases'] +
            0.2 * df['views'] +
            0.15 * (1 / (1 + df['days_since_last_purchase'])) +
            0.1 * df['purchase_frequency']
        ).round(6)
        
        scaler = MinMaxScaler()
        df['demand_score'] = scaler.fit_transform(df['demand_score_raw'].values.reshape(-1, 1)).flatten()

        # 11. Define and save output
        output_cols = [
            'id', 'farmer_id', 'product_name', 'price_per_unit', 'unit', 'availability',
            'quantity_sold', 'buyer_id', 'total_quantity', 'purchase_frequency', 
            'days_since_last_purchase', 'last_purchase_date', 'buyer_location', 
            'farmer_location', 'views', 'purchases', 'interaction_count', 
            'highest_purchase_month', 'timestamp', 'demand_score', 'demand_score_raw'
        ]
        
        # Ensure all columns exist before saving
        missing_cols = set(output_cols) - set(df.columns)
        if missing_cols:
            for col in missing_cols:
                df[col] = None
        
        df[output_cols].to_csv(file_path, index=False)
        df[output_cols].to_csv('C:/Users/HP/Desktop/Datasets/agrilink_data.csv', index=False)
        logger.info(f"Successfully exported enhanced data to {file_path}")
        return f"Successfully exported enhanced data to {file_path}"

    except Exception as e:
        logger.error(f"Error in export_data: {str(e)}", exc_info=True)
        raise ValueError(f"Data export failed: {str(e)}")
    
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
            'views', 'interaction_count', 'price_per_unit', 'availability', 'total_quantity', 'purchase_frequency'	
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
            0.3 * df['quantity_sold'] +
            0.25 * df['purchases'] +
            0.2 * df['views'] +
            0.15 * (1 / (1 + df['days_since_last_purchase'])) +
            0.1 * df['purchase_frequency']
        ).round(6)
        logger.info("demand_score_raw engineered")

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

       # Calculate recency weight with a shorter half-life (e.g., 7 days) for more sensitivity
        df['days_since_last_purchase'] = df['days_since_last_purchase'].replace(float('inf'), 365)  # Cap at 1 year for no purchases
        df['recency_weight'] = np.exp(-df['days_since_last_purchase'] / 7)  # Half-life of 7 days


        # Location weighting (slightly adjusted range)
        df['location_weight'] = np.where(
            (df['buyer_location'] == 'Unknown') | (df['farmer_location'] == 'Unknown'),
            0.9,  # Less penalty for unknowns
            np.where(df['buyer_location'] == df['farmer_location'], 1.5, 1.0)  # Moderate boost for local
        )

        df['interest_score'] = (
            0.4 * df['purchase_frequency'] +          # Volume matters most (50%)
            0.3 * df['total_quantity'] +              # Consistency matters (30%)
            0.2 * df['recency_weight'] +
            0.1 * df['views']
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