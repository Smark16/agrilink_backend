# recommendations/recommendation_utils.py
import joblib
import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz, process
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

import logging

logger = logging.getLogger(__name__)


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

def get_data():
    csv_path = 'C:/Users/HP/Desktop/Datasets/agrilink_data.csv'  # Update to your expanded CSV
    df = pd.read_csv(csv_path)
    df.fillna(0, inplace=True)
    
    # Engineer general_name
    product_names = df['product_name'].unique()
    similar_names = group_similar_names(product_names, threshold=80)
    df['general_name'] = df['product_name'].apply(lambda x: similar_names.get(preprocess_text(x), x))
    
    # Engineer demand_score_raw (ensure required columns exist)
    required_cols = ['quantity_sold', 'purchases', 'views', 'interaction_count']
    if all(col in df.columns for col in required_cols):
        df['demand_score_raw'] = (
            0.4 * df['quantity_sold'] +
            0.3 * df['purchases'] +
            0.2 * df['views'] +
            0.1 * df['interaction_count']
        ).round(6)
    else:
        raise ValueError(f"Missing required columns for demand_score_raw: {', '.join(set(required_cols) - set(df.columns))}")
    
    # Calculate interest_score
    df['interest_score'] = (
        df['purchases'] * 0.5 +
        df['views'] * 0.3 +
        df['interaction_count'] * 0.2
    ) * df.apply(lambda row: 2.0 if row['buyer_location'] == row['farmer_location'] else 1.0, axis=1)
    
    return df

def load_recommendation_model(model_path='Agri_Link/svd_recommendation_model.pkl'):
    try:
        model_data = joblib.load(model_path)
        print(f"Debug: Loaded model_data keys: {list(model_data.keys())}")  # Debug
        U, sigma, Vt = model_data['U'], model_data['sigma'], model_data['Vt']
        buyer_ids = model_data['buyer_ids']
        product_keys = model_data['product_names']
        predicted_affinity = np.dot(np.dot(U, sigma), Vt)
        affinity_df = pd.DataFrame(predicted_affinity, index=buyer_ids, columns=product_keys)
        print(f"Debug: Returning affinity_df shape: {affinity_df.shape}, buyer_ids len: {len(buyer_ids)}, product_keys len: {len(product_keys)}")  # Debug
        return affinity_df, buyer_ids, product_keys  # Ensure three values are returned
    except Exception as e:
        raise ValueError(f"Error loading model: {str(e)}")

def get_avg_demand(product_name, df, farmer_id=None):
    if farmer_id:
        raw_scores = df[(df['general_name'] == product_name) & (df['farmer_id'] == farmer_id)]['demand_score_raw']
    else:
        raw_scores = df[df['general_name'] == product_name]['demand_score_raw']
    if raw_scores.empty:
        return 'N/A'
    avg_score = raw_scores.mean()
    if avg_score < 6:
        return 'low'
    elif 6 <= avg_score <= 12:
        return 'moderate'
    else:
        return 'high'
    
def recommend_buyers_for_farmer_product(farmer_id, product_name, affinity_df, df, threshold=0.01):
    """
    Recommend all buyers interested in a product's general_name, regardless of farmer.
    """
    try:
        # Match product_name to general_name
        product_name = preprocess_text(product_name)
        general_names = df['general_name'].unique()
        match = process.extractOne(product_name, general_names, scorer=fuzz.partial_ratio)
        general_name = match[0] if match and match[1] >= 80 else product_name
        logger.info(f"Matched {product_name} to general_name: {general_name}")

        # Find all products with this general_name
        matching_products = df[df['general_name'] == general_name][['farmer_id', 'product_name']].drop_duplicates()
        matching_columns = [
            (row['farmer_id'], row['product_name'])
            for _, row in matching_products.iterrows()
            if (row['farmer_id'], row['product_name']) in affinity_df.columns
        ]
        
        if not matching_columns:
            logger.warning(f"No matching products found for general_name: {general_name}")
            return []

        # Aggregate affinity scores across all matching products
        product_scores = affinity_df[matching_columns]
        buyer_scores = product_scores.mean(axis=1)  # Average across all farmers' products
        interested_buyers = buyer_scores[buyer_scores > threshold].sort_values(ascending=False)
        buyer_ids = interested_buyers.index.tolist()
        
        logger.info(f"Buyers interested in {general_name}: {buyer_ids}")
        return buyer_ids  # Return list of buyer IDs
    except Exception as e:
        logger.error(f"Error in recommend_buyers_for_farmer_product: {str(e)}")
        raise

def Interested_buyers_for_farmer_product(farmer_id, affinity_df, df, product_name=None, top_n=3, threshold=0.01):
    if product_name:
        farmer_products = [product_name]
    else:
        farmer_products = df[df['farmer_id'] == farmer_id]['product_name'].unique()
    
    result = []
    for product_name in farmer_products:
        product_name = preprocess_text(product_name)
        filtered_df = df[(df['farmer_id'] == farmer_id) & (df['product_name'] == product_name)]
        if filtered_df.empty:
            general_name = process.extractOne(product_name, df['general_name'].unique(), scorer=fuzz.partial_ratio)[0]
        else:
            general_name = filtered_df['general_name'].iloc[0]
        
        matching_columns = [
            (fid, pname) for fid, pname in affinity_df.columns 
            if not df[(df['farmer_id'] == fid) & (df['product_name'] == pname)].empty and 
               df[(df['farmer_id'] == fid) & (df['product_name'] == pname)]['general_name'].iloc[0] == general_name
        ]
        
        if not matching_columns:
            result.append({
                'product_name': product_name,
                'buyer_id': [],
                'confidence_score': [],
                'market_demand': get_avg_demand(general_name, df, farmer_id=None)
            })
            continue
        
        buyer_scores = affinity_df[matching_columns].mean(axis=1).sort_values(ascending=False)
        interested_buyers = buyer_scores[buyer_scores > threshold].head(top_n)
        max_score = buyer_scores.max() if buyer_scores.max() > 0 else 1
        confidence_scores = (interested_buyers / max_score * 100).tolist()
        product_demand = get_avg_demand(general_name, df, farmer_id=None)
        
        result.append({
            'product_name': product_name,
            'buyer_id': interested_buyers.index.tolist(),
            'confidence_score': [round(score, 1) for score in confidence_scores],
            'market_demand': product_demand
        })
    
    return result

def recommend_products_for_buyer(buyer_id, affinity_df, df, top_n=3, threshold=0.01):
    logger.info(f"Starting recommendation for buyer_id: {buyer_id}")
    if buyer_id not in affinity_df.index:
        logger.warning(f"Buyer {buyer_id} not in affinity_df index")
        return {'general_name': [], 'confidence_score': []}
    
    buyer_scores = affinity_df.loc[buyer_id]
    logger.info(f"Buyer scores type: {type(buyer_scores)}, length: {len(buyer_scores)}")
    general_scores = {}
    try:
        for idx, score in buyer_scores.items():
            logger.info(f"Processing index: {idx}, score: {score}")
            farmer_id, product_name = idx  # Explicit unpacking
            general_name = df[(df['farmer_id'] == farmer_id) & (df['product_name'] == product_name)]['general_name'].iloc[0]
            general_scores[general_name] = general_scores.get(general_name, 0) + max(score, 0)
    except ValueError as e:
        logger.error(f"Unpacking error: {str(e)}, index: {idx}")
        raise
    
    sorted_scores = pd.Series(general_scores).sort_values(ascending=False)
    top_products = sorted_scores[sorted_scores > threshold].head(top_n)
    
    logger.info(f"Top products: {top_products.to_dict()}")
    return {
        'general_name': top_products.index.tolist(),
        'confidence_score': [round(score / sorted_scores.max() * 100, 1) for score in top_products] if sorted_scores.max() > 0 else []
    }