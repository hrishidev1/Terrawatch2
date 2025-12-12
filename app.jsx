import React, { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import axios from 'axios';
import 'cesium/Build/Cesium/Widgets/widgets.css';

// Replace with your Cesium Ion Access Token from cesium.com/ion
Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJhNDM4OWE2MC03M2ExLTQyODItYmM4MC1lNzNhNzA5OWY1ZTQiLCJpZCI6Mjg3NzU2LCJpYXQiOjE3NDUxNTc5Nzh9.vCPzMNXwoMTUSvReTQ1Go0hRi7FFPxUDvw7H4IkbZp8';

const BACKEND_URL = 'http://localhost:8000';

const App = () => {
  const viewerRef = useRef(null);

  useEffect(() => {
    // Log Cesium to debug import issues
    console.log('Cesium:', Cesium);

    // Initialize Cesium Viewer
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

      // Set initial view to Lincoln County, OR
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(-123.85, 44.65, 50000),
        orientation: { heading: Cesium.Math.toRadians(0), pitch: Cesium.Math.toRadians(-45) },
      });

      // Add DEM terrain
      const terrainProvider = new Cesium.CesiumTerrainProvider({
        url: `${BACKEND_URL}/raster/dem`,
        requestVertexNormals: true,
      });
      viewer.terrainProvider = terrainProvider;

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

      return () => { viewer.destroy(); handler.destroy(); };
    } catch (error) {
      console.error('Error initializing Cesium Viewer:', error);
      document.getElementById('cesiumContainer').innerHTML = '<p>Error: Failed to initialize Cesium Viewer.</p>';
    }
  }, []);

  return null;
};

export default App;