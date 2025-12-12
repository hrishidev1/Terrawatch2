from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import rasterio
import numpy as np
from sklearn.cluster import KMeans
from pathlib import Path
import pickle
import os

app = FastAPI(title="TERRAWATCH API")

DATA_DIR = Path("/Users/basithbinazeez/downloads/terrawatch2/data")
RASTERS = {
    "dem": DATA_DIR / "dem_fixed.tif",
    "susceptibility": DATA_DIR / "landslide_susceptibility.tif",
    "soil_mu": DATA_DIR / "soil_mutif",
}
MODEL_PATH = DATA_DIR / "kmeans_model.pkl"

# Load pre-trained K-means model
if MODEL_PATH.exists():
    with open(MODEL_PATH, "rb") as f:
        kmeans = pickle.load(f)
else:
    kmeans = None

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/raster/{raster_type}")
async def get_raster(raster_type: str):
    if raster_type not in RASTERS:
        raise HTTPException(status_code=404, detail="Raster type not found")
    raster_path = RASTERS[raster_type]
    if not raster_path.exists():
        raise HTTPException(status_code=404, detail="Raster file not found")
    return FileResponse(raster_path, media_type="image/tiff")

@app.get("/susceptibility/predict")
async def predict_susceptibility(lat: float, lon: float):
    if not kmeans:
        raise HTTPException(status_code=503, detail="K-means model not loaded")
    try:
        # Load raster data at the point
        features = []
        for raster_type in ["dem_fixed", "slope_corrected", "precipitation_corrected", "soil_mu", "nlcd_2019_corrected", "roads_dist"]:
            with rasterio.open(DATA_DIR / f"{raster_type}.tif") as src:
                row, col = src.index(lon, lat)
                value = src.read(1)[row, col]
                if value == src.nodata:
                    raise HTTPException(status_code=400, detail=f"No data at {lat}, {lon} for {raster_type}")
                features.append(value)
        
        # Normalize features (using precomputed means/std from training)
        with open(DATA_DIR / "feature_stats.pkl", "rb") as f:
            stats = pickle.load(f)
        features = [(f - stats["mean"][i]) / stats["std"][i] for i, f in enumerate(features)]
        
        # Apply weights
        weights = [0.1, 0.3, 0.3, 0.15, 0.05, 0.1]  # dem, slope, precipitation, soil, nlcd, roads
        weighted_features = [f * w for f, w in zip(features, weights)]
        
        # Predict
        prediction = kmeans.predict([weighted_features])[0] + 1  # 1–5 scale
        return {"latitude": lat, "longitude": lon, "susceptibility": int(prediction)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.get("/high_susceptibility_points")
async def get_high_susceptibility_points():
    try:
        with rasterio.open(RASTERS["susceptibility"]) as src:
            sus = src.read(1)
            transform = src.transform
            high_sus_mask = sus == 5
            rows, cols = np.where(high_sus_mask)
            points = []
            for row, col in zip(rows, cols):
                lon, lat = rasterio.transform.xy(transform, row, col)
                points.append({"latitude": lat, "longitude": lon})
            return {"points": points}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching points: {str(e)}")