import React, { useEffect, useState } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box, Alert, CircularProgress, Typography, Button } from '@mui/material';
import {
  useLiPDStore,
  NavigationPanel,
  EditorPanel,
  RouterProvider,
  AppBarBreadcrumbs
} from '@linkedearth/lipd-ui';
import THEME from '../styles/colorTheme';
import Icon from './Icon';

// Simple MUI theme that works with the existing dark mode system
const createMinimalTheme = (isDarkMode = false) => createTheme({
  palette: {
    mode: isDarkMode ? 'dark' : 'light',
  },
});

const LipdDatasetViewer = ({ lipdInstance, datasetName }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const { 
    dataset, 
    setDataset, 
    setThemeMode, 
    setReadonly 
  } = useLiPDStore(state => ({
    dataset: state.dataset,
    setDataset: state.setDataset,
    setThemeMode: state.setThemeMode,
    setReadonly: state.setReadonly
  }));

  // Use existing dark mode detection pattern
  const isDarkMode = document.documentElement.classList.contains('dark');
  const muiTheme = createMinimalTheme(isDarkMode);

  // Set theme mode in the store
  useEffect(() => {
    setThemeMode(isDarkMode ? 'dark' : 'light');
  }, [isDarkMode, setThemeMode]);

  // Set readonly mode in the store
  useEffect(() => {
    setReadonly(true); // Always readonly in this viewer
  }, [setReadonly]);

  useEffect(() => {
    const loadDataset = async () => {
      if (!lipdInstance || !datasetName) return;
      
      try {
        setLoading(true);
        setError(null);
        
        console.log('LiPD Instance:', lipdInstance);
        
        // Get the datasets from the already loaded LiPD instance
        const datasets = await lipdInstance.getDatasets();
        console.log('Loaded datasets:', datasets);
        
        if (datasets && datasets.length > 0) {
          const firstDataset = datasets[0];
          console.log('Using first dataset:', firstDataset);
          setDataset(firstDataset);
        } else {
          setError('No datasets found in LiPD instance');
        }
      } catch (err) {
        console.error('Error accessing LiPD dataset:', err);
        setError(`Failed to access dataset: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadDataset();
  }, [lipdInstance, datasetName, setDataset]);

  // Download LiPD file function
  const handleDownloadLiPD = async () => {
    if (!dataset || !lipdInstance) return;
    
    try {
      // Use the existing LiPD instance to create the file
      const dsName = dataset.getName?.() || 'dataset';
      const blob = await lipdInstance.createLipdBrowser(dsName);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${dsName}.lpd`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export LiPD file', err);
      setError(`Failed to download LiPD file: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className={`flex flex-col items-center justify-center p-8 ${THEME.containers.panel} rounded-lg`}>
        <CircularProgress size={40} />
        <div className={`mt-4 text-sm ${THEME.text.secondary}`}>
          Loading dataset...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`m-4 p-4 rounded-lg ${THEME.status.error.background} ${THEME.status.error.border} border`}>
        <div className={`font-semibold ${THEME.status.error.text} mb-2`}>Error</div>
        <div className={`text-sm ${THEME.status.error.text}`}>
          {error}
        </div>
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className={`m-4 p-8 rounded-lg ${THEME.containers.secondary} border ${THEME.borders.default}`}>
        <div className={`text-sm ${THEME.text.secondary}`}>
          No dataset available
        </div>
      </div>
    );
  }

  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      <div className={`flex flex-col h-full ${THEME.containers.background}`}>
        {/* Header with breadcrumbs, readonly indicator, and download button */}
        <div className={`flex justify-between items-center p-4 border-b ${THEME.borders.default} ${THEME.containers.header}`}>
          <div className="flex items-center gap-4">
            <RouterProvider>
              <AppBarBreadcrumbs />
            </RouterProvider>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Read-only indicator */}
            <span className={`px-3 py-1 text-xs font-medium rounded-full ${THEME.status.info.background} ${THEME.status.info.text} border ${THEME.status.info.border}`}>
              Read-only
            </span>
            
            {/* Download button */}
            <button
              onClick={handleDownloadLiPD}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg ${THEME.buttons.primary} transition-all duration-200`}
              title="Download LiPD file"
            >
              <Icon name="download" className="w-4 h-4" />
              Download LiPD
            </button>
          </div>
        </div>
        
        {/* Main content area with RouterProvider for navigation */}
        <div className="flex flex-1 overflow-hidden">
          <RouterProvider>
            {/* Navigation panel */}
            <div className={`w-80 border-r ${THEME.borders.default} overflow-auto ${THEME.containers.secondary}`}>
              <NavigationPanel dataset={dataset} />
            </div>
            
            {/* Editor panel (readonly) */}
            <div className={`flex-1 overflow-auto ${THEME.containers.main}`}>
              <EditorPanel />
            </div>
          </RouterProvider>
        </div>
      </div>
    </ThemeProvider>
  );
};

export default LipdDatasetViewer; 