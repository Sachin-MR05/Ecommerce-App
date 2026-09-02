import React, { useState, useRef, useEffect } from 'react';

const BUYER_AGENT_URL = 'http://localhost:8030/buyer/chat';

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [showAgentInfo, setShowAgentInfo] = useState(false);
  const [copied, setCopied] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: 'assistant',
      text: 'Hello! I am your AI Shopping Assistant. What can I help you find or buy today?',
    },
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [chatId, setChatId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const manifest = {
    name: 'TechHaven India',
    description: 'Electronics, smartphones, and accessories',
    agentUrl: 'http://localhost:8001/agent/message',
    authToken: 'Bearer dev-token-techhaven',
    contactPhone: '+91 90000 00001',
  };

  const handleCopyManifest = () => {
    navigator.clipboard.writeText(JSON.stringify(manifest, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen && !showAgentInfo) {
      scrollToBottom();
    }
  }, [messages, isOpen, showAgentInfo]);

  const handleSend = async (e) => {
    e?.preventDefault();
    const text = inputMessage.trim();
    if (!text || isLoading) return;

    setMessages((prev) => [...prev, { sender: 'user', text }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const payload = { message: text };
      if (chatId) {
        payload.chatId = chatId;
      }

      const res = await fetch(BUYER_AGENT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      if (data.chatId) {
        setChatId(data.chatId);
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: data.message || 'I processed your request.',
        },
      ]);
    } catch (err) {
      console.error('Chatbot error:', err);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: 'Sorry, I am having trouble connecting to the assistant. Please make sure the Buyer Agent service is running.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const renderFormattedText = (text) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);

    return parts.map((part, i) => {
      if (part.match(urlRegex)) {
        return (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: '#0066cc',
              textDecoration: 'underline',
              fontWeight: '600',
              wordBreak: 'break-all',
            }}
          >
            {part.includes('checkout') ? '👉 Launch Checkout / Pay Now' : part}
          </a>
        );
      }
      return part;
    });
  };

  return (
    <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 9999 }}>
      {/* Chat Popup Box */}
      {isOpen && (
        <div
          style={{
            width: '390px',
            height: '530px',
            backgroundColor: '#ffffff',
            border: '2px solid #111111',
            borderRadius: '12px',
            boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            marginBottom: '12px',
            fontFamily: 'Arial, sans-serif',
          }}
        >
          {/* Top Bar Header */}
          <div
            style={{
              backgroundColor: '#111111',
              color: '#ffffff',
              padding: '12px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>🤖</span>
              <div>
                <div style={{ fontWeight: 'bold', fontSize: '14px' }}>Shopping Assistant</div>
                <div style={{ fontSize: '11px', opacity: 0.8 }}>TechHaven Commerce</div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {/* Agent Info Button in Chatbar Top Bar */}
              <button
                onClick={() => setShowAgentInfo((prev) => !prev)}
                style={{
                  backgroundColor: showAgentInfo ? '#ffffff' : 'rgba(255,255,255,0.15)',
                  color: showAgentInfo ? '#111111' : '#ffffff',
                  border: '1px solid rgba(255,255,255,0.4)',
                  borderRadius: '14px',
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.2s ease',
                }}
                title="View & Copy Merchant Agent Info"
              >
                <span>ℹ️</span> {showAgentInfo ? 'Chat' : 'Agent Info'}
              </button>

              {/* Close Button */}
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#ffffff',
                  fontSize: '18px',
                  cursor: 'pointer',
                  padding: '2px 6px',
                }}
                title="Close assistant"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Main Body View */}
          {showAgentInfo ? (
            /* Agent Info Modal View inside Chat Widget */
            <div
              style={{
                flex: 1,
                padding: '16px',
                backgroundColor: '#ffffff',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>🏪</span>
                <h3 style={{ margin: 0, fontSize: '16px', color: '#111111' }}>
                  Merchant Agent Manifest
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '12px', color: '#555555', lineHeight: '1.4' }}>
                Copy this manifest to connect your personal Buyer Agent directly to our merchant store:
              </p>

              <pre
                style={{
                  backgroundColor: '#f4f4f4',
                  padding: '12px',
                  borderRadius: '6px',
                  fontSize: '11.5px',
                  border: '1px solid #e0e0e0',
                  overflowX: 'auto',
                  margin: 0,
                  fontFamily: 'monospace',
                  color: '#222222',
                }}
              >
                {JSON.stringify(manifest, null, 2)}
              </pre>

              <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                <button
                  onClick={handleCopyManifest}
                  style={{
                    flex: 1,
                    backgroundColor: copied ? '#2ecc71' : '#111111',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '10px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    transition: 'background-color 0.2s ease',
                  }}
                >
                  <span>{copied ? '✅' : '📋'}</span>
                  {copied ? 'Manifest Copied!' : 'Copy Agent Manifest'}
                </button>

                <button
                  onClick={() => setShowAgentInfo(false)}
                  style={{
                    backgroundColor: '#ffffff',
                    color: '#111111',
                    border: '1px solid #111111',
                    borderRadius: '6px',
                    padding: '10px 14px',
                    fontSize: '13px',
                    fontWeight: '600',
                    cursor: 'pointer',
                  }}
                >
                  Back to Chat
                </button>
              </div>
            </div>
          ) : (
            /* Standard Chat Messages View */
            <>
              <div
                style={{
                  flex: 1,
                  padding: '14px',
                  overflowY: 'auto',
                  backgroundColor: '#f8f9fa',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justify: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '84%',
                        padding: '10px 14px',
                        borderRadius:
                          msg.sender === 'user'
                            ? '16px 16px 2px 16px'
                            : '16px 16px 16px 2px',
                        backgroundColor: msg.sender === 'user' ? '#111111' : '#ffffff',
                        color: msg.sender === 'user' ? '#ffffff' : '#111111',
                        border: msg.sender === 'assistant' ? '1px solid #e0e0e0' : 'none',
                        fontSize: '13.5px',
                        lineHeight: '1.45',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {renderFormattedText(msg.text)}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: '16px 16px 16px 2px',
                        backgroundColor: '#ffffff',
                        border: '1px solid #e0e0e0',
                        fontSize: '13px',
                        color: '#666666',
                        fontStyle: 'italic',
                      }}
                    >
                      Thinking... 💬
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <form
                onSubmit={handleSend}
                style={{
                  padding: '10px 12px',
                  backgroundColor: '#ffffff',
                  borderTop: '1px solid #e0e0e0',
                  display: 'flex',
                  gap: '8px',
                }}
              >
                <input
                  type="text"
                  placeholder="Ask anything or request checkout..."
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled={isLoading}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '20px',
                    border: '1px solid #ccc',
                    fontSize: '13.5px',
                    outline: 'none',
                  }}
                />
                <button
                  type="submit"
                  disabled={isLoading || !inputMessage.trim()}
                  style={{
                    backgroundColor: '#111111',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '20px',
                    padding: '8px 16px',
                    fontWeight: 'bold',
                    cursor: isLoading ? 'default' : 'pointer',
                    fontSize: '13px',
                  }}
                >
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      )}

      {/* Floating Toggle Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          width: '58px',
          height: '58px',
          borderRadius: '50%',
          backgroundColor: '#111111',
          color: '#ffffff',
          border: '2px solid #ffffff',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '26px',
          cursor: 'pointer',
          transition: 'transform 0.2s ease',
        }}
        title="Toggle AI Chat Assistant"
        onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
        onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
      >
        {isOpen ? '✕' : '💬'}
      </button>
    </div>
  );
}

