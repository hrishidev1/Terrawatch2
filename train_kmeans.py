import rasterio
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import pickle
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("/Users/basithbinazeez/downloads/terrawatch2/data")
RASTER_FILES = [
    "dem_fixed.tif",
    "slope_corrected.tif",
    "precipitation_corrected.tif",
    "soil_mu.tif",
    "nlcd_2019_corrected.tif",
    "roads_dist.tif",
]

def compute_curvature(dem):
    """Compute simplified curvature from DEM using second derivative."""
    try:
        kernel = np.array([[1, -2, 1]])
        curvature_x = np.apply_along_axis(lambda x: np.convolve(x, kernel.flatten(), mode="same"), 0, dem)
        curvature_y = np.apply_along_axis(lambda x: np.convolve(x, kernel.flatten(), mode="same"), 1, dem)
        logger.info("Computed curvature feature")
        return curvature_x + curvature_y
    except Exception as e:
        logger.error(f"Error computing curvature: {str(e)}")
        raise

def load_and_preprocess():
    """Load and preprocess raster data, including curvature and no-data imputation."""
    data = []
    nodata_values = []
    
    logger.info("Loading raster data")
    for raster_file in RASTER_FILES:
        raster_path = DATA_DIR / raster_file
        if not raster_path.exists():
            logger.error(f"Raster file not found: {raster_path}")
            raise FileNotFoundError(f"Raster file not found: {raster_path}")
        
        with rasterio.open(raster_path) as src:
            array = src.read(1).astype(np.float32)
            nodata = src.nodata if src.nodata is not None else -9999
            nodata_values.append(nodata)
            if raster_file == "dem_fixed.tif":
                curvature = compute_curvature(array)
                data.append(curvature)  # Add curvature
                nodata_values.append(nodata)  # Use dem.tif nodata for curvature
            data.append(array)
    
    # Stack features
    data = np.stack(data, axis=-1)  # Shape: (height, width, n_features)
    height, width, n_features = data.shape
    logger.info(f"Loaded {n_features} features with shape {height}x{width}")
    
    # Create mask for valid data
    nodata_mask = np.any([data[:, :, i] == nodata_values[i] for i in range(n_features)], axis=0)
    nodata_percentage = (nodata_mask.sum() / nodata_mask.size) * 100
    logger.info(f"No-data pixels: {nodata_percentage:.2f}%")
    
    # Impute no-data
    for i in range(n_features):
        raster_name = "curvature" if i == 0 else RASTER_FILES[(i - 1) % len(RASTER_FILES)]
        if raster_name in ["soil_mu.tif", "nlcd_2019_corrected.tif"]:
            valid_data = data[:, :, i][~nodata_mask].astype(int)
            if valid_data.size > 0:
                mode_val = np.bincount(valid_data.ravel()).argmax()
            else:
                mode_val = 0
                logger.warning(f"No valid data for {raster_name}, using default mode 0")
            data[:, :, i][nodata_mask] = mode_val
        else:
            valid_data = data[:, :, i][~nodata_mask]
            if valid_data.size > 0:
                median_val = np.nanmedian(valid_data)
            else:
                median_val = 0
                logger.warning(f"No valid data for {raster_name}, using default median 0")
            data[:, :, i][nodata_mask] = median_val
        logger.info(f"Imputed no-data for feature {raster_name}")
    
    # Normalize features
    features = data.reshape(-1, n_features)
    means = np.mean(features, axis=0)
    stds = np.std(features, axis=0)
    stds[stds == 0] = 1  # Avoid division by zero
    features = (features - means) / stds
    logger.info("Normalized features")
    
    # Save stats for prediction
    stats_path = DATA_DIR / "feature_stats.pkl"
    with open(stats_path, "wb") as f:
        pickle.dump({"mean": means, "std": stds}, f)
    logger.info(f"Saved feature stats to {stats_path}")
    
    return features, nodata_mask, height, width, nodata_values

def train_kmeans():
    """Train K-means model and save susceptibility raster."""
    try:
        features, nodata_mask, height, width, nodata_values = load_and_preprocess()
        
        # Train K-means on valid data
        valid_features = features[~nodata_mask.flatten()]
        if valid_features.shape[0] == 0:
            logger.error("No valid data available for training after preprocessing")
            raise ValueError("No valid data available for training after preprocessing")
        
        logger.info(f"Training K-means on {valid_features.shape[0]} valid pixels")
        kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
        labels = kmeans.fit_predict(valid_features)
        
        # Evaluate
        sample_size = min(valid_features.shape[0], 10000)
        silhouette = silhouette_score(valid_features, labels, sample_size=sample_size)
        logger.info(f"Silhouette Score: {silhouette:.3f}")
        
        # Assign labels to all pixels
        full_labels = np.full(nodata_mask.shape, -9999, dtype=np.int32)
        full_labels[~nodata_mask] = labels + 1  # 1–5 scale
        full_labels = full_labels.reshape(height, width)
        
        # Save model
        model_path = DATA_DIR / "kmeans_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(kmeans, f)
        logger.info(f"Saved K-means model to {model_path}")
        
        # Save susceptibility raster
        output_path = DATA_DIR / "landslide_susceptibility.tif"
        with rasterio.open(DATA_DIR / RASTER_FILES[0]) as src:
            profile = src.profile
            profile.update(dtype=rasterio.int32, nodata=-9999)
            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(full_labels, 1)
        logger.info(f"Saved susceptibility raster to {output_path}")
    
    except Exception as e:
        logger.error(f"Error in train_kmeans: {str(e)}")
        raise

if __name__ == "__main__":
    train_kmeans()