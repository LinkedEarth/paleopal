import React, { useState, useEffect } from 'react';
import { LiPD } from 'lipdjs';
import THEME from '../styles/colorTheme';
import Icon from './Icon';



const InfoCard = ({ title, children, icon = null }) => (
  <div className={`border rounded-lg ${THEME.containers.card}`}>
    <div className={`px-3 py-2 border-b ${THEME.borders.default} ${THEME.containers.secondary}`}>
      <div className="flex items-center gap-2">
        {icon && <Icon name={icon} className="w-4 h-4" />}
        <span className={`font-medium text-sm ${THEME.text.primary}`}>{title}</span>
      </div>
    </div>
    <div className="p-3">{children}</div>
  </div>
);

const Collapsible = ({ title, children, defaultOpen = false, count = null, icon = null }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`border rounded-lg overflow-hidden ${THEME.borders.default}`}>
      <button
        className={`w-full flex items-center justify-between px-3 py-2 ${THEME.containers.secondary} ${THEME.interactive.hover}`}
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          {icon && <Icon name={icon} className="w-4 h-4" />}
          <span className={`${THEME.text.primary} font-medium text-sm`}>
            {title}
            {count !== null && <span className={`ml-1 text-xs ${THEME.text.muted}`}>({count})</span>}
          </span>
        </div>
        <Icon
          name="chevronDown"
          className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''} ${THEME.text.secondary}`}
        />
      </button>
      {open && <div className="p-3 space-y-3">{children}</div>}
    </div>
  );
};

const MetadataField = ({ label, value, isArray = false }) => {
  if (!value || (isArray && (!Array.isArray(value) || value.length === 0))) return null;
  
  const displayValue = isArray ? value.join(', ') : value;
  
  return (
    <div className="text-xs">
      <span className="font-medium">{label}:</span>{' '}
      <span className={THEME.text.secondary}>{displayValue}</span>
    </div>
  );
};

const PublicationList = ({ publications }) => {
  if (!Array.isArray(publications) || publications.length === 0) return null;
  
  return (
    <div className="space-y-3">
      {publications.map((pub, idx) => {
        const authors = pub.getAuthors() || [];
        const authorNames = authors.map(author => {
          // Check if author has getName method (Person class)
          if (typeof author.getName === 'function') {
            return author.getName();
          }
          return typeof author === 'string' ? author : 'Unknown Author';
        }).filter(Boolean);
        
        return (
          <div key={idx} className={`p-3 rounded border ${THEME.borders.default} ${THEME.containers.secondary} text-xs`}>
            {pub.getTitle() && <div className="font-medium mb-1">{pub.getTitle()}</div>}
            {authorNames.length > 0 && <div><span className="font-medium">Authors:</span> {authorNames.join(', ')}</div>}
            {pub.getJournal() && <div><span className="font-medium">Journal:</span> {pub.getJournal()}</div>}
            {pub.getYear() && <div><span className="font-medium">Year:</span> {pub.getYear()}</div>}
            {pub.getVolume() && <div><span className="font-medium">Volume:</span> {pub.getVolume()}</div>}
            {pub.getPages() && <div><span className="font-medium">Pages:</span> {pub.getPages()}</div>}
            {pub.getDOI() && (
              <div>
                <span className="font-medium">DOI:</span>{' '}
                <a href={`https://doi.org/${pub.getDOI()}`} className="text-blue-600 dark:text-blue-400 underline" target="_blank" rel="noopener noreferrer">
                  {pub.getDOI()}
                </a>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const VariableList = ({ variables }) => {
  if (!Array.isArray(variables) || variables.length === 0) return null;
  
  return (
    <div className="space-y-2">
      {variables.map((variableInfo, idx) => {
        const variable = variableInfo.variable; // Extract the actual variable object
        return (
          <div key={idx} className={`p-2 rounded border ${THEME.borders.default} ${THEME.containers.secondary}`}>
            <div className="text-xs space-y-1">
              <div className="font-medium">{variable.getName() || `Variable ${idx + 1}`}</div>
              <MetadataField label="Type" value={variable.getVariableType()} />
              <MetadataField label="Units" value={variable.getUnits()?.label} />
              <MetadataField label="Description" value={variable.getDescription()} />
              <MetadataField label="Proxy" value={variable.getProxy()?.label} />
              <MetadataField label="Archive Type" value={variable.getArchiveType()?.label} />
              {variableInfo.tableName && <MetadataField label="Table" value={variableInfo.tableName} />}
              {variableInfo.paleoDataName && <MetadataField label="PaleoData" value={variableInfo.paleoDataName} />}
              {variableInfo.chronDataName && <MetadataField label="ChronData" value={variableInfo.chronDataName} />}
              {variable.getValues() && (
                <div><span className="font-medium">Has Values:</span> Yes</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const TablePreview = ({ table, title = "Data" }) => {
  if (!table) return <p className={`${THEME.text.secondary} text-xs`}>No data available</p>;
  
  console.log(`Table Preview for ${title}:`, table);
  
  let data = [];
  let headers = [];
  let variables = [];
  
  // Check if this is a DataTable instance with getDataFrame method
  if (typeof table.getDataFrame === 'function') {
    try {
      const dataFrame = table.getDataFrame();
      console.log(`DataFrame for ${title}:`, dataFrame);
      
      // Get variables for metadata display
      variables = table.getVariables() || [];
      
      // Extract headers from data keys
      headers = Object.keys(dataFrame.data);
      
      // Convert columnar data to row-based data for table display
      const maxLength = Math.max(...headers.map(h => (dataFrame.data[h] || []).length));
      data = Array.from({ length: Math.min(maxLength, 20) }, (_, i) => {
        const row = {};
        headers.forEach(h => {
          row[h] = dataFrame.data[h]?.[i] || '';
        });
        return row;
      });
    } catch (err) {
      console.error('Error getting DataFrame:', err);
      // Fallback to getting variables directly
      variables = table.getVariables ? table.getVariables() : [];
      if (variables.length > 0) {
        headers = variables.map(v => v.getName()).filter(Boolean);
      }
    }
  }
  // Handle array of objects
  else if (Array.isArray(table) && table.length > 0) {
    data = table.slice(0, 20);
    headers = Object.keys(table[0]);
  }
  // Handle object with columns
  else if (table.columns && Array.isArray(table.columns)) {
    variables = table.columns;
    headers = table.columns.map(col => col.variableName || col.name || 'Unknown');
    const maxLength = Math.max(...table.columns.map(col => (col.values || []).length));
    data = Array.from({ length: Math.min(maxLength, 20) }, (_, i) => {
      const row = {};
      table.columns.forEach((col, colIdx) => {
        const colName = col.variableName || col.name || `Column ${colIdx + 1}`;
        row[colName] = col.values?.[i] || '';
      });
      return row;
    });
  }
  // Handle object with direct data arrays
  else if (typeof table === 'object' && Object.keys(table).length > 0) {
    const keys = Object.keys(table);
    const possibleDataKeys = keys.filter(k => 
      Array.isArray(table[k]) && table[k].length > 0 && 
      typeof table[k][0] !== 'object'
    );
    
    if (possibleDataKeys.length > 0) {
      headers = possibleDataKeys;
      const maxLength = Math.max(...possibleDataKeys.map(k => table[k].length));
      data = Array.from({ length: Math.min(maxLength, 20) }, (_, i) => {
        const row = {};
        possibleDataKeys.forEach(k => {
          row[k] = table[k][i] || '';
        });
        return row;
      });
    } else {
      headers = keys;
      data = [table];
    }
  }
  
  console.log(`Processed data for ${title}:`, { headers, data: data.slice(0, 3), variables: variables.length });
  
  if (data.length === 0 && headers.length === 0) {
    return <p className={`${THEME.text.secondary} text-xs`}>No data available or failed to parse table</p>;
  }
  
  return (
    <div className="space-y-2">
      {/* Show column info if available */}
      {variables.length > 0 && (
        <div className="mb-3">
          <h5 className={`text-sm font-medium ${THEME.text.primary} mb-2`}>Variables ({variables.length})</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {variables.slice(0, 10).map((variable, idx) => (
              <div key={idx} className={`p-2 rounded border ${THEME.borders.default} ${THEME.containers.secondary} text-xs`}>
                <div className="font-medium">{variable.getName() || `Variable ${idx + 1}`}</div>
                {variable.getUnits()?.label && <div><span className="font-medium">Units:</span> {variable.getUnits().label}</div>}
                {variable.getDescription() && <div><span className="font-medium">Description:</span> {variable.getDescription()}</div>}
                {variable.getVariableType() && <div><span className="font-medium">Type:</span> {variable.getVariableType()}</div>}
              </div>
            ))}
            {variables.length > 10 && (
              <div className={`p-2 rounded border ${THEME.borders.default} ${THEME.containers.secondary} text-xs text-center ${THEME.text.muted}`}>
                ... and {variables.length - 10} more variables
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Data table */}
      {data.length > 0 && headers.length > 0 && (
        <div className={`overflow-x-auto border rounded ${THEME.borders.default}`}>
          <table className="w-full text-xs border-collapse">
            <thead className={THEME.containers.secondary}>
              <tr>
                {headers.slice(0, 10).map((h) => (
                  <th key={h} className={`px-2 py-1 text-left border-b ${THEME.borders.default} font-medium`}>
                    {h}
                  </th>
                ))}
                {headers.length > 10 && (
                  <th className={`px-2 py-1 text-left border-b ${THEME.borders.default} font-medium ${THEME.text.muted}`}>
                    +{headers.length - 10} more
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={i} className={THEME.interactive.hover}>
                  {headers.slice(0, 10).map((h) => {
                    const val = row[h];
                    let display = val;
                    if (val === null || val === undefined) {
                      display = '';
                    } else if (typeof val === 'object') {
                      display = Array.isArray(val)
                        ? `[Array(${val.length})]`
                        : '{…}';
                    } else if (typeof val === 'string' && val.length > 50) {
                      display = val.substring(0, 47) + '...';
                    } else if (typeof val === 'number') {
                      display = Number.isInteger(val) ? val : parseFloat(val.toFixed(6));
                    }
                    return (
                      <td key={h} className={`px-2 py-1 border-b ${THEME.borders.table}`}>
                        {display}
                      </td>
                    );
                  })}
                  {headers.length > 10 && (
                    <td className={`px-2 py-1 border-b ${THEME.borders.table} ${THEME.text.muted}`}>
                      ...
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {data.length >= 20 && (
        <p className={`text-xs ${THEME.text.muted}`}>Showing first 20 of many rows</p>
      )}
      {data.length > 0 && data.length < 20 && (
        <p className={`text-xs ${THEME.text.muted}`}>Showing all {data.length} rows</p>
      )}
    </div>
  );
};

const LipdDatasetViewer = ({ lipdInstance, datasetName }) => {
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
  }, [lipdInstance, datasetName]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className={`${THEME.text.secondary}`}>Loading dataset...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 rounded-lg ${THEME.status.error.background} ${THEME.status.error.border} border`}>
        <div className={`${THEME.status.error.text} font-medium`}>Error</div>
        <div className={`${THEME.status.error.text} text-sm mt-1 opacity-90`}>{error}</div>
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className={`p-4 ${THEME.containers.secondary} rounded-lg`}>
        <div className={`${THEME.text.secondary}`}>No dataset available</div>
      </div>
    );
  }

  // Extract information using Dataset methods
  const name = dataset.getName() || 'Unknown Dataset';
  const archiveType = dataset.getArchiveType()?.label || '';
  
  // Geographic information
  const location = dataset.getLocation();
  const lat = location?.latitude || '';
  const lon = location?.longitude || '';
  const elevation = location?.elevation || '';
  const siteName = location?.siteName || '';
  
  // Publications
  const publications = dataset.getPublications() || [];
  
  // Funding
  const funding = dataset.getFundings() || [];
  
  // Data sections
  const paleoDataList = dataset.getPaleoData() || [];
  const chronDataList = dataset.getChronData() || [];
  
  // Extract variables and tables from data sections
  const paleoTables = [];
  const paleoVariables = [];
  
  paleoDataList.forEach((paleoData, pdIndex) => {
    const tables = paleoData.getMeasurementTables() || [];
    tables.forEach((table, tIndex) => {
      // Don't spread the table object, keep it as-is to preserve methods
      const tableInfo = {
        table: table, // Keep the original table object
        paleoDataName: paleoData.getName() || `PaleoData ${pdIndex + 1}`,
        tableName: table.getFileName() || `Table ${tIndex + 1}`
      };
      paleoTables.push(tableInfo);
      
      // Get variables from this table
      const variables = table.getVariables() || [];
      variables.forEach(variable => {
        // Don't spread the variable object, keep it as-is to preserve methods
        const variableInfo = {
          variable: variable, // Keep the original variable object
          tableName: table.getFileName() || `Table ${tIndex + 1}`,
          paleoDataName: paleoData.getName() || `PaleoData ${pdIndex + 1}`
        };
        paleoVariables.push(variableInfo);
      });
    });
  });
  
  const chronTables = [];
  const chronVariables = [];
  
  chronDataList.forEach((chronData, cdIndex) => {
    const tables = chronData.getMeasurementTables() || [];
    tables.forEach((table, tIndex) => {
      // Don't spread the table object, keep it as-is to preserve methods
      const tableInfo = {
        table: table, // Keep the original table object
        chronDataName: `ChronData ${cdIndex + 1}`, // ChronData doesn't have getName method
        tableName: table.getFileName() || `Table ${tIndex + 1}`
      };
      chronTables.push(tableInfo);
      
      // Get variables from this table
      const variables = table.getVariables() || [];
      variables.forEach(variable => {
        // Don't spread the variable object, keep it as-is to preserve methods
        const variableInfo = {
          variable: variable, // Keep the original variable object
          tableName: table.getFileName() || `Table ${tIndex + 1}`,
          chronDataName: `ChronData ${cdIndex + 1}` // ChronData doesn't have getName method
        };
        chronVariables.push(variableInfo);
      });
    });
  });

  console.log('Dataset info:', {
    name,
    archiveType,
    location,
    publications: publications.length,
    funding: funding.length,
    paleoDataList: paleoDataList.length,
    chronDataList: chronDataList.length,
    paleoTables: paleoTables.length,
    chronTables: chronTables.length,
    paleoVariables: paleoVariables.length,
    chronVariables: chronVariables.length
  });

  return (
    <div className="space-y-4 text-sm max-h-[80vh] overflow-y-auto">
      {/* Overview Section */}
      <InfoCard title="Dataset Overview" icon="🏛️">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-2">
            <MetadataField label="Name" value={name} />
            <MetadataField label="Archive Type" value={archiveType} />
            <MetadataField label="Site Name" value={siteName} />
          </div>
          <div className="space-y-2">
            {lat && lon && (
              <MetadataField label="Location" value={`${lat}, ${lon}`} />
            )}
            {elevation && <MetadataField label="Elevation" value={elevation} />}
          </div>
        </div>
      </InfoCard>

      {/* Publications */}
      {Array.isArray(publications) && publications.length > 0 && (
        <Collapsible title="Publications" count={publications.length} icon="📚" defaultOpen={true}>
          <PublicationList publications={publications} />
        </Collapsible>
      )}

      {/* Funding */}
      {Array.isArray(funding) && funding.length > 0 && (
        <Collapsible title="Funding" count={funding.length} icon="💰">
          <div className="space-y-2">
            {funding.map((fund, idx) => (
              <div key={idx} className={`p-2 rounded border ${THEME.containers.secondary} text-xs`}>
                <MetadataField label="Agency" value={fund.getFundingAgency()} />
                <MetadataField label="Grants" value={fund.getGrants()} isArray={true} />
                <MetadataField label="Country" value={fund.getFundingCountry()} />
              </div>
            ))}
          </div>
        </Collapsible>
      )}

      {/* Paleo Variables */}
      {Array.isArray(paleoVariables) && paleoVariables.length > 0 && (
        <Collapsible title="Paleo Variables" count={paleoVariables.length} icon="🔬" defaultOpen={false}>
          <VariableList variables={paleoVariables} />
        </Collapsible>
      )}

      {/* Chron Variables */}
      {Array.isArray(chronVariables) && chronVariables.length > 0 && (
        <Collapsible title="Chronology Variables" count={chronVariables.length} icon="⏰" defaultOpen={false}>
          <VariableList variables={chronVariables} />
        </Collapsible>
      )}

      {/* Paleo Data Tables */}
      {Array.isArray(paleoTables) && paleoTables.length > 0 && (
        <Collapsible title="Paleo Data Tables" count={paleoTables.length} icon="📊" defaultOpen={true}>
          <div className="space-y-4">
            {paleoTables.map((table, idx) => (
              <div key={idx}>
                <h4 className={`font-medium ${THEME.text.primary} mb-2`}>
                  Table {idx + 1}
                  {table.tableName && ` - ${table.tableName}`}
                </h4>
                <TablePreview table={table.table} title={`Paleo Table ${idx + 1}`} />
              </div>
            ))}
          </div>
        </Collapsible>
      )}

      {/* Chron Data Tables */}
      {Array.isArray(chronTables) && chronTables.length > 0 && (
        <Collapsible title="Chronology Data Tables" count={chronTables.length} icon="📈" defaultOpen={false}>
          <div className="space-y-4">
            {chronTables.map((table, idx) => (
              <div key={idx}>
                <h4 className={`font-medium ${THEME.text.primary} mb-2`}>
                  Table {idx + 1}
                  {table.tableName && ` - ${table.tableName}`}
                </h4>
                <TablePreview table={table.table} title={`Chron Table ${idx + 1}`} />
              </div>
            ))}
          </div>
        </Collapsible>
      )}

      {/* Raw Dataset for debugging */}
      <Collapsible title="Raw Dataset Object" defaultOpen={false} icon="🔧">
        <pre className={`whitespace-pre-wrap break-words text-xs ${THEME.containers.secondary} p-3 rounded max-h-[40vh] overflow-y-auto font-mono`}>
          {JSON.stringify(dataset, null, 2)}
        </pre>
      </Collapsible>
    </div>
  );
};

export default LipdDatasetViewer; 