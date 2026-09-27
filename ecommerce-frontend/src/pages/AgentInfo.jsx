import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiClient from '../services/apiClient';

export default function AgentInfo() {
  const { isAuthenticated, user } = useAuth();
  const [manifest, setManifest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isAuthenticated) {
      setLoading(true);
      setError(null);
      apiClient.get('/api/agent/manifest')
        .then((res) => {
          setManifest(res.data);
        })
        .catch((err) => {
          console.error('Failed to load agent manifest:', err);
          setError('Could not load personalized agent manifest.');
        })
        .finally(() => setLoading(false));
    } else {
      setManifest(null);
    }
  }, [isAuthenticated]);

  const handleCopy = () => {
    if (!manifest) return;
    navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ maxWidth: '640px', margin: '50px auto', padding: '24px', border: '1px solid #e0e0e0', borderRadius: '10px', background: '#fff', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
        <span style={{ fontSize: '24px' }}>🏪</span>
        <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800 }}>Merchant Agent Manifest</h2>
      </div>

      <p style={{ color: '#555', fontSize: '13.5px', marginBottom: '20px', lineHeight: '1.5' }}>
        Connect your personal Buyer Agent directly to TechHaven Commerce for automated shopping and cart isolation.
      </p>

      {!isAuthenticated ? (
        <div style={{ padding: '24px', background: '#f8f9fa', border: '1px dashed #ced4da', borderRadius: '8px', textAlign: 'center' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>🔒</div>
          <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 700, color: '#222' }}>
            Login Required for Dedicated Agent ID
          </h3>
          <p style={{ fontSize: '13px', color: '#666', margin: '0 0 16px', lineHeight: '1.4' }}>
            Please log in or register to generate your unique Buyer Agent ID and ensure your agent's cart never collides with other users.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '10px' }}>
            <Link to="/login" style={{ padding: '8px 20px', background: '#111', color: '#fff', textDecoration: 'none', borderRadius: '4px', fontSize: '13px', fontWeight: 'bold' }}>
              Log In
            </Link>
            <Link to="/register" style={{ padding: '8px 20px', background: '#fff', color: '#111', border: '1px solid #111', textDecoration: 'none', borderRadius: '4px', fontSize: '13px', fontWeight: 'bold' }}>
              Register
            </Link>
          </div>
        </div>
      ) : loading ? (
        <div style={{ padding: '30px', textAlign: 'center', color: '#666', fontSize: '14px' }}>
          Generating your dedicated Agent ID...
        </div>
      ) : error ? (
        <div style={{ padding: '16px', background: '#f8d7da', color: '#721c24', borderRadius: '6px', fontSize: '13px' }}>
          {error}
        </div>
      ) : manifest ? (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#2b8a3e', background: '#ebfbee', padding: '3px 8px', borderRadius: '4px' }}>
              ● Assigned to: {user?.username} &nbsp;|&nbsp; Agent: <code>{manifest.agentUsername}</code>
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px' }}>
            Owner email used for verification: <strong>{manifest.ownerEmail}</strong>
          </div>

          <pre style={{ textAlign: 'left', background: '#f8f9fa', padding: '14px', borderRadius: '6px', fontSize: '12.5px', border: '1px solid #e9ecef', overflowX: 'auto', fontFamily: 'monospace', color: '#212529', lineHeight: '1.45' }}>
            {JSON.stringify(manifest, null, 2)}
          </pre>

          <button 
            onClick={handleCopy}
            style={{ 
              background: copied ? '#2b8a3e' : '#111', 
              color: '#fff', 
              border: 'none', 
              padding: '11px 22px', 
              borderRadius: '6px', 
              cursor: 'pointer', 
              marginTop: '16px',
              fontSize: '13.5px',
              fontWeight: 'bold',
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'background-color 0.2s ease'
            }}
          >
            <span>{copied ? '✅' : '📋'}</span>
            {copied ? 'Manifest Copied to Clipboard!' : 'Copy Dedicated Agent Manifest'}
          </button>
        </div>
      ) : null}
    </div>
  );
}
