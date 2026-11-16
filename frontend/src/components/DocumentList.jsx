import { useState } from 'react';
import { BookOpen, Download, FileText, LoaderCircle, RefreshCw, Trash2 } from 'lucide-react';
import { api, fileUrl } from '../services/api';
export default function DocumentList({ documents, loading, onChange }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState('');
  async function action(id, kind) {
    setBusy(id); setError('');
    try { await (kind === 'delete' ? api.remove(id) : api.reindex(id)); setDeleting(''); await onChange(); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(''); }
  }
  return <section className="documents-card"><div className="section-title"><div><h2>Your source library <span className="count-pill">{documents.length}</span></h2><p>Manage the documents behind your assistant's answers.</p></div></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="empty-library"><LoaderCircle className="spin"/><p>Loading your source library…</p></div> : !documents.length ? <div className="empty-library"><div><BookOpen size={29} strokeWidth={1.4}/></div><h3>A place for knowledge to take root.</h3><p>Add your first document above to start building your farming library.</p></div> : <div className="document-table-wrap"><table className="document-table"><thead><tr><th>DOCUMENT</th><th>STATUS</th><th>PASSAGES</th><th>ADDED</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{documents.map(document => <tr key={document.id}><td><div className="document-name"><FileText size={21}/><div><b>{document.title}</b><small>{document.source_organization || 'Source organization unknown'} · {document.filename}</small>{document.error && <span className="document-error">{document.error}</span>}</div></div></td><td><span className={`document-status ${document.status}`}><span/>{document.status}</span></td><td>{document.chunk_count || '—'}</td><td>{new Date(document.uploaded_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</td><td><div className="document-actions"><a className="icon-button" href={fileUrl(document.id)} aria-label={`Download ${document.title}`}><Download size={16}/></a><button className="icon-button" aria-label={`Reindex ${document.title}`} disabled={busy === document.id || ['queued', 'processing', 'deleting'].includes(document.status)} onClick={() => action(document.id, 'reindex')}><RefreshCw size={16} className={busy === document.id ? 'spin' : ''}/></button><button className="icon-button danger" aria-label={`Delete ${document.title}`} disabled={!!busy} onClick={() => setDeleting(document.id)}><Trash2 size={16}/></button></div>{deleting === document.id && <div className="delete-confirm"><p>Delete this document and its indexed passages?</p><button className="button danger" onClick={() => action(document.id, 'delete')} disabled={!!busy}>Delete</button><button className="button quiet" onClick={() => setDeleting('')}>Cancel</button></div>}</td></tr>)}</tbody></table></div>}
  </section>;
}
