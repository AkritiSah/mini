import { BookOpen, MessageCircle, Sprout } from 'lucide-react';

export default function Navbar({ page, health }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand" href="#chat" aria-label="Krishi Mitra home">
          <span className="brand-mark"><Sprout size={28} strokeWidth={1.5}/></span>
          <span>Krishi Mitra<small>A growing companion for Sikkim</small></span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#chat" className={page === 'chat' ? 'active' : ''} aria-current={page === 'chat' ? 'page' : undefined}>
            <MessageCircle size={18}/> Farming assistant
          </a>
          <a href="#knowledge" className={page === 'knowledge' ? 'active' : ''} aria-current={page === 'knowledge' ? 'page' : undefined}>
            <BookOpen size={18}/> Knowledge Base
          </a>
        </nav>
        <span className="connection-status" role="status">
          <span className={`status-dot ${health ? 'online' : ''}`}/>
          {health ? 'Connected' : 'Unavailable'}
        </span>
      </div>
    </header>
  );
}
