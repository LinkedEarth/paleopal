/**
 * Custom Leaflet Theme System
 * Professional map styling that matches PaleoPal's theme system
 */

// Helper function to detect dark mode
const isDarkMode = () => document.documentElement.classList.contains('dark');

// Tile layer configurations for different themes
export const TILE_LAYERS = {
  light: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
      className: 'map-tiles-light'
    }
  },
  dark: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
      className: 'map-tiles-dark'
    }
  }
};

// Professional popup styling that matches theme system
export const getPopupOptions = () => {
  const dark = isDarkMode();
  
  return {
    className: dark ? 'custom-popup-dark' : 'custom-popup-light',
    closeButton: true,
    autoPan: true,
    maxWidth: 300,
    minWidth: 200,
    offset: [0, -10]
  };
};

// Default cluster options (using standard Leaflet styling)
export const getClusterOptions = () => {
  return {
    chunkedLoading: true,
    maxClusterRadius: 50
    // Using default iconCreateFunction for standard Leaflet cluster styling
  };
};

// Professional control styling
export const getControlOptions = () => {
  const dark = isDarkMode();
  
  return {
    position: 'topleft',
    className: dark ? 'leaflet-control-dark' : 'leaflet-control-light'
  };
};

// Get current tile layer based on theme
export const getCurrentTileLayer = () => {
  const dark = isDarkMode();
  return dark ? TILE_LAYERS.dark : TILE_LAYERS.light;
};

// Archive type color adjustments for theme
export const getThemedArchiveColors = () => {
  const dark = isDarkMode();
  
  // Base colors work well in both themes, but adjust opacity/brightness for dark mode
  const adjustColor = (color) => {
    if (dark) {
      // Slightly brighten colors for dark mode
      return color.replace(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/, (match, r, g, b) => {
        const newR = Math.min(255, parseInt(r) + 20);
        const newG = Math.min(255, parseInt(g) + 20);
        const newB = Math.min(255, parseInt(b) + 20);
        return `rgb(${newR}, ${newG}, ${newB})`;
      });
    }
    return color;
  };

  return {
    'coral': { color: adjustColor('#FF6B6B'), symbol: '🪸', name: 'Coral' },
    'ice': { color: adjustColor('#4ECDC4'), symbol: '🧊', name: 'Ice Core' },
    'lake': { color: adjustColor('#45B7D1'), symbol: '🏔️', name: 'Lake Sediment' },
    'marine': { color: adjustColor('#96CEB4'), symbol: '🌊', name: 'Marine Sediment' },
    'tree': { color: adjustColor('#FFEAA7'), symbol: '🌳', name: 'Tree Ring' },
    'speleothem': { color: adjustColor('#DDA0DD'), symbol: '🗻', name: 'Speleothem' },
    'borehole': { color: adjustColor('#F0A500'), symbol: '🕳️', name: 'Borehole' },
    'default': { color: adjustColor('#6C5CE7'), symbol: '📍', name: 'Other' }
  };
};

// Theme change listener for live updates
let themeChangeListeners = [];

export const addThemeChangeListener = (callback) => {
  themeChangeListeners.push(callback);
};

export const removeThemeChangeListener = (callback) => {
  themeChangeListeners = themeChangeListeners.filter(cb => cb !== callback);
};

// Watch for theme changes using MutationObserver
if (typeof window !== 'undefined') {
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
        const darkModeChanged = mutation.target.classList.contains('dark') !== 
                               (mutation.oldValue || '').includes('dark');
        if (darkModeChanged) {
          themeChangeListeners.forEach(callback => callback());
        }
      }
    });
  });

  observer.observe(document.documentElement, {
    attributes: true,
    attributeOldValue: true,
    attributeFilter: ['class']
  });
} 