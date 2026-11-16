import { Sprout, UserRound } from 'lucide-react';
import SourceCitation from './SourceCitation';
const languages = { en: 'English', ne: 'नेपाली', 'ne-Latn': 'Romanized Nepali' };
export default function MessageBubble({ message }) {
  const assistant = message.role === 'assistant';
  return <article className={`message ${assistant ? 'assistant' : 'user'}`}><div className="message-avatar">{assistant ? <Sprout size={19}/> : <UserRound size={18}/>}</div><div className="message-body"><div className="message-label">{assistant ? 'Krishi Mitra' : 'You'}{assistant && <small>{languages[message.detected_language] || message.detected_language}</small>}</div><div className="message-text">{message.content}</div>
    {assistant && message.citations?.length > 0 && <div className="citations"><div className="sources-label">SOURCE DOCUMENTS</div>{message.citations.map(citation => <SourceCitation key={citation.id} citation={citation}/>)}</div>}
    {assistant && message.evidence_status === 'insufficient' && <span className="evidence-label">More source material needed</span>}
    {assistant && message.metadata?.provider && <div className="generation-label">{message.metadata.provider === 'gemini' ? 'Gemini fallback' : 'Claude'} · {message.metadata.model}</div>}
    {message.failed && <small className="failed-label">Request failed. Your question is ready to retry below.</small>}
  </div></article>;
}
