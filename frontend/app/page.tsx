'use client';

import { useState } from 'react';
// We can remove the Image import if it's no longer used by the new interface
// import Image from "next/image";

export default function Home() {
  const [jobRole, setJobRole] = useState('Software Engineer');
  const [location, setLocation] = useState('United States');
  const [maxPages, setMaxPages] = useState(1);
  const [results, setResults] = useState<any[] | string>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ADK_API_BASE_URL = 'http://localhost:8000';
  const APP_NAME = 'adk-backend'; // This should match the folder name of your ADK agent
  const USER_ID = 'frontend-user';
  let SESSION_ID = `session-${Date.now()}`;

  // Function definition for createSessionIfNeeded
  async function createSessionIfNeeded() {
    console.log(`Attempting to create or verify session: ${SESSION_ID} for user: ${USER_ID} and app: ${APP_NAME}`);
    try {
      const response = await fetch(
        `${ADK_API_BASE_URL}/apps/${APP_NAME}/users/${USER_ID}/sessions/${SESSION_ID}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ state: {} }), // Optional initial state
        }
      );
      // A 409 status code means the session already exists, which is acceptable.
      if (response.ok || response.status === 409) { 
        const data = await response.json();
        console.log('Session created or already exists:', data);
        // Update SESSION_ID if the server potentially created a new one or confirmed an existing one with a slightly different ID (though unlikely for POST)
        SESSION_ID = data.id || SESSION_ID; 
        return true;
      }
      // If not OK and not 409, it's an actual error.
      const errorData = await response.json();
      console.error('Failed to create session:', response.status, errorData);
      setError(`Failed to create session: ${errorData.detail || response.statusText}`);
      return false;
    } catch (e: any) {
      console.error('Error during session creation fetch call:', e);
      setError(`Network or other error creating session: ${e.message}`);
      return false;
    }
  }

  const handleSearch = async () => {
    setLoading(true);
    setResults([]);
    setError(null);

    SESSION_ID = `session-${Date.now()}`; // Always create a new session ID for a fresh search
    const sessionCreated = await createSessionIfNeeded();
    if (!sessionCreated) {
      setLoading(false);
      return; // Stop if session creation failed
    }

    const userQuery = `Find jobs for role '${jobRole}' in '${location}' scraping ${maxPages} pages.`;
    console.log(`User query for ADK: ${userQuery}`);
    console.log(`Sending /run request with session ID: ${SESSION_ID}`);

    try {
      const response = await fetch(`${ADK_API_BASE_URL}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          appName: APP_NAME,
          userId: USER_ID,
          sessionId: SESSION_ID, 
          newMessage: {
            role: 'user',
            parts: [{ text: userQuery }],
          },
        }),
      });

      if (!response.ok) {
        const errorData = await response.text(); 
        console.error('API Error Response from /run:', errorData);
        throw new Error(`API /run request failed: ${response.status} ${response.statusText}. Server response: ${errorData}`);
      }

      const adkResponseEvents = await response.json();
      console.log('ADK /run response events:', adkResponseEvents);
      
      let jobData = null;
      let agentMessage = "No specific message from agent.";

      for (const event of adkResponseEvents) {
        if (event.content && event.content.parts) {
          for (const part of event.content.parts) {
            if (part.functionResponse && part.functionResponse.name === 'find_jobs_on_simplyhired') {
              jobData = part.functionResponse.response;
              console.log('Extracted jobData from functionResponse:', jobData);
              break;
            }
            if (part.text && event.role === 'model') {
                agentMessage = part.text;
                console.log('Captured agent text message:', agentMessage);
            }
          }
        }
        if (jobData) break;
      }

      if (jobData && Array.isArray(jobData)) {
        if (jobData.length > 0 && jobData[0] && jobData[0].error) {
            console.error('Error reported by agent tool:', jobData[0]);
            setError(`Error from agent tool: ${jobData[0].error}${jobData[0].details ? ` - ${jobData[0].details}` : ''}`);
            setResults([]);
        } else {
            console.log('Setting job results:', jobData);
            setResults(jobData);
        }
      } else if (jobData) { 
        console.log('Setting single job result (wrapped in array):', jobData);
        setResults([jobData]);
      } 
      else {
        console.warn('No structured job data found. Agent message:', agentMessage);
        setError('No job data found in agent response. Agent said: ' + agentMessage);
        setResults([]);
      }

    } catch (e: any) {
      console.error('Search error in handleSearch catch block:', e);
      setError(`Search failed: ${e.message}`);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    // Removed the outer Next.js default layout classes like "grid grid-rows..."
    // and replaced with the simpler structure for the job agent.
    <main className="container">
      <h1>AI Job Agent</h1>
      <div className="form-container">
        <div className="form-group">
          <label htmlFor="jobRole">Job Role:</label>
          <input
            type="text"
            id="jobRole"
            value={jobRole}
            onChange={(e) => setJobRole(e.target.value)}
            placeholder="e.g., Software Engineer"
          />
        </div>
        <div className="form-group">
          <label htmlFor="location">Location:</label>
          <input
            type="text"
            id="location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g., New York or Remote"
          />
        </div>
        <div className="form-group">
          <label htmlFor="maxPages">Max Pages:</label>
          <input
            type="number"
            id="maxPages"
            value={maxPages}
            onChange={(e) => setMaxPages(parseInt(e.target.value, 10) || 1)}
            min="1"
            max="10"
          />
        </div>
        <button onClick={handleSearch} disabled={loading} className="search-button">
          {loading ? 'Searching...' : 'Search Jobs'}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <p>Error: {error}</p>
        </div>
      )}

      {/* Results Display */}
      {results.length > 0 && typeof results !== 'string' && (
        <div className="results-container">
          <h2>Search Results:</h2>
          {results.map((job, index) => (
            <div key={index} className="job-item">
              <h3>{job.title || 'N/A'}</h3>
              <p><strong>Company:</strong> {job.company || 'N/A'}</p>
              <p><strong>Location:</strong> {job.location || 'N/A'}</p>
              <p><strong>URL:</strong>
                {job.url && job.url !== 'N/A' ?
                  <a href={job.url} target="_blank" rel="noopener noreferrer">{job.url}</a> : 'N/A'}
              </p>
              {job.page_scraped && <p><em><small>Scraped from page: {job.page_scraped}</small></em></p>}
            </div>
          ))}
        </div>
      )}
      {/* Display string results if that's what was set (e.g. for non-array error messages from agent) */}
      {typeof results === 'string' && results.length > 0 && (
         <div className="results-container">
            <h2>Agent Response:</h2>
            <pre>{results}</pre>
        </div>
      )}

    </main>
  );
}
