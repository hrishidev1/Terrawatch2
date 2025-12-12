import rasterio
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")  # Suppress warnings for clean output

# File paths
data_dir = "/Users/basithbinazeez/downloads/terrawatch2/data/"
raster_files = {
    "dem": f"{data_dir}dem_fixed.tif",
    "slope": f"{data_dir}slope_corrected.tif",
    "soil_mu": f"{data_dir}soil_mu.tif",
    "roads_dist": f"{data_dir}roads_dist.tif",
    "precipitation": f"{data_dir}precipitation_corrected.tif",
    "nlcd_2019": f"{data_dir}nlcd_2019_corrected.tif"
}
output_tif = f"{data_dir}landslide_susceptibility.tif"

# Read rasters
rasters = {}
meta = None
for name, path in raster_files.items():
    with rasterio.open(path) as src:
        rasters[name] = src.read(1)  # Shape: (2520, 2520)
        if meta is None:
            meta = src.meta.copy()
        if src.crs != "EPSG:4326" or src.shape != (2520, 2520):
            raise ValueError(f"{name}.tif has incorrect CRS or dimensions")

# Create feature matrix
height, width = rasters["dem"].shape
X = np.stack([rasters[name].flatten() for name in raster_files], axis=1)  # Shape: (6350400, 6)

# Handle no-data
nodata_values = {
    "dem": -9999, "slope": -9999, "soil_mu": -9999,
    "roads_dist": 0, "precipitation": -9999, "nlcd_2019": 0
}
mask = np.ones(X.shape[0], dtype=bool)
for i, name in enumerate(raster_files):
    mask &= (X[:, i] != nodata_values[name])
X_valid = X[mask]  # Pixels with no no-data
valid_indices = np.where(mask)[0]

# Check no-data percentage
nodata_percent = (1 - mask.mean()) * 100
print(f"No-data pixels: {nodata_percent:.2f}%")
if nodata_percent > 10:
    print("Warning: High no-data percentage. Consider preprocessing.")

# Standardize numerical features
numerical_cols = ["dem", "slope", "roads_dist", "precipitation"]
numerical_indices = [list(raster_files.keys()).index(name) for name in numerical_cols]
scaler = StandardScaler()
X_valid[:, numerical_indices] = scaler.fit_transform(X_valid[:, numerical_indices])

# K-means clustering
n_clusters = 5  # Low to high susceptibility
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
labels = kmeans.fit_predict(X_valid)

# Assign labels to susceptibility scores (1=low, 5=high)
# Rank clusters by mean slope and precipitation (higher = more susceptible)
cluster_means = np.array([
    X_valid[labels == i][:, [numerical_indices[1], numerical_indices[3]]].mean(axis=0)
    for i in range(n_clusters)
])  # Slope, precipitation
cluster_scores = np.argsort(cluster_means.sum(axis=1)) + 1  # 1 to 5
susceptibility = np.zeros_like(labels, dtype=np.int32)
for i, score in enumerate(cluster_scores):
    susceptibility[labels == i] = score

# Map back to full raster
output = np.zeros(X.shape[0], dtype=np.int32)
output[valid_indices] = susceptibility
output[~mask] = -9999  # No-data
output_raster = output.reshape(height, width)

# Save output
meta.update(dtype=rasterio.int32, nodata=-9999, compress="LZW", tiled=True)
with rasterio.open(output_tif, "w", **meta) as dst:
    dst.write(output_raster, 1)

print(f"Saved landslide susceptibility map to {output_tif}")
print("Values: 1=low, 5=high susceptibility, -9999=no-data")