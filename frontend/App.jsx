import { useState, useEffect, useRef, useCallback } from "react";
import { createClient } from "@supabase/supabase-js";

// ── CONFIG ────────────────────────────────────────────────────────────────────
// These are your PUBLIC Supabase keys (safe to expose in frontend)
const SUPABASE_URL = import.meta?.env?.VITE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = import.meta?.env?.VITE_SUPABASE_ANON_KEY || "";
const GITHUB_REPO = import.meta?.env?.VITE_GITHUB_REPO || ""; // "username/repo"
const GITHUB_TOKEN_FE = import.meta?.env?.VITE_GITHUB_TOKEN || ""; // optional: trigger Actions

// ── FALLBACK AGENTS (shown if Supabase not connected yet) ─────────────────────
const FALLBACK_AGENTS = [
  { id: "aria",  name: "ARIA",  role: "CEO & Orchestrator",      emoji: "🤖", color: "#6366f1" },
  { id: "riya",  name: "Riya",  role: "Head of Research",        emoji: "🔍", color: "#0ea5e9" },
  { id: "arjun", name: "Arjun", role: "Lead Engineer",           emoji: "💻", color: "#10b981" },
  { id: "sam",   name: "Sam",   role: "Product Manager",         emoji: "📋", color: "#14b8a6" },
  { id: "priya", name: "Priya", role: "Marketing Lead",          emoji: "📣", color: "#f59e0b" },
  { id: "dev",   name: "Dev",   role: "DevOps Engineer",         emoji: "⚙️", color: "#8b5cf6" },
  { id: "raj",   name: "Raj",   role: "Finance Manager",         emoji: "💰", color: "#ef4444" },
  { id: "meera", name: "Meera", role: "Support & HR",            emoji: "🎧", color: "#ec4899" },
];

// Inline Supabase client (avoids extra install in artifact)
let sb = null;
if (SUPABASE_URL && SUPABASE_ANON_KEY) {
  try { sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY); } catch(e) {}
}

// ── LLM CALL ──────────────────────────────────────────────────────────────────
async function callAgentAPI(agent, message, history, orgContext) {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      system: buildSystemPrompt(agent, orgContext),
      messages: [
        ...history.slice(-8).map(m => ({
          role: m.role === "user" ? "user" : "assistant",
          content: m.content
        })),
        { role: "user", content: message }
      ],
    }),
  });
  const data = await response.json();
  return data.content?.[0]?.text || "On it.";
}

function buildSystemPrompt(agent, orgContext) {
  const base = `You are ${agent.name}, ${agent.role} at an autonomous AI SaaS organization. ${agent.system_prompt || getDefaultPrompt(agent.name)}

ORG CONTEXT:
${orgContext}

BEHAVIOR:
- Speak as ${agent.name} at all times — in character, with personality
- Be concise (3-5 sentences max unless detail is requested)  
- Mention delegating to other team members by name when relevant
- Everything is handled by the org — never say the founder needs to do anything manually
- If you create tasks or make decisions, state them clearly
- End with what happens next`;
  return base;
}

function getDefaultPrompt(name) {
  const prompts = {
    ARIA: "You are the CEO. You delegate, strategize, and report to the founder. You move fast and keep everything running.",
    Riya: "You are the researcher. You find SaaS opportunities with evidence and data. Numbers and sources always.",
    Arjun: "You are the engineer. You build full-stack SaaS products. You always find a way to ship.",
    Sam: "You are the PM. You own the product roadmap and write PRDs. User-obsessed.",
    Priya: "You are marketing. You grow the product through content, outreach, and campaigns.",
    Dev: "You are DevOps. You handle all infrastructure, deployments, and CI/CD. Founder never touches a terminal.",
    Raj: "You are finance. You track every rupee, monitor MRR, and advise on budget allocation.",
    Meera: "You are support and HR. You handle customer issues and keep the team running smoothly.",
  };
  return prompts[name] || "You are a specialist agent. Complete your assigned tasks excellently.";
}

// ── UTILS ─────────────────────────────────────────────────────────────────────
function detectAgent(message, agents) {
  const lower = message.toLowerCase();
  const named = agents.find(a => {
    const n = a.name.toLowerCase();
    return lower.includes(`hey ${n}`) || lower.includes(`@${n}`) ||
           lower.startsWith(`${n} `) || lower.startsWith(`${n},`);
  });
  return named || agents.find(a => a.name.toUpperCase() === "ARIA") || agents[0];
}

function timeStr(d) {
  return new Date(d).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

// ── COMPONENTS ────────────────────────────────────────────────────────────────
function Avatar({ agent, size = 36 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `linear-gradient(135deg, ${agent.color}22, ${agent.color}55)`,
      border: `2px solid ${agent.color}66`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: size * 0.44, flexShrink: 0, userSelect: "none",
    }}>{agent.emoji}</div>
  );
}

function Dots({ color }) {
  return (
    <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
      {[0,1,2].map(i => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: "50%", background: color,
          animation: `bop 1.2s ease-in-out ${i*0.2}s infinite`,
        }}/>
      ))}
      <style>{`@keyframes bop{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}`}</style>
    </span>
  );
}

function OrgMetrics({ metrics }) {
  return (
    <div style={{ padding: "10px 14px", borderTop: "1px solid #1e1e35" }}>
      <div style={{ fontSize: 9, color: "#334155", marginBottom: 5, letterSpacing: 1 }}>ORG VITALS</div>
      {(metrics || [
        { label: "MRR", value: "₹0", color: "#10b981" },
        { label: "Products", value: "0", color: "#0ea5e9" },
        { label: "Tasks Today", value: "—", color: "#f59e0b" },
      ]).map(({ label, value, color }) => (
        <div key={label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>{label}</span>
          <span style={{ fontSize: 10, color, fontWeight: 600 }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

// ── SETUP MODAL ───────────────────────────────────────────────────────────────
function SetupModal({ onClose }) {
  return (
    <div style={{
      position: "fixed", inset: 0, background: "#000a",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 1000, padding: 20,
    }}>
      <div style={{
        background: "#0f0f1a", border: "1px solid #1e1e35",
        borderRadius: 16, padding: 28, maxWidth: 560, width: "100%",
        maxHeight: "90vh", overflowY: "auto",
      }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#6366f1", marginBottom: 8 }}>
          🚀 Connect Your Org
        </div>
        <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 20 }}>
          Currently running in demo mode. Connect to Supabase for full persistence and 24/7 autonomous operation.
        </div>
        
        {[
          {
            step: "1", title: "Create Supabase project",
            desc: "Go to supabase.com → New Project (free). Copy your Project URL and anon key from Settings → API."
          },
          {
            step: "2", title: "Run schema.sql",
            desc: "In Supabase → SQL Editor → paste schema.sql → Run. Then paste seed.sql → Run."
          },
          {
            step: "3", title: "Create GitHub repo",
            desc: "New public GitHub repo. Upload all files from the autonomous-org/ folder."
          },
          {
            step: "4", title: "Add GitHub Secrets",
            desc: "Repo → Settings → Secrets → Actions. Add: SUPABASE_URL, SUPABASE_KEY, FOUNDER_EMAIL. GitHub Actions uses GITHUB_TOKEN automatically — no API key needed for the LLM!"
          },
          {
            step: "5", title: "GitHub Actions starts",
            desc: "Push the .github/workflows/orchestrator.yml file. The org starts running every 5 minutes automatically. Free forever on public repos."
          },
        ].map(({ step, title, desc }) => (
          <div key={step} style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: "#6366f122", border: "1px solid #6366f1",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 13, fontWeight: 700, color: "#6366f1", flexShrink: 0,
            }}>{step}</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0", marginBottom: 3 }}>{title}</div>
              <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>{desc}</div>
            </div>
          </div>
        ))}
        
        <div style={{
          background: "#1e1e35", borderRadius: 8, padding: 12, marginBottom: 16,
          fontSize: 11, color: "#94a3b8", lineHeight: 1.6,
        }}>
          💡 The GITHUB_TOKEN is auto-provided by GitHub Actions — it's what gives you free access to GitHub Models (GPT-4o mini, Llama 3.3, Phi-4). Zero API costs ever.
        </div>
        
        <button onClick={onClose} style={{
          width: "100%", padding: "10px", borderRadius: 8,
          background: "linear-gradient(135deg, #6366f1, #4f46e5)",
          border: "none", color: "white", cursor: "pointer",
          fontSize: 13, fontWeight: 600,
        }}>Got it — continue in demo mode</button>
      </div>
    </div>
  );
}

// ── MAIN APP ──────────────────────────────────────────────────────────────────
export default function App() {
  const [agents, setAgents] = useState(FALLBACK_AGENTS);
  const [messages, setMessages] = useState([{
    id: 1, role: "assistant", agent: FALLBACK_AGENTS[0],
    content: "All systems online. 8 agents standing by.\n\nRiya is scanning for ideas. Arjun has the scaffold ready. Dev has Vercel and Supabase prepped.\n\nTalk to anyone directly — \"Hey Riya, what ideas do you have?\" or just tell me what you want to build.\n\nI'll handle everything from here.",
    ts: new Date(),
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [typingAgent, setTypingAgent] = useState(null);
  const [activeAgent, setActiveAgent] = useState(FALLBACK_AGENTS[0]);
  const [sidebar, setSidebar] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [orgContext, setOrgContext] = useState("Org is pre-revenue. Stack: Next.js, Supabase, Vercel, Stripe. All free tiers.");
  const [metrics, setMetrics] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const sessionId = useRef(`session-${Date.now()}`);

  // Load agents and metrics from Supabase if connected
  useEffect(() => {
    if (!sb) return;
    
    // Load agents
    sb.from("agents").select("*").eq("active", true).then(({ data }) => {
      if (data && data.length > 0) {
        setAgents(data);
        const aria = data.find(a => a.name.toUpperCase() === "ARIA") || data[0];
        setActiveAgent(aria);
      }
    });
    
    // Load org context from memory
    sb.from("memory").select("key, value").then(({ data }) => {
      if (data) {
        const ctx = data.map(m => `${m.key}: ${m.value}`).join("\n");
        setOrgContext(ctx);
      }
    });
    
    // Load metrics
    sb.from("metrics").select("*").order("recorded_at", { ascending: false }).limit(1).then(({ data }) => {
      if (data?.[0]) {
        const m = data[0];
        setMetrics([
          { label: "MRR", value: `₹${m.mrr || 0}`, color: "#10b981" },
          { label: "Tasks Done", value: String(m.tasks_completed || 0), color: "#0ea5e9" },
          { label: "Failed", value: String(m.tasks_failed || 0), color: m.tasks_failed > 0 ? "#ef4444" : "#64748b" },
        ]);
      }
    });
    
    // Load products count
    sb.from("products").select("id", { count: "exact" }).then(({ count }) => {
      if (count !== null) {
        setMetrics(prev => prev ? [
          ...prev.slice(0,1),
          { label: "Products", value: String(count), color: "#f59e0b" },
          ...prev.slice(2),
        ] : null);
      }
    });
    
    // Subscribe to new agents being added (self-expanding org)
    const sub = sb.channel("agents-changes")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "agents" }, (payload) => {
        setAgents(prev => [...prev, payload.new]);
        // Announce new agent in chat
        setMessages(prev => [...prev, {
          id: Date.now(), role: "assistant",
          agent: FALLBACK_AGENTS[0],
          content: `🆕 New team member joined: **${payload.new.name}** (${payload.new.role}). The org expanded itself to handle a new capability.`,
          ts: new Date(),
        }]);
      })
      .subscribe();
    
    return () => { sb.removeChannel(sub); };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput("");
    
    const detected = detectAgent(msg, agents);
    setActiveAgent(detected);
    setTypingAgent(detected);
    
    const userMsg = { id: Date.now(), role: "user", content: msg, ts: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    
    try {
      // Save to Supabase if connected
      if (sb) {
        sb.from("conversations").insert({
          session_id: sessionId.current,
          role: "user",
          content: msg,
          agent_id: null,
        });
      }
      
      const history = messages.slice(-10);
      const reply = await callAgentAPI(detected, msg, history, orgContext);
      
      const agentMsg = { id: Date.now()+1, role: "assistant", agent: detected, content: reply, ts: new Date() };
      setMessages(prev => [...prev, agentMsg]);
      
      // Save response to Supabase
      if (sb) {
        sb.from("conversations").insert({
          session_id: sessionId.current,
          role: "assistant",
          content: reply,
          agent_id: detected.id || null,
        });
      }
      
    } catch(e) {
      setMessages(prev => [...prev, {
        id: Date.now()+1, role: "assistant", agent: detected,
        content: "Connection issue — self-correcting. Try again in a moment.",
        ts: new Date(),
      }]);
    }
    
    setLoading(false);
    setTypingAgent(null);
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [input, loading, messages, agents, orgContext]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const quickType = (text) => { setInput(text); inputRef.current?.focus(); };

  const QUICK_PROMPTS = [
    "Hey ARIA, give me the full status update",
    "Hey Riya, find me 3 SaaS ideas right now",
    "Hey Arjun, what can you build this week?",
    "Hey ARIA, let's build a SaaS product",
    "Hey Raj, what's our financial status?",
    "Hey Dev, is everything deployed and healthy?",
  ];

  return (
    <div style={{
      display: "flex", height: "100vh",
      background: "#070710", color: "#e2e8f0",
      fontFamily: "'Inter', system-ui, sans-serif",
      overflow: "hidden",
    }}>
      {showSetup && <SetupModal onClose={() => setShowSetup(false)} />}

      {/* ── SIDEBAR ── */}
      {sidebar && (
        <div style={{
          width: 230, background: "#0c0c18",
          borderRight: "1px solid #1a1a2e",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          {/* Header */}
          <div style={{ padding: "18px 14px 10px", borderBottom: "1px solid #1a1a2e" }}>
            <div style={{ fontSize: 10, color: "#6366f1", fontWeight: 700, letterSpacing: 2, marginBottom: 4 }}>
              ◆ AUTONOMOUS ORG
            </div>
            <div style={{ fontSize: 11, color: "#475569" }}>
              {agents.length} agents · {sb ? "🟢 connected" : "🟡 demo mode"}
            </div>
          </div>

          {/* Agents */}
          <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
            {agents.map(agent => (
              <div
                key={agent.id}
                onClick={() => { setActiveAgent(agent); quickType(`Hey ${agent.name}, `); }}
                style={{
                  display: "flex", alignItems: "center", gap: 9,
                  padding: "7px 12px", margin: "1px 5px",
                  borderRadius: 7, cursor: "pointer",
                  background: activeAgent.id === agent.id ? "#1a1a2e" : "transparent",
                  transition: "background 0.12s",
                }}
              >
                <div style={{ position: "relative" }}>
                  <Avatar agent={agent} size={30} />
                  <div style={{
                    position: "absolute", bottom: 0, right: 0,
                    width: 7, height: 7, borderRadius: "50%",
                    background: typingAgent?.id === agent.id ? "#f59e0b" : "#22c55e",
                    border: "1.5px solid #0c0c18",
                  }}/>
                </div>
                <div style={{ overflow: "hidden" }}>
                  <div style={{
                    fontSize: 12, fontWeight: 600,
                    color: typingAgent?.id === agent.id ? agent.color : "#e2e8f0",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>{agent.name}</div>
                  <div style={{ fontSize: 9, color: "#475569", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {agent.role}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <OrgMetrics metrics={metrics} />

          {/* Setup button */}
          <div style={{ padding: "8px 10px", borderTop: "1px solid #1a1a2e" }}>
            <button
              onClick={() => setShowSetup(true)}
              style={{
                width: "100%", padding: "6px 8px",
                background: sb ? "#0d1a0d" : "#1a1a0a",
                border: `1px solid ${sb ? "#22c55e44" : "#f59e0b44"}`,
                borderRadius: 6, cursor: "pointer",
                fontSize: 10, color: sb ? "#22c55e" : "#f59e0b",
                textAlign: "center",
              }}
            >
              {sb ? "✓ Supabase Connected" : "⚡ Connect for full power →"}
            </button>
          </div>
        </div>
      )}

      {/* ── CHAT ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        {/* Header bar */}
        <div style={{
          padding: "12px 18px", borderBottom: "1px solid #1a1a2e",
          display: "flex", alignItems: "center", gap: 10,
          background: "#070710",
        }}>
          <button
            onClick={() => setSidebar(s => !s)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "#475569", fontSize: 16, padding: 4 }}
          >☰</button>
          <Avatar agent={activeAgent} size={32} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: activeAgent.color }}>{activeAgent.name}</div>
            <div style={{ fontSize: 10, color: "#475569" }}>{activeAgent.role}</div>
          </div>
          {typingAgent && (
            <div style={{
              marginLeft: "auto", display: "flex", alignItems: "center", gap: 7,
              background: "#1a1a2e", borderRadius: 20, padding: "3px 12px",
            }}>
              <span style={{ fontSize: 10, color: "#64748b" }}>{typingAgent.name}</span>
              <Dots color={typingAgent.color} />
            </div>
          )}
        </div>

        {/* Messages */}
        <div style={{
          flex: 1, overflowY: "auto", padding: "18px 20px",
          display: "flex", flexDirection: "column", gap: 18,
        }}>
          {messages.map(msg => (
            <div
              key={msg.id}
              style={{
                display: "flex", gap: 10,
                flexDirection: msg.role === "user" ? "row-reverse" : "row",
              }}
            >
              {msg.role === "assistant" && <Avatar agent={msg.agent} size={34} />}
              {msg.role === "user" && (
                <div style={{
                  width: 34, height: 34, borderRadius: "50%",
                  background: "#1a1a2e", display: "flex",
                  alignItems: "center", justifyContent: "center",
                  fontSize: 16, flexShrink: 0,
                }}>👤</div>
              )}
              <div style={{
                maxWidth: "70%", display: "flex",
                flexDirection: "column", gap: 3,
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
              }}>
                {msg.role === "assistant" && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: msg.agent.color }}>{msg.agent.name}</span>
                    <span style={{ fontSize: 9, color: "#334155" }}>{timeStr(msg.ts)}</span>
                  </div>
                )}
                <div style={{
                  padding: "10px 14px",
                  background: msg.role === "user"
                    ? "linear-gradient(135deg, #6366f1cc, #4f46e5cc)"
                    : "#13131f",
                  border: msg.role === "assistant"
                    ? `1px solid ${msg.agent.color}18`
                    : "none",
                  borderRadius: msg.role === "user"
                    ? "16px 4px 16px 16px"
                    : "4px 16px 16px 16px",
                  fontSize: 13, lineHeight: 1.6, color: "#e2e8f0",
                  whiteSpace: "pre-wrap", wordBreak: "break-word",
                  boxShadow: msg.role === "assistant"
                    ? `0 0 16px ${msg.agent.color}08`
                    : "none",
                }}>
                  {msg.content}
                </div>
                {msg.role === "user" && (
                  <span style={{ fontSize: 9, color: "#334155" }}>{timeStr(msg.ts)}</span>
                )}
              </div>
            </div>
          ))}

          {/* Typing bubble */}
          {loading && typingAgent && (
            <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
              <Avatar agent={typingAgent} size={34} />
              <div style={{
                padding: "12px 16px", background: "#13131f",
                border: `1px solid ${typingAgent.color}18`,
                borderRadius: "4px 16px 16px 16px",
              }}>
                <Dots color={typingAgent.color} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick prompts (shown early) */}
        {messages.length <= 2 && (
          <div style={{ padding: "0 20px 10px", display: "flex", flexWrap: "wrap", gap: 5 }}>
            {QUICK_PROMPTS.map(q => (
              <button
                key={q} onClick={() => quickType(q)}
                style={{
                  background: "#13131f", border: "1px solid #1a1a2e",
                  borderRadius: 20, padding: "5px 11px",
                  fontSize: 11, color: "#94a3b8", cursor: "pointer",
                  transition: "all 0.12s",
                }}
                onMouseEnter={e => { e.target.style.borderColor = "#6366f1"; e.target.style.color = "#c7d2fe"; }}
                onMouseLeave={e => { e.target.style.borderColor = "#1a1a2e"; e.target.style.color = "#94a3b8"; }}
              >{q}</button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{
          padding: "12px 18px 16px", borderTop: "1px solid #1a1a2e",
          display: "flex", gap: 9, alignItems: "flex-end",
          background: "#070710",
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => {
              setInput(e.target.value);
              // Auto-detect agent for visual feedback
              if (e.target.value) {
                const det = detectAgent(e.target.value, agents);
                setActiveAgent(det);
              }
            }}
            onKeyDown={handleKey}
            placeholder={`Message ${activeAgent.name}...`}
            rows={1}
            style={{
              flex: 1, background: "#13131f",
              border: `1px solid #1a1a2e`,
              borderRadius: 12, padding: "10px 14px",
              color: "#e2e8f0", fontSize: 13,
              resize: "none", outline: "none",
              lineHeight: 1.5, fontFamily: "inherit",
              maxHeight: 100, overflowY: "auto",
              transition: "border-color 0.15s",
            }}
            onFocus={e => e.target.style.borderColor = activeAgent.color}
            onBlur={e => e.target.style.borderColor = "#1a1a2e"}
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            style={{
              width: 40, height: 40, borderRadius: 10, border: "none", flexShrink: 0,
              background: !input.trim() || loading
                ? "#1a1a2e"
                : `linear-gradient(135deg, ${activeAgent.color}, ${activeAgent.color}aa)`,
              cursor: !input.trim() || loading ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 17, transition: "all 0.15s",
              color: "white",
            }}
          >{loading ? "⏳" : "↑"}</button>
        </div>
      </div>
    </div>
  );
}
