import { useEffect, useState } from 'react';
import { buildApiUrl } from '../config/api';

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
      let fetchDone = false; // Use local variable instead of state
      console.log('Starting fetch loop with offset:', offset, 'batchSize:', batchSize);
      console.log('Loop conditions - cancel:', cancel, 'fetchDone:', fetchDone);
      
      while (!cancel && !fetchDone) {
        try {
          console.log('Fetching batch with offset:', offset);
          const resp = await fetch(buildApiUrl('/api/sparql/run'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: sparqlQuery, limit: batchSize, offset })
          });
          
          if (!resp.ok) {
            console.error('Fetch failed with status:', resp.status);
            const errorText = await resp.text();
            console.error('Error response:', errorText);
            break;
          }
          
          const json = await resp.json();
          console.log('Received response:', json);
          const newRows = json.rows || [];
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
          console.error('Fetch error:', e);
          break;
        }
      }
      console.log('Fetch loop completed');
    };
    fetchLoop();
    return () => {
      cancel = true;
    };
  }, [sparqlQuery, enabled]);

  return rows;
} 