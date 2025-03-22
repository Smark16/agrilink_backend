from django.core.management.base import BaseCommand
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
import joblib
from fuzzywuzzy import fuzz, process

class Command(BaseCommand):
    help = 'Train and save SVD recommendation model from CSV'

    def preprocess_text(self, text):
        """Basic normalization of product names."""
        return str(text).lower().strip()

    def group_similar_names(self, product_names, threshold=80):
        """Group similar product names into a general name."""
        groups = {}
        product_names = list(set(product_names))  # Unique names
        for name in product_names:
            if not isinstance(name, str) or name.strip() == "":
                continue
            name = self.preprocess_text(name)
            if not groups:
                groups[name] = name
                continue
            match_result = process.extractOne(name, list(groups.keys()), scorer=fuzz.partial_ratio)
            if match_result and match_result[1] >= threshold:
                groups[name] = groups[match_result[0]]
            else:
                groups[name] = name
        return groups

    def handle(self, *args, **kwargs):
        # Load latest data from CSV
        csv_path = 'C:/Users/HP/Desktop/Datasets/agrilink_data.csv'
        df = pd.read_csv(csv_path)
        if df.empty:
            self.stdout.write(self.style.WARNING('No data in CSV'))
            return

        # Basic data cleaning
        df.fillna(0, inplace=True)  # Replace NaNs with 0

        # Engineer general_name from product_name
        product_names = df['product_name'].unique()
        similar_names = self.group_similar_names(product_names, threshold=80)
        df['general_name'] = df['product_name'].apply(lambda x: similar_names.get(self.preprocess_text(x), x))

        # Feature engineering
        df['interest_score'] = (df['purchases'] * 0.5 + 
                               df['views'] * 0.3 + 
                               df['interaction_count'] * 0.2)

        # Build buyer-product matrix
        buyer_product = df.pivot_table(
            index='buyer_id',
            columns='general_name',
            values='interest_score',
            fill_value=0
        )
        buyer_product_sparse = csr_matrix(buyer_product.values)

        # Dynamic n_factors
        n_buyers = buyer_product.shape[0]
        n_products = buyer_product.shape[1]
        n_factors = max(2, min(10, int(min(n_buyers, n_products) / 2)))

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
        joblib.dump(model_data, 'Agri_Link/svd_recommendation_model.pkl')
        self.stdout.write(self.style.SUCCESS('Model trained and saved'))