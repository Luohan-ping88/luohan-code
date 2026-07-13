"""Debug feature column mismatch"""
from core.data_collector import PL5DataCollector
from core.feature_engineering import FeatureEngineer

collector = PL5DataCollector()
df = collector.load_processed_data()
print(f"Processed data shape: {df.shape}")
print(f"Processed data columns: {list(df.columns[:10])}...")

engineer = FeatureEngineer()
df_features = engineer.extract_all_features(df)
cols = list(df_features.columns)
print(f"\nTotal columns in df_features: {len(cols)}")

exclude = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']
feature_cols = [c for c in cols if c not in exclude]
print(f"After excluding {exclude}: {len(feature_cols)}")
print(f"full_number in feature_cols: {'full_number' in feature_cols}")

# Check what analyze_and_send.py uses
# It uses: non_feature_cols = ['period', 'full_number'] + [p for p in positions]
positions = ['wan', 'qian', 'bai', 'shi', 'ge']
non_feature_cols2 = ['period', 'full_number'] + positions
feature_cols2 = [c for c in cols if c not in non_feature_cols2]
print(f"\nanalyze_and_send exclude list: {non_feature_cols2}")
print(f"analyze_and_send feature count: {len(feature_cols2)}")
print(f"Difference: {set(feature_cols) - set(feature_cols2)}")
