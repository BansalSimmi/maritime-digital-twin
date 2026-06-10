import React, { useState, useEffect, useRef } from 'react';
import api from '../api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const Chat = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<any[]>(() => {
    const saved = localStorage.getItem('marineos_chat_history');
    return saved ? JSON.parse(saved) : [
      {
        role: 'ai',
        content: "Hello! I'm your MarineOS AI assistant. I have real-time access to all vessels in your fleet, live sensor data, and emission telemetry. How can I help optimize your operations today?",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
      }
    ];
  });
  const [loading, setLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem('marineos_chat_history', JSON.stringify(messages));
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages]);

  const handleSend = async (e?: any, customMsg?: string) => {
    if (e) e.preventDefault();
    const msg = customMsg || input;
    if (!msg.trim() || loading) return;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

    setInput('');
    const newMessages = [...messages, { role: 'user', content: msg, time: now }];
    setMessages(newMessages);
    setLoading(true);

    // Prepare history for the backend (excluding the welcome message if it doesn't fit the role/content structure)
    const history = newMessages.map(m => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.content
    })).slice(-10); // Last 10 messages for context

    try {
      const res = await api.post('/api/chat', { message: msg, history });
      const data = res.data;

      let reply = '';
      if (data.error) {
        reply = `❌ **Error:** ${data.error}`;
      } else if (data.summary) {
        reply = data.summary;
      } else if (data.result && Array.isArray(data.result)) {
        reply = `✅ Found ${data.rows_returned || data.result.length} records.\n\n` +
          "| Field | Value |\n| :--- | :--- |\n" +
          Object.entries(data.result[0] || {}).map(([k, v]) => `| ${k} | ${v} |`).join('\n');
      } else {
        reply = "I couldn't process that request properly. Please try again.";
      }

      setMessages(prev => [...prev, { role: 'ai', content: reply, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) }]);
    } catch (err: any) {
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout');
      const errMsg = isTimeout
        ? '⏱️ **Request timed out.** The AI is still processing — please try again in a moment.'
        : '❌ **Connection Error:** Could not reach the backend server. Make sure it is running on port 8000.';
      setMessages(prev => [...prev, { role: 'ai', content: errMsg, time: now }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    if (window.confirm("Clear conversation history?")) {
      setMessages([{
        role: 'ai',
        content: "History cleared. How else can I assist your fleet operations?",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
      }]);
    }
  };

  const ABOUT_MARINE_OS = `**MarineOS** is the brand name given to this project — a **Maritime Digital Twin management platform**. Think of it like how "Windows OS" manages your computer; MarineOS manages your entire maritime fleet.

> **Marine** → Maritime / Ocean / Shipping industry
> **OS** → Operating System (the "brain" that runs and monitors everything)

It's a **full-stack fleet intelligence platform** with these modules acting like an "OS" for ships:

| Module | Role (like an OS component) |
| :--- | :--- |
| 🚢 Vessel Tracking | Real-time GPS / AIS data — like a Task Manager showing live processes |
| 🌐 Digital Twin | Virtual simulation of vessels — like a system emulator |
| 💨 Emissions (Carbon) | CO2/NOx/SOx monitoring — like a system health monitor |
| ⚠️ Anomaly Detection | Alerts for irregular vessel behavior — like an antivirus/firewall |
| 🤖 AI Assistant | Natural language interface to query all data — like a voice assistant for the OS |

So in short — **MarineOS = an operating system for your maritime fleet**, where instead of managing files and apps, it manages vessels, emissions, anomalies, and routes in real time.`;

  const handleAboutMarineOS = () => {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    setMessages(prev => [
      ...prev,
      { role: 'user', content: 'About MarineOS', time: now },
      { role: 'ai', content: ABOUT_MARINE_OS, time: now }
    ]);
  };

  const suggestions = [
    "Show active anomalies",
    "Highest CO2 emitter",
    "Top polluters",
  ];

  return (
    <div className="page on" style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)' }}>
      {/* RICH HEADER */}
      <div className="ch-h">
        <div className="ch-h-left">
          <div className="ch-h-icon">🤖</div>
          <div>
            <div className="ch-h-title">MarineOS Intelligence</div>
            <div className="ch-h-status">
              <div className="ch-h-dot"></div>
              Active — Llama-3.1 Enhanced
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div className="ch-h-context">Fleet Context Loaded</div>
          <button onClick={clearChat} style={{
            background: 'rgba(255,59,59,0.1)',
            border: '1px solid rgba(255,59,59,0.2)',
            color: 'var(--danger)',
            fontSize: '10px',
            padding: '4px 10px',
            borderRadius: '6px',
            cursor: 'pointer'
          }}>Clear</button>
        </div>
      </div>

      <div className="clayout" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div ref={chatContainerRef} className="cmsgs" style={{ flex: 1, padding: '24px 20px', overflowY: 'auto' }}>
          {messages.map((m, i) => (
            <div key={i} className={`cmsg-wrap ${m.role === 'ai' ? 'ai' : 'u'}`}>
              <div className={`cmsg-avatar ${m.role === 'ai' ? 'ai' : 'u'}`}>
                {m.role === 'ai' ? '🤖' : '👤'}
              </div>
              <div className="cbub-container">
                <div className="cbub markdown-container">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content}
                  </ReactMarkdown>
                </div>
                <div className="cbub-ts">{m.time}</div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="cmsg-wrap ai">
              <div className="cmsg-avatar ai">🤖</div>
              <div className="cbub-container">
                <div className="cbub italic opacity-60">
                  <span className="blink">Generating operational insight...</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* SUGGESTION CHIPS */}
        <div className="csug" style={{ padding: '0 20px 16px' }}>
          {suggestions.map(s => (
            <div key={s} className="chip" onClick={() => handleSend(null, s)} style={{ borderRadius: '10px', padding: '6px 14px' }}>
              {s}
            </div>
          ))}
          <div className="chip" onClick={handleAboutMarineOS} style={{ borderRadius: '10px', padding: '6px 14px' }}>
            About Marine OS
          </div>
        </div>

        {/* INPUT AREA */}
        <form className="cia" onSubmit={handleSend} style={{ background: 'var(--panel)', padding: '16px 20px 24px', borderTop: '1px solid var(--b)' }}>
          <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <input
              className="cinp"
              placeholder="Ask about your fleet, emissions, anomalies, routes..."
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={loading}
              style={{
                background: 'var(--bg3)',
                border: '1px solid var(--b)',
                borderRadius: '12px',
                padding: '0 16px',
                height: '48px',
                flex: 1,
                fontSize: '13px',
                color: 'var(--text)'
              }}
            />
            <button className="csnd" type="submit" disabled={loading} style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: loading ? 'var(--bg3)' : 'linear-gradient(135deg, #3b82f6, #2563eb)',
              border: 'none',
              boxShadow: '0 4px 12px rgba(37, 99, 235, 0.2)',
              cursor: loading ? 'default' : 'pointer',
              color: '#fff'
            }}>
              {loading ? <div className="spin"></div> : '➤'}
            </button>
          </div>
        </form>
      </div>

      <style>{`
        .markdown-container table {
          border-collapse: collapse;
          width: 100%;
          margin: 10px 0;
          font-size: 11px;
        }
        .markdown-container th, .markdown-container td {
          border: 1px solid var(--b2);
          padding: 8px;
          text-align: left;
        }
        .markdown-container th {
          background: rgba(0,200,255,0.05);
          color: var(--accent);
          font-weight: 700;
          text-transform: uppercase;
          font-size: 9px;
        }
        .markdown-container p { margin-bottom: 8px; }
        .markdown-container p:last-child { margin-bottom: 0; }
        .markdown-container ul, .markdown-container ol { margin-left: 20px; margin-bottom: 8px; }
        .markdown-container li { margin-bottom: 4px; }
      `}</style>
    </div>
  );
};

export default Chat;
