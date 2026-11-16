import { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import ChatPage from './pages/ChatPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { api } from './services/api';
import { MapPin, Leaf } from 'lucide-react';

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
      try {
        const state = await api.health();
        if (active) { setHealth(state); setConnectionError(''); }
        const documents = await api.documents();
        if (active) setStats(documents);
      } catch (error) { if (active) { setConnectionError(error.message); setHealth(null); } }
    }
    refresh(); const interval = setInterval(refresh, 10000);
    return () => { active = false; clearInterval(interval); };
  }, []);
  return <div className="app-shell">
    <Navbar page={page} health={health} />
    <main className="main-area">
      <header className="topbar"><span><Leaf size={15}/> A little closer to nature.</span><span><MapPin size={14}/> Sikkim, India <i/> Local research prototype</span></header>
      {page === 'chat'
        ? <ChatPage health={health} connectionError={connectionError} stats={stats} messages={messages} setMessages={setMessages}/>
        : <KnowledgeBasePage onStats={setStats}/>}
      <footer className="page-footer"><span>Rooted in evidence. Growing together.</span><span>Krishi Mitra <span className="footer-dot">•</span> Organic farming, informed.</span></footer>
    </main>
  </div>;
}
