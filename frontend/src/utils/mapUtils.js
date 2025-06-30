/**
 * Utility functions for detecting and handling geographic data in SPARQL results
 */

/**
 * Detect if the data contains latitude/longitude columns
 * @param {Array} data - Array of data objects
 * @returns {Object|null} - Object with column names or null if no geographic data
 */
export const detectLocationColumns = (data) => {
  if (!data || data.length === 0) return null;
  
  const headers = Object.keys(data[0]);
  const latCols = headers.filter(h => 
    /^(lat|latitude|geo_meanlat|meanlat)$/i.test(h)
  );
  const lonCols = headers.filter(h => 
    /^(lon|long|lng|longitude|geo_meanlon|meanlon)$/i.test(h)
  );
  
  // Return the first matching pair
  if (latCols.length > 0 && lonCols.length > 0) {
    return {
      lat: latCols[0],
      lon: lonCols[0],
      label: headers.find(h => 
        /^(name|title|datasetname|dataset|dsname|label)$/i.test(h)
      ) || headers[0],
      archiveType: headers.find(h => 
        /^(archivetype|archive_type|archive|type|archivetypelabel|archive_type_label)$/i.test(h)
      ) || null
    };
  }
  
  return null;
};

/**
 * Check if data has geographic coordinates
 * @param {Array} data - Array of data objects
 * @returns {boolean} - True if geographic data is present
 */
export const hasGeographicData = (data) => {
  return detectLocationColumns(data) !== null;
};

/**
 * Convert data to map points with validation
 * @param {Array} data - Array of data objects
 * @param {Object} locationCols - Column mapping object
 * @returns {Array} - Array of valid map points
 */
export const convertToMapPoints = (data, locationCols) => {
  if (!locationCols || !data) return [];
  
  return data
    .map((row, index) => {
      const lat = parseFloat(row[locationCols.lat]);
      const lon = parseFloat(row[locationCols.lon]);
      
      if (isNaN(lat) || isNaN(lon)) return null;
      
      // Basic validation for realistic coordinates
      if (lat < -90 || lat > 90 || lon < -180 || lon > 360) return null;
      
      const archiveType = locationCols.archiveType ? row[locationCols.archiveType] : null;
      const archiveConfig = getArchiveTypeConfig(archiveType);
      
      return {
        id: index,
        lat,
        lon,
        label: row[locationCols.label] || `Point ${index + 1}`,
        archiveType,
        archiveConfig,
        data: row
      };
    })
    .filter(point => point !== null);
};

/**
 * Archive type configurations with colors and symbols
 */
export const ARCHIVE_TYPES = {
  'borehole': { color: '#8B4513', symbol: '●', name: 'Borehole' },
  'coral': { color: '#FF6B6B', symbol: '❋', name: 'Coral' },
  'fluvial': { color: '#4682B4', symbol: '〰', name: 'Fluvial sediment' },
  'glacier': { color: '#B0E0E6', symbol: '❅', name: 'Glacier ice' },
  'ground': { color: '#87CEEB', symbol: '❆', name: 'Ground ice' },
  'lake': { color: '#1E90FF', symbol: '≋', name: 'Lake sediment' },
  'marine': { color: '#20B2AA', symbol: '≈', name: 'Marine sediment' },
  'midden': { color: '#D2691E', symbol: '⬢', name: 'Midden' },
  'mollusk': { color: '#FFB6C1', symbol: '◉', name: 'Mollusk shell' },
  'peat': { color: '#8B4513', symbol: '▦', name: 'Peat' },
  'sclerosponge': { color: '#FF69B4', symbol: '⬟', name: 'Sclerosponge' },
  'shoreline': { color: '#F4A460', symbol: '⌒', name: 'Shoreline' },
  'speleothem': { color: '#9370DB', symbol: '▲', name: 'Speleothem' },
  'terrestrial': { color: '#A0522D', symbol: '■', name: 'Terrestrial sediment' },
  'wood': { color: '#228B22', symbol: '※', name: 'Wood' },
  'documents': { color: '#708090', symbol: '⎗', name: 'Documents' },
  'other': { color: '#696969', symbol: '◆', name: 'Other' }
};

/**
 * Get archive type configuration for a given type
 * @param {string} archiveType - Archive type string
 * @returns {Object} - Archive type configuration
 */
export const getArchiveTypeConfig = (archiveType) => {
  if (!archiveType) return ARCHIVE_TYPES.other;
  
  const type = archiveType.toLowerCase().trim();
  
  // Check for exact matches first
  if (ARCHIVE_TYPES[type]) return ARCHIVE_TYPES[type];
  
  // Check for partial matches
  if (type.includes('borehole') || type.includes('bore')) return ARCHIVE_TYPES.borehole;
  if (type.includes('coral')) return ARCHIVE_TYPES.coral;
  if (type.includes('fluvial') || type.includes('river')) return ARCHIVE_TYPES.fluvial;
  if (type.includes('glacier')) return ARCHIVE_TYPES.glacier;
  if (type.includes('ground') && type.includes('ice')) return ARCHIVE_TYPES.ground;
  if (type.includes('lake') || type.includes('lacustrine')) return ARCHIVE_TYPES.lake;
  if (type.includes('marine') || type.includes('ocean')) return ARCHIVE_TYPES.marine;
  if (type.includes('midden')) return ARCHIVE_TYPES.midden;
  if (type.includes('mollusk') || type.includes('shell')) return ARCHIVE_TYPES.mollusk;
  if (type.includes('peat')) return ARCHIVE_TYPES.peat;
  if (type.includes('sclerosponge')) return ARCHIVE_TYPES.sclerosponge;
  if (type.includes('shoreline') || type.includes('shore')) return ARCHIVE_TYPES.shoreline;
  if (type.includes('speleothem') || type.includes('cave')) return ARCHIVE_TYPES.speleothem;
  if (type.includes('terrestrial')) return ARCHIVE_TYPES.terrestrial;
  if (type.includes('wood') || type.includes('tree')) return ARCHIVE_TYPES.wood;
  if (type.includes('document')) return ARCHIVE_TYPES.documents;
  if (type.includes('ice') && !type.includes('ground') && !type.includes('glacier')) return ARCHIVE_TYPES.glacier; // fallback for general ice
  
  return ARCHIVE_TYPES.other;
};

/**
 * Get unique archive types from data
 * @param {Array} data - Array of data objects
 * @param {string} archiveTypeColumn - Archive type column name
 * @returns {Array} - Array of unique archive types with configurations
 */
export const getUniqueArchiveTypes = (data, archiveTypeColumn) => {
  if (!data || !archiveTypeColumn) return [];
  
  const uniqueTypes = [...new Set(data.map(row => row[archiveTypeColumn]).filter(Boolean))];
  
  return uniqueTypes.map(type => ({
    type,
    config: getArchiveTypeConfig(type),
    count: data.filter(row => row[archiveTypeColumn] === type).length
  }));
};

/**
 * Create custom marker HTML for archive types
 * @param {Object} archiveConfig - Archive type configuration
 * @param {number} size - Marker size
 * @returns {string} - HTML string for custom marker
 */
export const createArchiveMarkerHTML = (archiveConfig, size = 30) => {
  return `
    <div style="
      width: ${size}px;
      height: ${size}px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: ${Math.max(16, size * 0.8)}px;
      color: ${archiveConfig.color};
      font-weight: 900;
      font-family: 'Arial', 'Helvetica', sans-serif;
      line-height: 1;
    ">
      ${archiveConfig.symbol}
    </div>
  `;
};

/**
 * Get sample geographic data for testing
 * @returns {Array} - Sample SPARQL results with geographic data
 */
export const getSampleGeographicData = () => {
  return [
    {
      dataSetName: "Greenland Ice Core",
      lat: "72.5",
      lon: "-38.5",
      elev: "3200",
      archiveType: "ice"
    },
    {
      dataSetName: "Antarctic Ice Sheet",
      lat: "-89.0",
      lon: "0.0",
      elev: "2800",
      archiveType: "ice"
    },
    {
      dataSetName: "Alpine Lake Sediment",
      lat: "46.8",
      lon: "8.6",
      elev: "1650",
      archiveType: "lake"
    },
    {
      dataSetName: "Great Barrier Reef",
      lat: "-18.2",
      lon: "147.7",
      elev: "-10",
      archiveType: "coral"
    },
    {
      dataSetName: "California Tree Ring",
      lat: "37.4",
      lon: "-119.6",
      elev: "2100",
      archiveType: "tree"
    }
  ];
};

// Function to extract dataset name from URI or value
export const extractDatasetNameFromValue = (value) => {
  if (!value || typeof value !== 'string') return null;
  
  // If it's a URI (contains protocol or starts with http/https)
  if (value.includes('://') || value.startsWith('http')) {
    // Extract the local name (part after the last / or #)
    const lastSlash = value.lastIndexOf('/');
    const lastHash = value.lastIndexOf('#');
    const lastSeparator = Math.max(lastSlash, lastHash);
    
    if (lastSeparator >= 0 && lastSeparator < value.length - 1) {
      return value.substring(lastSeparator + 1);
    }
  }
  
  // If it's just a plain dataset name, return as-is
  return value;
};

// Function to detect dataset-related columns
export const detectDatasetColumns = (data) => {
  if (!data || data.length === 0) return [];
  
  const headers = Object.keys(data[0]);
  return headers.filter(h => 
    /^(datasetname|dataset_name|datasetid|dataset_id|dsname|dataset)$/i.test(h) ||
    // Also detect URI patterns that might contain dataset references
    /^(.*uri.*|.*url.*|.*link.*|.*ref.*)$/i.test(h)
  );
}; 