import { Sprout, MessagesSquare, BookOpen, ArrowUpRight, ShieldCheck } from 'lucide-react';
export default function Navbar({ page, health }) {
  return <aside className="sidebar">
    <a className="brand" href="#chat"><div className="brand-mark"><Sprout size={27}/></div><div>Krishi Mitra<small>GROW WITH KNOWLEDGE</small></div></a>
    <div className="workspace-label">YOUR WORKSPACE</div>
    <nav aria-label="Main navigation">
      <a href="#chat" className={page === 'chat' ? 'active' : ''}><MessagesSquare size={19}/> Farming assistant <span>↗</span></a>
      <a href="#knowledge" className={page === 'knowledge' ? 'active' : ''}><BookOpen size={19}/> Knowledge Base</a>
    </nav>
    <div className="sidebar-note"><div className="note-icon"><Sprout size={26}/></div><h3>Healthy soil.<br/>Thoughtful farming.</h3><p>Find practical guidance, grounded in the documents you trust.</p><a href="#knowledge">Build your knowledge base <ArrowUpRight size={16}/></a></div>
    <div className="sidebar-bottom"><ShieldCheck size={18}/><div>Local workspace<small><span className={`status-dot ${health ? 'online' : ''}`}/>{health ? 'Backend connected' : 'Backend unavailable'}</small></div></div>
  </aside>;
}
