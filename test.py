import rasterio
import numpy as np

with rasterio.open("/Users/basithbinazeez/downloads/terrawatch2/data/soil_mu_temp.tif") as src:
    data = src.read(1)
    nodata = src.nodata
    valid_data = data[data != nodata] if nodata is not None else data
    nodata_count = np.sum(data == nodata) if nodata is not None else 0
    total_pixels = data.size
    unique_mukeys = np.unique(valid_data)
    print("--- New soil_mu.tif ---")
    print("CRS:", src.crs)
    print("Bounds:", src.bounds)
    print("Resolution (degrees):", src.res)
    print("Width (pixels):", src.width)
    print("Height (pixels):", src.height)
    print("Total pixels:", src.width * src.height)
    print("Data type:", src.dtypes)
    print("Unique MUKEYs:", len(unique_mukeys), unique_mukeys)
    print("No-data value:", nodata)
    print(f"No-data pixels: {nodata_count} ({nodata_count/total_pixels*100:.2f}%)")