import { useRef, useState } from 'react';
import { ArrowUp, BookOpen, Bug, Flower2, Leaf, MapPin, Recycle, RotateCcw, Sprout } from 'lucide-react';
import ChatWindow from '../components/ChatWindow';
import { api } from '../services/api';

const prompts = [
  { icon: Sprout, question: 'How do I grow organic ginger in Sikkim?', text: 'Organic ginger cultivation' },
  { icon: Bug, question: 'How can I manage pests in organic tomato farming?', text: 'Natural pest management' },
  { icon: Recycle, question: 'How can I prepare compost for organic farming?', text: 'Composting & soil health' },
  { icon: Flower2, question: 'What are the best practices for large cardamom cultivation?', text: 'Large cardamom farming' },
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
  return (
    <div className={`page chat-page ${empty ? 'is-empty' : 'has-messages'}`}>
      <div className="page-heading">
        <div>
          <h1>Farming assistant</h1>
          <p>Practical guidance for organic farming in Sikkim.</p>
        </div>
        <button className="button quiet" disabled={busy || empty} onClick={() => { setMessages([]); setError(''); }}>
          <RotateCcw size={16}/> New conversation
        </button>
      </div>

      <div className="chat-layout">
        <section className="conversation-panel" aria-label="Farming conversation">
          <div className="panel-top">
            <span><Sprout size={18}/> Ask Krishi Mitra</span>
            <span>English / नेपाली</span>
          </div>
          {empty ? (
            <div className="welcome">
              <p className="greeting">नमस्ते. Namaste.</p>
              <h2>What's growing<br/>on your farm?</h2>
              <p>Ask about your crops, soil, compost, or plant health. We'll look for guidance in the documents you've added.</p>
              <div className="suggestions">
                <p>Or start with a question</p>
                <div className="prompt-grid">
                  {prompts.map(({ icon: Icon, text, question: value }) => (
                    <button key={text} onClick={() => { setQuestion(value); input.current?.focus(); }}>
                      <Icon size={19} strokeWidth={1.5}/><span>{text}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : <ChatWindow messages={messages} busy={busy}/>}

          <div className="composer-wrap">
            {error && <div className="error-banner" role="alert">{error}</div>}
            {connectionError && <div className="error-banner" role="status">{connectionError}</div>}
            {health && !health.llm_configured && <div className="notice-banner">Add a Gemini API key in backend/.env to enable answers.</div>}
            <form className="composer" onSubmit={submit}>
              <textarea ref={input} aria-label="Your farming question" placeholder="What would you like to know?"
                value={question} maxLength={4000} disabled={busy} rows={2}
                onChange={event => setQuestion(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault(); submit();
                  }
                }}/>
              <div className="composer-bottom">
                <span>English, नेपाली, or Romanized Nepali</span>
                <button type="submit" aria-label="Send question" disabled={!question.trim() || busy}><ArrowUp size={21}/></button>
              </div>
            </form>
            <p className="composer-hint">Answers come from your sources. Check the cited guidance before acting.</p>
          </div>
        </section>

        <aside className="context-column">
          {empty && (
            <figure className="field-photo">
              <img src="/images/darap-farm.jpg" alt="Maize fields and a rural home beneath misty forested hills in Darap, Sikkim" width="1280" height="850" fetchPriority="high"/>
              <figcaption>
                <span><MapPin size={14}/> Darap, West Sikkim</span>
              </figcaption>
            </figure>
          )}
          <section className="source-summary">
            <h2><BookOpen size={19}/> Your source library</h2>
            <p>Add farming manuals, advisories, and guides. Your answers are based on what's in this library.</p>
            <div className="source-counts">
              <span><strong>{stats.document_count}</strong> documents</span>
              <span><strong>{stats.chunk_count}</strong> indexed passages</span>
            </div>
            <a className="button outline" href="#knowledge">Manage documents</a>
          </section>
          <p className="local-note"><Leaf size={18}/><span>Local questions. Organic practices.<br/>A little help for the next growing season.</span></p>
        </aside>
      </div>
    </div>
  );
}
