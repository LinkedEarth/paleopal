import React, { useEffect, useMemo, useState } from 'react';
import MapGL, { Popup, Source, Layer } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import THEME from '../styles/colorTheme';
import MapLegend from './MapLegend';
import {
  detectLocationColumns,
  convertToMapPoints,
  getUniqueArchiveTypes,
  extractDatasetNameFromValue
} from '../utils/mapUtils';

// Mapbox access token — read from env
const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN;

const InteractiveMapMapbox = ({ data, height = '600px', onDatasetClick }) => {
  const locationCols = useMemo(() => detectLocationColumns(data), [data]);
  const [selectedPoint, setSelectedPoint] = useState(null);
  const isDark = typeof window !== 'undefined' && document.documentElement.classList.contains('dark');

  const points = useMemo(() => {
    if (!locationCols) return [];
    return convertToMapPoints(data, locationCols);
  }, [data, locationCols]);

  const archiveTypes = useMemo(() => {
    if (!locationCols?.archiveType) return [];
    return getUniqueArchiveTypes(data, locationCols.archiveType);
  }, [data, locationCols]);

  const geoJson = useMemo(() => ({
    type: 'FeatureCollection',
    features: points.map((p, idx) => ({
      type: 'Feature',
      properties: {
        id: p.id,
        index: idx,
        label: p.label,
        color: p.archiveConfig.color,
        symbol: p.archiveConfig.symbol,
      },
      geometry: {
        type: 'Point',
        coordinates: [p.lon, p.lat]
      }
    }))
  }), [points]);

  const onMapClick = (event) => {
    const feature = event.features && event.features[0];
    if (!feature) {
      setSelectedPoint(null);
      return;
    }

    // Cluster clicked -> zoom in
    if (feature.layer.id === 'clusters') {
      const clusterId = feature.properties.cluster_id;
      const mapboxSource = event.target.getSource('datasets');
      if (mapboxSource && mapboxSource.getClusterExpansionZoom) {
        mapboxSource.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err) return;
          event.target.easeTo({ center: feature.geometry.coordinates, zoom });
        });
      }
    }
    // Unclustered point clicked
    if (feature.layer.id === 'unclustered') {
      const idx = feature.properties.index;
      if (points[idx]) {
        setSelectedPoint(points[idx]);
      }
    }
  };

  // cluster color depending on theme
  const clusterColor = isDark ? '#60a5fa' : '#3b82f6';

  // Layers definition
  const clusterLayer = {
    id: 'clusters',
    type: 'circle',
    source: 'datasets',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': clusterColor,
      'circle-radius': [
        'step',
        ['get', 'point_count'],
        15,
        10,
        20,
        25,
        30
      ],
      'circle-opacity': 0.75
    }
  };

  const clusterCountLayer = {
    id: 'cluster-count',
    type: 'symbol',
    source: 'datasets',
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-size': 12
    },
    paint: {
      'text-color': '#ffffff'
    }
  };

  // circle background for individual symbols
  const unclusteredCircleLayer = {
    id: 'unclustered-circle',
    type: 'circle',
    source: 'datasets',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': 12,
      'circle-opacity': 0.9,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1
    }
  };

  const unclusteredLayer = {
    id: 'unclustered',
    type: 'symbol',
    source: 'datasets',
    filter: ['!', ['has', 'point_count']],
    layout: {
      'text-field': ['get', 'symbol'],
      'text-size': 20,
      'text-allow-overlap': true,
      'text-ignore-placement': true
    },
    paint: {
      'text-color': '#ffffff'
    }
  };

  if (!MAPBOX_TOKEN) {
    return (
      <div className={`p-3 rounded border ${THEME.borders.default} ${THEME.containers.card} text-sm`}>Mapbox token not set (REACT_APP_MAPBOX_TOKEN).</div>
    );
  }

  if (!locationCols || points.length === 0) return null;

  // use same basemap regardless of theme for consistency
  const mapStyle = 'mapbox://styles/mapbox/streets-v12';

  const initialView = {
    longitude: points[0].lon,
    latitude: points[0].lat,
    zoom: 2
  };

  return (
    <div className="relative" style={{ height }}>
      <MapGL
        mapboxAccessToken={MAPBOX_TOKEN}
        mapStyle={mapStyle}
        initialViewState={initialView}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
        onClick={onMapClick}
        interactiveLayerIds={['clusters', 'unclustered']}
      >
        <Source id="datasets" type="geojson" data={geoJson} cluster={true} clusterRadius={50} clusterMaxZoom={14} />
        <Layer {...clusterLayer} />
        <Layer {...clusterCountLayer} />
        <Layer {...unclusteredCircleLayer} />
        <Layer {...unclusteredLayer} />

        {selectedPoint && (
          <Popup
            longitude={selectedPoint.lon}
            latitude={selectedPoint.lat}
            onClose={() => setSelectedPoint(null)}
            maxWidth="240px"
            closeOnClick={false}
          >
            <div style={{ fontSize: 12, lineHeight: 1.4 }}>
              <h3 style={{ margin: '0 0 6px 0', fontWeight: 600, fontSize: 14 }}>
                {selectedPoint.label}
              </h3>
              <div>
                <div>
                  <strong>Latitude:</strong> {selectedPoint.lat}
                </div>
                <div>
                  <strong>Longitude:</strong> {selectedPoint.lon}
                </div>
                {selectedPoint.archiveType && (
                  <div>
                    <strong>Archive Type:</strong> {selectedPoint.archiveConfig.name}
                  </div>
                )}
              </div>
              {locationCols && Object.entries(selectedPoint.data)
                .filter(([k]) => ![locationCols.lat, locationCols.lon, locationCols.label, locationCols.archiveType].includes(k))
                .map(([key, value]) => {
                  if (!value) return null;
                  const isDatasetField = /(dataset|dsname|datasetname|dataset_id|datasetid)/i.test(key);
                  if (isDatasetField && onDatasetClick) {
                    const dsName = extractDatasetNameFromValue(value);
                    return (
                      <div key={key}>
                        <strong>{key}:</strong>{' '}
                        <span style={{ color: '#2563eb', cursor: 'pointer', textDecoration: 'underline' }}
                          onClick={() => onDatasetClick(value)}>
                          {value}
                        </span>
                      </div>
                    );
                  }
                  return (
                    <div key={key}>
                      <strong>{key}:</strong> {String(value)}
                    </div>
                  );
                })}
              {onDatasetClick && (
                <button
                  style={{
                    marginTop: 10,
                    background: '#2563eb',
                    color: 'white',
                    border: 'none',
                    padding: '6px 10px',
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontSize: 11,
                    width: '100%'
                  }}
                  onClick={() => onDatasetClick(selectedPoint.data[locationCols.label] || selectedPoint.label)}
                >
                  📊 Browse Dataset
                </button>
              )}
            </div>
          </Popup>
        )}
      </MapGL>

      {/* Legend */}
      {archiveTypes.length > 0 && (
        <MapLegend archiveTypes={archiveTypes} />
      )}
    </div>
  );
};

export default InteractiveMapMapbox; 