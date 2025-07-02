const { override } = require('customize-cra');
const path = require('path');

module.exports = override(
  (config) => {
    // Handle .mjs files
    config.module.rules.push({
      test: /\.mjs$/,
      include: /node_modules/,
      type: 'javascript/auto'
    });

    // Update resolve configuration
    config.resolve = {
      ...config.resolve,
      extensionAlias: {
        '.js': ['.js', '.ts', '.tsx'],
        '.mjs': ['.mjs', '.js']
      },
      // Disable fully specified imports for ES modules
      fullySpecified: false
    };

    // Add custom webpack rule to handle ES module imports
    config.module.rules.unshift({
      test: /\.m?js$/,
      resolve: {
        fullySpecified: false
      }
    });

    // Create dynamic alias resolution for all @mui imports
    const createMuiAlias = (packageName) => {
      const aliases = {};
      const muiComponents = [
        'Box', 'IconButton', 'Divider', 'Tooltip', 'Breadcrumbs', 'Typography', 
        'Dialog', 'DialogTitle', 'DialogContent', 'DialogActions', 'FormControl',
        'Select', 'InputLabel', 'Button', 'DialogContentText', 'LinearProgress',
        'TextField', 'Paper', 'Card', 'CardContent', 'List', 'ListItem', 
        'ListItemText', 'Chip', 'Alert', 'CircularProgress', 'Grid', 'Stack',
        'AppBar', 'Toolbar', 'MenuItem'
      ];
      
      muiComponents.forEach(component => {
        try {
          aliases[`${packageName}/${component}`] = require.resolve(`${packageName}/${component}`);
        } catch (e) {
          // Component doesn't exist, skip it
        }
      });
      
      return aliases;
    };

    // Create aliases for @mui/x-tree-view components
    const createTreeViewAlias = () => {
      const aliases = {};
      const treeComponents = ['SimpleTreeView', 'TreeItem', 'TreeView'];
      
      treeComponents.forEach(component => {
        try {
          aliases[`@mui/x-tree-view/${component}`] = require.resolve(`@mui/x-tree-view/${component}`);
        } catch (e) {
          // Component doesn't exist, skip it
        }
      });
      
      return aliases;
    };

    // Create aliases for @mui/x-data-grid components
    const createDataGridAlias = () => {
      const aliases = {};
      const gridComponents = ['DataGrid', 'GridToolbar'];
      
      gridComponents.forEach(component => {
        try {
          aliases[`@mui/x-data-grid/${component}`] = require.resolve(`@mui/x-data-grid/${component}`);
        } catch (e) {
          // Component doesn't exist, skip it
        }
      });
      
      return aliases;
    };

    // Apply all aliases
    config.resolve.alias = {
      ...config.resolve.alias,
      ...createMuiAlias('@mui/material'),
      ...createMuiAlias('@mui/icons-material'),
      ...createTreeViewAlias(),
      ...createDataGridAlias()
    };

    return config;
  }
); 