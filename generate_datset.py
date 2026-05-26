import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

start_date = datetime(2023,1,1)
days = 1100

dates = [start_date + timedelta(days=i) for i in range(days)]

zones = [
    "North Delhi",
    "South Delhi",
    "East Delhi",
    "West Delhi",
    "Central Delhi"
]

population = 32000000

data = []

for d in dates:

    zone = random.choice(zones)

    temperature = np.random.normal(32,5)
    rainfall = max(0,np.random.normal(10,6))
    industrial_index = np.random.uniform(60,90)

    water_demand = (
        population*150
        + temperature*100000
        - rainfall*50000
        + industrial_index*200000
        + np.random.normal(0,2000000)
    )

    data.append([
        d,
        zone,
        population,
        temperature,
        rainfall,
        industrial_index,
        water_demand
    ])

df = pd.DataFrame(data, columns=[
    "date",
    "zone",
    "population",
    "temperature",
    "rainfall",
    "industrial_index",
    "water_demand"
])

df.to_csv("delhi_water_dataset.csv", index=False)

print("Dataset created successfully")