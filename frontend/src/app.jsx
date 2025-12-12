import React, { useEffect, useRef } from 'react';
import axios from 'axios';

// Use global Cesium object loaded via CDN
const Cesium = window.Cesium;

// Set Cesium Ion Access Token
Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI1YTJkYTVjNi0zMGRiLTQyZjgtOTE5Ni1hY2I2MDYxYjc3MDMiLCJpZCI6Mjg3NzU2LCJpYXQiOjE3NDU0ODMxMDN9.d1WjC2iKY5za-5Irs6nc2OpUQC6ANn7vA4NOhKGNpMg';

const BACKEND_URL = 'http://localhost:8000';

const App = () => {
  const viewerRef = useRef(null);

  useEffect(() => {
    // Log Cesium to debug availability
    console.log('Cesium:', Cesium);

    // Initialize Cesium Viewer asynchronously
    const initializeViewer = async () => {
      try {
        if (!Cesium || !Cesium.Viewer) throw new Error('Cesium library not available.');

        // Create terrain provider asynchronously
        const terrainProvider = await Cesium.createWorldTerrainAsync();
        console.log('Terrain Provider:', terrainProvider);

        // Try Cesium Ion Imagery Provider for Sentinel-2 (asset ID 5) as an alternative
        let imageryProvider;
        try {
          imageryProvider = await Cesium.IonImageryProvider.fromAssetId(5); // Sentinel-2
          console.log('Imagery Provider (Sentinel-2):', imageryProvider);
        } catch (imgError) {
          console.error('Error loading Sentinel-2 imagery:', imgError);
          // Fallback to Bing Maps Aerial (asset ID 2)
          imageryProvider = await Cesium.IonImageryProvider.fromAssetId(2);
          console.log('Imagery Provider (Bing Maps):', imageryProvider);
        }

        // Initialize the viewer with the terrain and imagery providers
        const viewer = new Cesium.Viewer('cesiumContainer', {
          terrainProvider,
          imageryProvider,
          baseLayerPicker: true,
          geocoder: true,
          homeButton: true,
          sceneModePicker: true,
          navigationHelpButton: true,
          animation: false,
          timeline: false,
        });
        viewerRef.current = viewer;

        // Set initial view to Lincoln County, OR
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(-123.85, 44.65, 50000),
          orientation: { heading: Cesium.Math.toRadians(0), pitch: Cesium.Math.toRadians(-45) },
        });

        // Add DEM terrain from back-end
        const customTerrainProvider = new Cesium.CesiumTerrainProvider({
          url: `${BACKEND_URL}/raster/dem`,
          requestVertexNormals: true,
        });
        viewer.terrainProvider = customTerrainProvider;

        // Add susceptibility heatmap with custom color scale
        const susceptibilityProvider = new Cesium.SingleTileImageryProvider({
          url: `${BACKEND_URL}/raster/susceptibility`,
          rectangle: Cesium.Rectangle.fromDegrees(-124.2, 44.2999944, -123.4999944, 45.0),
          minimumLevel: 0,
          maximumLevel: 14,
          tileWidth: 256,
          tileHeight: 256,
          colorFunc: (value) => {
            const colors = [
              Cesium.Color.GREEN,
              Cesium.Color.YELLOW,
              Cesium.Color.ORANGE,
              Cesium.Color.RED,
              Cesium.Color.fromCssColorString('#8B0000'),
            ];
            return colors[Math.floor(value) - 1] || Cesium.Color.TRANSPARENT;
          },
        });
        const susceptibilityLayer = viewer.imageryLayers.addImageryProvider(susceptibilityProvider);
        susceptibilityLayer.alpha = 0.7;

        // Fetch and add high-susceptibility points
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

        // Click handler for susceptibility prediction
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

        // Cleanup on unmount
        return () => {
          viewer.destroy();
          handler.destroy();
        };
      } catch (error) {
        console.error('Error initializing Cesium Viewer:', error);
        document.getElementById('cesiumContainer').innerHTML = '<p>Error: Failed to initialize Cesium Viewer.</p>';
      }
    };

    // Call the async function
    initializeViewer();
  }, []);

  return null;
};

export default App;