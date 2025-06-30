import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.markercluster';
import './InteractiveMap.css';
import THEME from '../styles/colorTheme';
import Icon from './Icon';
import MapLegend from './MapLegend';
import { 
  detectLocationColumns, 
  convertToMapPoints, 
  getUniqueArchiveTypes,
  createArchiveMarkerHTML,
  extractDatasetNameFromValue
} from '../utils/mapUtils';
import {
  getCurrentTileLayer,
  getPopupOptions,
  getClusterOptions,
  addThemeChangeListener,
  removeThemeChangeListener
} from '../styles/leafletTheme';

// Fix for default marker icons in webpack
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const InteractiveMap = ({ data, hideHeader = false, height = '400px', onDatasetClick }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerClusterGroupRef = useRef(null);
  const tileLayerRef = useRef(null);
  const [isDarkTheme, setIsDarkTheme] = useState(() => 
    typeof window !== 'undefined' && document.documentElement.classList.contains('dark')
  );

  // Function to update tile layer based on theme
  const updateTileLayer = () => {
    if (!mapInstanceRef.current) return;
    
    // Remove existing tile layer
    if (tileLayerRef.current) {
      mapInstanceRef.current.removeLayer(tileLayerRef.current);
    }
    
    // Add new tile layer based on current theme
    const tileConfig = getCurrentTileLayer();
    tileLayerRef.current = L.tileLayer(tileConfig.url, tileConfig.options);
    
    // Add error handling for tile loading
    tileLayerRef.current.on('tileerror', (e) => {
      console.warn('Tile loading error:', e);
    });
    
    tileLayerRef.current.on('tileload', () => {
      console.log('Tiles loaded successfully');
    });
    
    tileLayerRef.current.addTo(mapInstanceRef.current);
  };

  useEffect(() => {
    if (!mapRef.current || !data || data.length === 0) return;

    const locationCols = detectLocationColumns(data);
    if (!locationCols) return;

    const points = convertToMapPoints(data, locationCols);
    if (points.length === 0) return;

    // Initialize map if not already done
    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current, {
        zoomControl: true,
        scrollWheelZoom: true,
        doubleClickZoom: true,
        touchZoom: true,
      });

      // Add initial tile layer
      updateTileLayer();
    }

    // Clear existing marker cluster group
    if (markerClusterGroupRef.current) {
      mapInstanceRef.current.removeLayer(markerClusterGroupRef.current);
    }

    // Create new marker cluster group with theme-aware options
    markerClusterGroupRef.current = L.markerClusterGroup(getClusterOptions());

    // Add markers to cluster group
    points.forEach(point => {
      // Detect dataset columns in the point data
      const datasetColumns = Object.keys(point.data).filter(h => 
        /^(datasetname|dataset_name|datasetid|dataset_id|dsname|dataset)$/i.test(h) ||
        /^(.*uri.*|.*url.*|.*link.*|.*ref.*)$/i.test(h)
      );
      
      // Find dataset values for browse button
      let datasetValue = null;
      let datasetName = null;
      for (const col of datasetColumns) {
        const value = point.data[col];
        if (value) {
          datasetValue = value;
          datasetName = extractDatasetNameFromValue(value);
          break;
        }
      }
      
      // Create popup content with all data fields
      const dataFields = Object.entries(point.data)
        .filter(([key, value]) => 
          key !== locationCols.lat && 
          key !== locationCols.lon && 
          key !== locationCols.label &&
          key !== locationCols.archiveType &&
          value !== null &&
          value !== undefined &&
          value !== ''
        )
        .map(([key, value]) => {
          // Check if this field contains a dataset reference
          const isDatasetField = datasetColumns.includes(key);
          if (isDatasetField && onDatasetClick) {
            const dsName = extractDatasetNameFromValue(value);
            if (dsName) {
              return `<div><strong>${key}:</strong> <span class="dataset-text" style="color: #2563eb;">${value}</span></div>`;
            }
          }
          return `<div><strong>${key}:</strong> ${value}</div>`;
        })
        .join('');

      // Add Browse Data button if dataset is available
      const browseButton = datasetName && onDatasetClick ? `
        <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
          <button class="browse-dataset-btn" data-dataset="${datasetValue}" style="
            background: #2563eb; 
            color: white; 
            border: none; 
            padding: 6px 12px; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 11px; 
            font-weight: 500;
            width: 100%;
            transition: background-color 0.2s;
          " onmouseover="this.style.backgroundColor='#1d4ed8'" onmouseout="this.style.backgroundColor='#2563eb'">
            📊 Browse Dataset
          </button>
        </div>
      ` : '';

      const popupContent = `
        <div style="min-width: 200px;">
          <h3 style="margin: 0 0 8px 0; font-weight: 600; font-size: 14px;">${point.label}</h3>
          <div style="font-size: 12px; line-height: 1.4;">
            <div><strong>Latitude:</strong> ${point.lat}</div>
            <div><strong>Longitude:</strong> ${point.lon}</div>
            ${point.archiveType ? `<div><strong>Archive Type:</strong> ${point.archiveConfig.name}</div>` : ''}
            ${dataFields}
          </div>
          ${browseButton}
        </div>
      `;

      // Create custom marker icon for archive types
      let marker;
      if (point.archiveType) {
        const customIcon = L.divIcon({
          html: createArchiveMarkerHTML(point.archiveConfig, 30),
          className: 'custom-archive-marker',
          iconSize: [30, 30],
          iconAnchor: [15, 15],
          popupAnchor: [0, -15]
        });
        
        marker = L.marker([point.lat, point.lon], { icon: customIcon });
      } else {
        // Use default marker for points without archive type
        marker = L.marker([point.lat, point.lon]);
      }
      
      // Bind popup with event delegation for dataset browse button
      const popup = L.popup(getPopupOptions()).setContent(popupContent);
      marker.bindPopup(popup);
      
      // Add event listener for browse dataset button after popup opens
      marker.on('popupopen', (e) => {
        const popupElement = e.popup.getElement();
        if (popupElement && onDatasetClick) {
          const browseBtn = popupElement.querySelector('.browse-dataset-btn');
          if (browseBtn) {
            browseBtn.addEventListener('click', (event) => {
              event.preventDefault();
              event.stopPropagation();
              const datasetValue = browseBtn.getAttribute('data-dataset');
              if (datasetValue) {
                onDatasetClick(datasetValue);
              }
            });
          }
        }
      });
      
      markerClusterGroupRef.current.addLayer(marker);
    });

    // Add cluster group to map
    mapInstanceRef.current.addLayer(markerClusterGroupRef.current);

    // Fit map to show all markers
    if (points.length === 1) {
      mapInstanceRef.current.setView([points[0].lat, points[0].lon], 10);
    } else if (points.length > 1) {
      mapInstanceRef.current.fitBounds(markerClusterGroupRef.current.getBounds().pad(0.1));
    }

    // Cleanup function
    return () => {
      if (mapInstanceRef.current && markerClusterGroupRef.current) {
        mapInstanceRef.current.removeLayer(markerClusterGroupRef.current);
      }
    };
  }, [data]);

  // Listen for theme changes and update map styling
  useEffect(() => {
    const handleThemeChange = () => {
      // Update theme state
      setIsDarkTheme(document.documentElement.classList.contains('dark'));
      
      updateTileLayer();
      
      // Update cluster group with new theme
      if (mapInstanceRef.current && markerClusterGroupRef.current) {
        const currentMarkers = [];
        markerClusterGroupRef.current.eachLayer(layer => {
          currentMarkers.push(layer);
        });
        
        // Remove old cluster group
        mapInstanceRef.current.removeLayer(markerClusterGroupRef.current);
        
        // Create new cluster group with updated theme
        markerClusterGroupRef.current = L.markerClusterGroup(getClusterOptions());
        
        // Re-add all markers with updated popup options
        currentMarkers.forEach(marker => {
          // Update popup options if it exists
          if (marker.getPopup()) {
            const content = marker.getPopup().getContent();
            marker.bindPopup(content, getPopupOptions());
          }
          markerClusterGroupRef.current.addLayer(marker);
        });
        
        // Add updated cluster group back to map
        mapInstanceRef.current.addLayer(markerClusterGroupRef.current);
      }
    };

    addThemeChangeListener(handleThemeChange);

    return () => {
      removeThemeChangeListener(handleThemeChange);
    };
  }, []);

  // Cleanup map on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  const locationCols = detectLocationColumns(data);
  if (!locationCols) {
    return null; // Don't render if no location data
  }

  const points = convertToMapPoints(data, locationCols);
  if (points.length === 0) {
    return null; // Don't render if no valid points
  }

  // Get unique archive types for legend
  const archiveTypes = locationCols?.archiveType ? getUniqueArchiveTypes(data, locationCols.archiveType) : [];

  // Determine theme class for map container
  const mapThemeClass = isDarkTheme ? 'map-container-dark' : 'map-container-light';

  const mapContent = (
    <div className="space-y-2">
      <div className="relative">
        <div 
          ref={mapRef} 
          style={{ height, width: '100%' }}
          className={`rounded border ${THEME.borders.default} overflow-hidden ${mapThemeClass}`}
        />
        {archiveTypes.length > 0 && (
          <MapLegend archiveTypes={archiveTypes} />
        )}
      </div>
      <p className={`text-xs ${THEME.text.muted}`}>
        Showing {points.length} location{points.length !== 1 ? 's' : ''} on map
        {archiveTypes.length > 0 && (
          <span className="ml-2">
            • {archiveTypes.length} archive type{archiveTypes.length !== 1 ? 's' : ''}
          </span>
        )}
      </p>
    </div>
  );

  if (hideHeader) {
    return mapContent;
  }

  return (
    <div className={`border ${THEME.borders.default} rounded-lg ${THEME.containers.panel}`}>
      <div className={`flex justify-between items-center p-3 border-b ${THEME.borders.default} rounded-t-lg ${THEME.containers.header}`}>
        <h4 className={`font-medium text-sm m-0 flex items-center gap-2 ${THEME.text.primary}`}>
          <Icon name="map" className="w-4 h-4" />
          Location Map ({points.length} point{points.length !== 1 ? 's' : ''})
          {archiveTypes.length > 0 && (
            <span className={`text-xs ${THEME.text.secondary} ml-2`}>
              • {archiveTypes.length} archive type{archiveTypes.length !== 1 ? 's' : ''}
            </span>
          )}
        </h4>
      </div>
      <div className="p-3">
        {mapContent}
      </div>
    </div>
  );
};

export default InteractiveMap; 