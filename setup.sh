#!/bin/bash

# Check and initialize Conda
if [ ! -d "/opt/anaconda3" ]; then
    echo "Anaconda not found at /opt/anaconda3. Please check your Anaconda installation path."
    exit 1
fi

source /opt/anaconda3/etc/profile.d/conda.sh
if ! conda info >/dev/null 2>&1; then
    echo "Initializing Conda..."
    conda init bash
    source ~/.bash_profile
fi

# Activate terrademo environment
conda activate terrademo || {
    echo "Failed to activate terrademo environment. Please ensure it exists."
    exit 1
}

# Install back-end dependencies
pip install fastapi uvicorn rasterio numpy scikit-learn

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.bash_profile
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Install Node.js if not present
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    brew install node
fi

# Verify npm
if ! command -v npm &> /dev/null; then
    echo "npm not found after installing Node.js. Please check installation."
    exit 1
fi

# Train K-means model
cd /Users/basithbinazeez/downloads/terrawatch2
python train_kmeans.py || {
    echo "Failed to train K-means model. Check train_kmeans.py output."
    exit 1
}

# Set up front-end project
mkdir -p frontend && cd frontend
npm init -y
npm install react react-dom cesium axios tailwindcss postcss autoprefixer
npm install -D vite@6.3.3 @vitejs/plugin-react vite-plugin-cesium@1.2.23

# Create Vite config
cat > vite.config.js << 'EOL'
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import cesium from 'vite-plugin-cesium';

export default defineConfig({
  plugins: [react(), cesium()],
  server: { port: 3000, strictPort: false },
  define: { CESIUM_BASE_URL: JSON.stringify('/cesium') },
  resolve: {
    alias: { cesium: 'cesium/Build/Cesium/Cesium.js' },
  },
  optimizeDeps: { include: ['cesium'] },
});
EOL

# Initialize Tailwind CSS
npx tailwindcss init -p

# Update tailwind.config.js
cat > tailwind.config.js << 'EOL'
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {} },
  plugins: [],
};
EOL

# Create src directory and new files
mkdir -p src
cat > src/main.jsx << 'EOL'
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('cesiumContainer')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
EOL

cat > src/App.jsx << 'EOL'
import React, { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import axios from 'axios';
import 'cesium/Build/Cesium/Widgets/widgets.css';

// Replace with your Cesium Ion Access Token from cesium.com/ion
Cesium.Ion.defaultAccessToken = 'YOUR_CESIUM_ION_TOKEN';

const BACKEND_URL = 'http://localhost:8000';

const App = () => {
  const viewerRef = useRef(null);

  useEffect(() => {
    console.log('Cesium:', Cesium);
    try {
      if (!Cesium || !Cesium.Viewer) throw new Error('Cesium library not available.');
      const viewer = new Cesium.Viewer('cesiumContainer', {
        terrainProvider: Cesium.createWorldTerrain(),
        imageryProvider: Cesium.createOpenStreetMapImageryProvider(),
        baseLayerPicker: true,
        geocoder: true,
        homeButton: true,
        sceneModePicker: true,
        navigationHelpButton: true,
        animation: false,
        timeline: false,
      });
      viewerRef.current = viewer;

      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(-123.85, 44.65, 50000),
        orientation: { heading: Cesium.Math.toRadians(0), pitch: Cesium.Math.toRadians(-45) },
      });

      const terrainProvider = new Cesium.CesiumTerrainProvider({
        url: `${BACKEND_URL}/raster/dem`,
        requestVertexNormals: true,
      });
      viewer.terrainProvider = terrainProvider;

      const susceptibilityProvider = new Cesium.SingleTileImageryProvider({
        url: `${BACKEND_URL}/raster/susceptibility`,
        rectangle: Cesium.Rectangle.fromDegrees(-124.2, 44.2999944, -123.4999944, 45.0),
        minimumLevel: 0,
        maximumLevel: 14,
        tileWidth: 256,
        tileHeight: 256,
        colorFunc: (value) => {
          const colors = [Cesium.Color.GREEN, Cesium.Color.YELLOW, Cesium.Color.ORANGE, Cesium.Color.RED, Cesium.Color.fromCssColorString('#8B0000')];
          return colors[Math.floor(value) - 1] || Cesium.Color.TRANSPARENT;
        },
      });
      viewer.imageryLayers.addImageryProvider(susceptibilityProvider).alpha = 0.7;

      axios.get(`${BACKEND_URL}/high_susceptibility_points`)
        .then(response => response.data.points.forEach(point =>
          viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(point.longitude, point.latitude, 100),
            point: { pixelSize: 8, color: Cesium.Color.PURPLE, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
            label: {
              text: 'High Risk', font: '12px sans-serif', fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK, outlineWidth: 1, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -10),
            },
          })
        ))
        .catch(error => console.error('Error fetching points:', error));

      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction(async (click) => {
        const cartesian = viewer.camera.pickEllipsoid(click.position);
        if (cartesian) {
          const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
          const lon = Cesium.Math.toDegrees(cartographic.longitude);
          const lat = Cesium.Math.toDegrees(cartographic.latitude);
          try {
            const response = await axios.get(`${BACKEND_URL}/susceptibility/predict?lat=${lat}&lon=${lon}`);
            document.getElementById('susceptibilityInfo').innerHTML = `
              <p><strong>Latitude:</strong> ${lat.toFixed(4)}</p>
              <p><strong>Longitude:</strong> ${lon.toFixed(4)}</p>
              <p><strong>Susceptibility:</strong> ${response.data.susceptibility} (1=Low, 5=High)</p>
            `;
          } catch (error) {
            document.getElementById('susceptibilityInfo').innerHTML = `<p>Error: ${error.response?.data?.detail || 'Prediction failed'}</p>`;
          }
        }
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      return () => { viewer.destroy(); handler.destroy(); };
    } catch (error) {
      console.error('Error initializing Cesium Viewer:', error);
      document.getElementById('cesiumContainer').innerHTML = '<p>Error: Failed to initialize Cesium Viewer.</p>';
    }
  }, []);

  return null;
};

export default App;
EOL

cat > index.html << 'EOL'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TERRAWATCH - Landslide Susceptibility Map</title>
  <style>
    html, body, #cesiumContainer { width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; }
    #sidebar { position: absolute; top: 10px; left: 10px; background: rgba(255, 255, 255, 0.9); padding: 10px; border-radius: 5px; max-width: 300px; }
  </style>
</head>
<body class="bg-gray-100">
  <div id="cesiumContainer"></div>
  <div id="sidebar" class="text-gray-800">
    <h2 class="text-lg font-bold">TERRAWATCH</h2>
    <p>Landslide Susceptibility Map - Lincoln County, OR</p>
    <div id="susceptibilityInfo" class="mt-2"></div>
  </div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
EOL

# Update package.json
cat > package.json << 'EOL'
{
  "name": "terrawatch-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "cesium": "^1.114.0",
    "axios": "^1.6.8",
    "tailwindcss": "^3.4.1",
    "postcss": "^8.4.38",
    "autoprefixer": "^10.4.19"
  },
  "devDependencies": {
    "vite": "^6.3.3",
    "@vitejs/plugin-react": "^4.2.1",
    "vite-plugin-cesium": "^1.2.23"
  }
}
EOL

# Start back end in background
cd ..
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Start front end in background
cd frontend
npm run dev &

echo "Setup complete. Back end running at http://localhost:8000, front end at http://localhost:3000"
echo "Please open http://localhost:3000 in Chrome to view the demo."