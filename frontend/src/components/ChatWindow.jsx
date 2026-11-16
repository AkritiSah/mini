import { useEffect, useRef } from 'react';
import { Sprout } from 'lucide-react';
import MessageBubble from './MessageBubble';
export default function ChatWindow({ messages, busy }) {
  const bottom = useRef();
  useEffect(() => { bottom.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' }); }, [messages, busy]);
  return <div className="chat-window" role="log" aria-live="polite">{messages.map((message, index) => <MessageBubble key={index} message={message}/>)}{busy && <div className="thinking"><Sprout size={18}/><span>Finding guidance in your sources<span className="loading-dots">…</span></span></div>}<div ref={bottom}/></div>;
}
