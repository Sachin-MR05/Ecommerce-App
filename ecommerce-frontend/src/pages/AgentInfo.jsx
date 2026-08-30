import React, { useState } from 'react';

export default function AgentInfo() {
  const [copied, setCopied] = useState(false);
  const manifest = {
    name: "TechHaven India",
    description: "Electronics, smartphones, and accessories",
    agentUrl: "http://localhost:8001/agent/message",
    authToken: "Bearer dev-token-techhaven",
    contactPhone: "+91 90000 00001"
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ maxWidth: '600px', margin: '60px auto', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', background: '#fff', textAlign: 'center' }}>
      <h2>Merchant Agent Manifest</h2>
      <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
        Copy this manifest to connect your personal Buyer Agent to our merchant store.
      </p>
      <pre style={{ textAlign: 'left', background: '#f5f5f5', padding: '15px', borderRadius: '6px', fontSize: '13px', overflowX: 'auto' }}>
        {JSON.stringify(manifest, null, 2)}
      </pre>
      <button 
        onClick={handleCopy}
        style={{ background: copied ? '#2ecc71' : '#528FF0', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', marginTop: '15px' }}
      >
        {copied ? 'Copied!' : 'Copy Manifest'}
      </button>
    </div>
  );
}
