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
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  
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

  // Close mobile nav when screen becomes large
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) { // lg breakpoint
        setIsMobileNavOpen(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
      <style>
        {`
          /* Hide unwanted close buttons from NavigationPanel */
          .lipd-nav-wrapper button[aria-label*="close" i],
          .lipd-nav-wrapper button[title*="close" i],
          .lipd-nav-wrapper .MuiIconButton-root[aria-label*="close" i],
          .lipd-nav-wrapper .close-button,
          .lipd-nav-wrapper [data-testid*="close"],
          .lipd-nav-wrapper button:has([data-icon="times"]),
          .lipd-nav-wrapper button:has([data-icon="x"]),
          .lipd-nav-wrapper button:has(svg[viewBox="0 0 24 24"]):has(line[x1="18"]):has(line[y1="6"]):has(line[x2="6"]):has(line[y2="18"]),
          .lipd-nav-wrapper .MuiBox-root.css-1a6ic4q {
            display: none !important;
          }
        `}
      </style>
      <div className={`flex flex-col h-full ${THEME.containers.background}`}>
        {/* Header with breadcrumbs, readonly indicator, and download button */}
        <div className={`flex justify-between items-center p-4 border-b ${THEME.borders.default} ${THEME.containers.header}`}>
          <div className="flex items-center gap-4">
            {/* Mobile menu button - only visible on smaller screens */}
            <button
              onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
              className={`lg:hidden flex items-center justify-center w-10 h-10 rounded-lg ${THEME.buttons.secondary} transition-all duration-200`}
              title="Toggle navigation"
            >
              <Icon name={isMobileNavOpen ? "close" : "menu"} className="w-5 h-5" />
            </button>
            
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
              <span className="hidden sm:inline">Download LiPD</span>
              <span className="sm:hidden">Download</span>
            </button>
          </div>
        </div>
        
        {/* Main content area with RouterProvider for navigation */}
        <div className="flex flex-1 overflow-hidden relative">
          <RouterProvider>
            {/* Mobile backdrop overlay */}
            {isMobileNavOpen && (
              <div 
                className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
                onClick={() => setIsMobileNavOpen(false)}
              />
            )}
            
            {/* Navigation panel */}
            <div className={`
              ${isMobileNavOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
              lg:relative fixed top-0 left-0 h-full z-50 lg:z-auto
              w-80 border-r ${THEME.borders.default} overflow-auto ${THEME.containers.secondary}
              transition-transform duration-300 ease-in-out
              lg:block
            `}>
              {/* Mobile close button */}
              <div className="lg:hidden flex justify-end p-3 border-b border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => setIsMobileNavOpen(false)}
                  className={`flex items-center justify-center w-8 h-8 rounded-lg ${THEME.buttons.secondary} transition-all duration-200`}
                  title="Close navigation"
                >
                  <Icon name="close" className="w-5 h-5" />
                </button>
              </div>
              
              <div className="lipd-nav-wrapper">
                <NavigationPanel dataset={dataset} />
              </div>
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