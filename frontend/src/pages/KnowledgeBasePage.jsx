import { useCallback, useEffect, useState } from 'react';
import { BookOpen, FileText, Layers3, RefreshCw } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import DocumentList from '../components/DocumentList';
import { api } from '../services/api';
export default function KnowledgeBasePage({ onStats }) {
  const [data, setData] = useState({ documents: [], document_count: 0, chunk_count: 0 });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try { const result = await api.documents(); setData(result); onStats(result); setError(''); }
    catch (failure) { setError(failure.message); }
    finally { setLoading(false); }
  }, [onStats]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!data.documents.some(document => ['queued', 'processing', 'deleting'].includes(document.status))) return;
    const timer = setTimeout(refresh, 3000);
    return () => clearTimeout(timer);
  }, [data.documents, refresh]);
  return <div className="page knowledge-page"><div className="page-heading"><div><h1>Knowledge Base</h1><p>The farming documents behind your answers.</p></div><button className="button quiet" onClick={refresh}><RefreshCw size={15}/> Refresh</button></div>
    <div className="stats-row"><div><span><FileText size={21}/></span><strong>{data.document_count}</strong><p>Uploaded documents</p></div><div><span><Layers3 size={21}/></span><strong>{data.chunk_count}</strong><p>Indexed passages</p></div><div><span><BookOpen size={21}/></span><strong>{data.documents.filter(d => d.status === 'indexed').length}</strong><p>Ready for questions</p></div></div>
    <FileUpload onChange={refresh}/>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <DocumentList documents={data.documents} loading={loading} onChange={refresh}/>
  </div>;
}
