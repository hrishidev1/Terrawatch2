import rasterio
import numpy as np
import plotly.graph_objects as go

# File paths
dem_path = "/Users/basithbinazeez/downloads/terrawatch2/data/dem_fixed.tif"
susceptibility_path = "/Users/basithbinazeez/downloads/terrawatch2/data/landslide_susceptibility.tif"

# Read rasters
with rasterio.open(dem_path) as dem_src:
    dem = dem_src.read(1)
    dem_nodata = dem_src.nodata
    dem = dem.astype(np.float32)  # Ensure float for NaN
    dem[dem == dem_nodata] = np.nan  # Convert no-data to NaN

with rasterio.open(susceptibility_path) as sus_src:
    sus = sus_src.read(1)
    sus_nodata = sus_src.nodata
    sus_mask = sus == sus_nodata  # Mask for no-data
    nodata_percent = (sus_mask.sum() / sus.size) * 100
    print(f"No-data pixels in landslide_susceptibility.tif: {nodata_percent:.2f}%")

# Create coordinate grids (degrees)
height, width = dem.shape  # 2520 x 2520
x = np.linspace(-124.2, -123.4999944, width)
y = np.linspace(45.0, 44.2999944, height)
X, Y = np.meshgrid(x, y)

# Create color array for surface (handle no-data)
sus_color = sus.astype(np.float32)  # Copy as float for coloring
sus_color[sus_mask] = np.nan  # No-data as NaN for Plotly

# Create 3D surface (elevation colored by susceptibility)
colorscale = [
    [0, "green"],  # 1: Low susceptibility
    [0.25, "yellow"],
    [0.5, "orange"],
    [0.75, "red"],
    [1, "darkred"]  # 5: High susceptibility
]
surface = go.Surface(
    x=X, y=Y, z=dem,
    surfacecolor=sus_color,
    colorscale=colorscale,
    cmin=1, cmax=5,
    colorbar=dict(title="Susceptibility (1=Low, 5=High)"),
    showscale=True
)

# Highlight high-susceptibility points (value = 5) as proxies for landslide points
high_sus_mask = sus == 5
scatter = go.Scatter3d(
    x=X[high_sus_mask], y=Y[high_sus_mask], z=dem[high_sus_mask],
    mode="markers",
    marker=dict(size=5, color="purple", opacity=0.8),
    name="High Susceptibility (5)"
)

# Layout
layout = go.Layout(
    title="3D Landslide Susceptibility Map (Lincoln County, OR)",
    scene=dict(
        xaxis_title="Longitude (degrees)",
        yaxis_title="Latitude (degrees)",
        zaxis_title="Elevation (m)",
        aspectratio=dict(x=1, y=1, z=1)  # Increase z-axis scale
    ),
    width=1200,  # Larger figure size
    height=800,
    showlegend=True
)

# Plot
fig = go.Figure(data=[surface, scatter], layout=layout)
fig.write_html("/Users/basithbinazeez/downloads/terrawatch2/landslide_susceptibility_3d.html")
print("Saved 3D visualization to /Users/basithbinazeez/downloads/terrawatch2/landslide_susceptibility_3d.html")