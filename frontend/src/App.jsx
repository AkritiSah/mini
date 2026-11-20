import { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import ChatPage from './pages/ChatPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { api } from './services/api';

export default function App() {
  const [page, setPage] = useState(location.hash === '#knowledge' ? 'knowledge' : 'chat');
  const [health, setHealth] = useState(null);
  const [connectionError, setConnectionError] = useState('');
  const [stats, setStats] = useState({ document_count: 0, chunk_count: 0 });
  const [messages, setMessages] = useState([]);
  useEffect(() => {
    const change = () => setPage(location.hash === '#knowledge' ? 'knowledge' : 'chat');
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  useEffect(() => {
    let active = true;
    async function refresh() {
      let failure = '';
      try {
        const state = await api.health();
        if (!active) return;
        setHealth(state);
      } catch (error) {
        failure = error.message;
        if (active) setHealth(null);
      }
      try {
        const documents = await api.documents();
        if (active) setStats(documents);
      } catch (error) { failure ||= error.message; }
      if (active) setConnectionError(failure);
    }
    refresh();
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    return () => {
      active = false;
      window.removeEventListener('focus', refresh);
      window.removeEventListener('online', refresh);
    };
  }, []);
  return <div className="app-shell">
    <Navbar page={page} health={health} />
    <main className="main-area">
      {page === 'chat'
        ? <ChatPage health={health} connectionError={connectionError} stats={stats} messages={messages} setMessages={setMessages}/>
        : <KnowledgeBasePage onStats={setStats}/>}
      <footer className="page-footer"><span>For the people who grow in Sikkim.</span><span>English / नेपाली / Romanized Nepali</span></footer>
    </main>
  </div>;
}
