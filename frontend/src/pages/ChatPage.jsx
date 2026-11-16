import { useRef, useState } from 'react';
import { ArrowUp, ArrowUpRight, BookOpen, Bug, Flower2, Leaf, Recycle, RotateCcw, Sparkles, Sprout } from 'lucide-react';
import ChatWindow from '../components/ChatWindow';
import { api } from '../services/api';

const prompts = [
  { icon: Sprout, label: 'Grow better', question: 'How do I grow organic ginger in Sikkim?', text: 'Organic ginger cultivation' },
  { icon: Bug, label: 'Protect your crops', question: 'How can I manage pests in organic tomato farming?', text: 'Natural pest management' },
  { icon: Recycle, label: 'Nourish your soil', question: 'How can I prepare compost for organic farming?', text: 'Composting & soil health' },
  { icon: Flower2, label: 'Find local guidance', question: 'What are the best practices for large cardamom cultivation?', text: 'Large cardamom farming' },
];

export default function ChatPage({ health, connectionError, stats, messages, setMessages }) {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const input = useRef();
  async function submit(event) {
    event?.preventDefault();
    if (!question.trim() || busy) return;
    const content = question.trim();
    const history = messages.filter(m => !m.failed).map(m => ({ role: m.role, content: m.content })).slice(-12);
    setMessages(current => [...current, { role: 'user', content }]);
    setQuestion(''); setBusy(true); setError('');
    try {
      const result = await api.chat({ question: content, history });
      setMessages(current => [...current, { role: 'assistant', content: result.answer, ...result }]);
    } catch (failure) {
      setError(failure.message);
      setMessages(current => current.map((message, i) => i === current.length - 1 ? { ...message, failed: true } : message));
      setQuestion(content);
    } finally { setBusy(false); input.current?.focus(); }
  }
  const empty = messages.length === 0;
  return <div className="page chat-page">
    <div className="page-heading"><div><div className="eyebrow"><span/> YOUR FARMING COMPANION</div><h1>Farming assistant</h1><p>Your Organic Farming Guide for Sikkim</p></div>
      <button className="button quiet" disabled={busy || empty} onClick={() => { setMessages([]); setError(''); }}><RotateCcw size={15}/> New conversation</button></div>
    <div className="chat-layout"><section className="conversation-panel" aria-label="Farming conversation">
      <div className="panel-top"><div><span className="tiny-sprout"><Sprout size={17}/></span><b>Krishi Mitra</b><span className="muted">/</span><span>Let's grow together</span></div><span className="language-tag">EN / नेपाली</span></div>
      {empty ? <div className="welcome">
        <div className="welcome-art" aria-hidden="true"><div className="sun"/><div className="hill hill-back"/><div className="hill hill-front"/><Sprout className="art-sprout" size={54} strokeWidth={1.3}/><Leaf className="art-leaf" size={25}/></div>
        <span className="hello-label">नमस्ते · NAMASTE</span><h2>Good farming starts<br/>with good knowledge.</h2>
        <p>I am Krishi Mitra, your organic farming guide for Sikkim. Ask me about organic crops, vegetables, fruits, soil management, composting, pest control, and farming practices in English or Nepali.</p>
        <div className="prompt-grid">{prompts.map(({ icon: Icon, label, text, question: value }) => <button key={label} onClick={() => { setQuestion(value); input.current?.focus(); }}><Icon size={20}/><span><small>{label}</small>{text}</span><ArrowUpRight size={15}/></button>)}</div>
      </div> : <ChatWindow messages={messages} busy={busy}/>}
      <div className="composer-wrap">
        {error && <div className="error-banner" role="alert">{error}</div>}
        {connectionError && <div className="error-banner" role="status">{connectionError}</div>}
        {health && !health.llm_configured && <div className="notice-banner">Add a Claude or Gemini API key in backend/.env to enable generation and translation.</div>}
        <form className="composer" onSubmit={submit}><textarea ref={input} aria-label="Your farming question" placeholder="Ask anything about organic farming…" value={question} maxLength={4000} disabled={busy} rows={2} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}/><div className="composer-bottom"><span>English, नेपाली, or Romanized Nepali</span><button type="submit" aria-label="Send question" disabled={!question.trim() || busy}><ArrowUp size={20}/></button></div></form>
        <p className="composer-hint"><Sparkles size={12}/> Answers are based on your uploaded sources. Always check the cited guidance.</p>
      </div>
    </section><aside className="context-column">
      <div className="context-card"><div className="card-kicker"><BookOpen size={17}/> YOUR KNOWLEDGE BASE</div><h3>Better sources.<br/>Better answers.</h3><p>Give your assistant the documents it needs to offer reliable guidance.</p><div className="kb-stats"><div><strong>{stats.document_count}</strong><small>Documents</small></div><div><strong>{stats.chunk_count}</strong><small>Indexed passages</small></div></div><a className="button outline full" href="#knowledge">Manage documents <ArrowUpRight size={15}/></a></div>
      <div className="how-card"><span className="small-label">A LITTLE ABOUT YOUR GUIDE</span><div><span>01</span><p><b>Grounded in your sources</b>Answers come from the agricultural documents you upload.</p></div><div><span>02</span><p><b>Made for Sikkim</b>Focused on locally relevant organic farming practices.</p></div><div><span>03</span><p><b>Honest about the unknown</b>When evidence is missing, your assistant will say so.</p></div></div>
      <div className="organic-note"><Leaf size={19}/><p>Small steps.<br/><b>A more sustainable harvest.</b></p></div>
    </aside></div>
  </div>;
}
