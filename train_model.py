import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error
import joblib

# -----------------------------
# Load Dataset
# -----------------------------

data = pd.read_csv("delhi_water_dataset.csv")

# -----------------------------
# Feature Engineering
# -----------------------------

# Convert date column
data['date'] = pd.to_datetime(data['date'])

data['month'] = data['date'].dt.month
data['day'] = data['date'].dt.day

# Encode zone column
le = LabelEncoder()
data['zone_encoded'] = le.fit_transform(data['zone'])

# -----------------------------
# Select Features
# -----------------------------

X = data[['population', 'temperature', 'rainfall', 'industrial_index', 'month', 'day', 'zone_encoded']]
y = data['water_demand']

# -----------------------------
# Train Test Split
# -----------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -----------------------------
# Train Model
# -----------------------------

model = RandomForestRegressor(
    n_estimators=200,
    max_depth=10,
    random_state=42
)

model.fit(X_train, y_train)

# -----------------------------
# Evaluate Model
# -----------------------------

predictions = model.predict(X_test)

r2 = r2_score(y_test, predictions)
mae = mean_absolute_error(y_test, predictions)

print("\nModel Training Complete")
print("R2 Score:", r2)
print("Mean Absolute Error:", mae)

# -----------------------------
# Save Model
# -----------------------------

joblib.dump(model, "water_demand_model.pkl")
joblib.dump(le, "zone_encoder.pkl")

print("\nModel saved as water_demand_model.pkl")
print("Zone encoder saved as zone_encoder.pkl")