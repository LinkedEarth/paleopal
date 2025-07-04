import { useEffect, useState } from 'react';

export default function usePagedSparql(initialRows = [], sparqlQuery, batchSize = 500, enabled = true) {
  const [rows, setRows] = useState(initialRows || []);
  const [done, setDone] = useState(!enabled);

  // Separate effect to handle initialRows changes
  useEffect(() => {
    setRows(initialRows || []);
  }, [initialRows]);

  useEffect(() => {
    if (!sparqlQuery || !enabled) {
      setDone(true);
      return;
    }
    let cancel = false;

    // reset done state when starting fetch
    setDone(false);

    const fetchLoop = async () => {
      let offset = initialRows.length;
      let fetchDone = false;
      console.log('Starting direct SPARQL fetch with offset:', offset, 'batchSize:', batchSize);
      
      while (!cancel && !fetchDone) {
        try {
          console.log('Fetching batch with offset:', offset);
          
          // Direct SPARQL query to the GraphDB endpoint
          const pagedQuery = `${sparqlQuery.trim()} LIMIT ${batchSize} OFFSET ${offset}`;
          
          const response = await fetch('https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse-dynamic', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/sparql-results+json'
            },
            body: `query=${encodeURIComponent(pagedQuery)}`
          });
          
          if (!response.ok) {
            console.error('SPARQL fetch failed with status:', response.status);
            const errorText = await response.text();
            console.error('Error response:', errorText);
            break;
          }
          
          const json = await response.json();
          console.log('Received SPARQL response:', json);
          
          // Convert SPARQL results to simple rows format
          const newRows = [];
          if (json.results && json.results.bindings) {
            const vars = json.head?.vars || [];
            for (const binding of json.results.bindings) {
              const row = {};
              for (const varName of vars) {
                if (binding[varName]) {
                  row[varName] = binding[varName].value;
                } else {
                  row[varName] = null;
                }
              }
              newRows.push(row);
            }
          }
          
          console.log('New rows received:', newRows.length);
          
          if (newRows.length === 0) {
            console.log('No more rows, setting done to true');
            fetchDone = true;
            setDone(true);
            break;
          }
          
          setRows((prev) => {
            console.log('Adding', newRows.length, 'rows to existing', prev.length, 'rows');
            return [...prev, ...newRows];
          });
          offset += batchSize;
          // brief yield to keep UI responsive
          await new Promise((r) => setTimeout(r, 10));
        } catch (e) {
          console.error('Direct SPARQL fetch error:', e);
          break;
        }
      }
      console.log('Direct SPARQL fetch loop completed');
    };
    
    fetchLoop();
    return () => {
      cancel = true;
    };
  }, [sparqlQuery, enabled]);

  return rows;
} 