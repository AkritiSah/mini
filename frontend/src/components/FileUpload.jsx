import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CloudUpload, FileText, Info, LoaderCircle, Plus, X } from 'lucide-react';
import { api } from '../services/api';
export const ACCEPT = '.pdf,.txt,.md,.html,.htm,.csv,.json,.jsonl,.xml,.xls,.xlsx,.doc,.docx,.ppt,.pptx,.epub';
export default function FileUpload({ onChange }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const picker = useRef();
  const form = useRef();
  const callback = useRef(onChange);
  callback.current = onChange;
  useEffect(() => {
    if (!job?.id || ['completed', 'failed'].includes(job.status)) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const state = await api.job(job.id);
        if (!active) return;
        setJob(state);
        if (state.status === 'completed' || state.status === 'failed') {
          setBusy(false); setSuccess(state.status === 'completed');
          if (state.error) setError(state.error);
          if (state.status === 'completed') { setFile(null); form.current?.reset(); }
          callback.current();
        }
      } catch (failure) { if (active) setError(failure.message); }
    }, 1500);
    return () => { active = false; clearInterval(timer); };
  }, [job?.id, job?.status]);
  function choose(selected) {
    if (busy) return;
    setSuccess(false); setError(''); setJob(null);
    if (selected && !ACCEPT.split(',').includes('.' + selected.name.split('.').pop().toLowerCase())) {
      setFile(null); setError('This file format is not supported.'); return;
    }
    setFile(selected);
  }
  async function upload(event) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setSuccess(false);
    const body = new FormData(event.currentTarget); body.set('file', file);
    try { const result = await api.upload(body); setJob({ id: result.job_id, status: 'queued', progress: 0 }); onChange(); }
    catch (failure) { setError(failure.message); setBusy(false); }
  }
  return <section className="upload-card"><div className="section-title"><div><h2>Add a farming document</h2><p>Bring in a manual, advisory, or guide you trust.</p></div></div>
    <form ref={form} onSubmit={upload}><div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]); }}>
      <input ref={picker} type="file" aria-label="Select source document" accept={ACCEPT} disabled={busy} onChange={e => choose(e.target.files[0])} hidden/>
      <div className="upload-icon"><CloudUpload size={29} strokeWidth={1.5}/></div><h3>{file ? file.name : 'Choose a document for your library'}</h3><p>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to upload` : 'Drop a file here, or browse your computer.'}</p>
      <button type="button" className="button outline" disabled={busy} onClick={() => picker.current.click()}><Plus size={16}/>{file ? 'Choose another file' : 'Choose a document'}</button><small>PDF, Word, Excel, PowerPoint, EPUB, text, HTML, CSV, JSON & XML</small>
    </div>
    <details className="source-fields"><summary>Source details <span>Optional, but helpful for reliable citations</span></summary><div className="form-grid">{[['title', 'Document title', 'e.g. Organic ginger cultivation guide'], ['source_organization', 'Source organization', 'e.g. ICAR'], ['source_url', 'Original source URL', 'https://…'], ['publication_date', 'Publication date', ''], ['crop', 'Crop', 'Only if stated by the source'], ['topic', 'Farming topic', 'e.g. Composting'], ['district', 'District applicability', 'Only if explicitly stated'], ['organic_standard', 'Organic standard', 'Only if explicitly stated']].map(([name, label, placeholder]) => <label key={name}>{label}<input name={name} type={name === 'publication_date' ? 'date' : name === 'source_url' ? 'url' : 'text'} placeholder={placeholder} maxLength={name === 'source_url' ? 2000 : name === 'title' ? 300 : 100} disabled={busy}/></label>)}</div></details>
    {job && <div className="job-status" role="status"><span>{job.status === 'completed' ? <CheckCircle2 size={16}/> : <LoaderCircle size={16} className={busy ? 'spin' : ''}/>} {job.status} · {job.progress}%</span><progress value={job.progress} max={100}/></div>}
    {error && <div className="error-banner" role="alert">{error}</div>}{success && <div className="success-banner" role="status">Document indexed. Its passages are now available to the farming assistant.</div>}
    <div className="upload-bottom"><span><Info size={15}/> Your original files stay in your local library.</span><button className="button primary" type="submit" disabled={!file || busy}>{busy ? <LoaderCircle size={16} className="spin"/> : <CloudUpload size={16}/>} {busy ? 'Processing document…' : 'Upload & index'}</button></div></form>
  </section>;
}
