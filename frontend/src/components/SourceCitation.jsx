import { useEffect, useState } from 'react';
import { BookOpen, ExternalLink, X } from 'lucide-react';
import { api, fileUrl, safeUrl } from '../services/api';
export default function SourceCitation({ citation }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    const escape = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [open]);
  async function inspect() {
    setOpen(true); setError('');
    try { setSource(await api.source(citation.chunk_id)); }
    catch (failure) { setError(failure.message); }
  }
  return <><button className="citation" onClick={inspect}><span>[{citation.id}]</span><BookOpen size={14}/><span>{citation.title || citation.filename}{citation.page ? ` · p. ${citation.page}` : ''}</span><ExternalLink size={12}/></button>
    {open && <div className="modal-backdrop" onClick={() => setOpen(false)}><section className="source-modal" role="dialog" aria-modal="true" aria-label="Source details" onClick={e => e.stopPropagation()}><button className="icon-button close-modal" aria-label="Close source details" onClick={() => setOpen(false)} autoFocus><X size={20}/></button><div className="eyebrow">SOURCE [{citation.id}]</div><h2>{citation.title || citation.filename}</h2>{error && <p className="error-banner">{error}</p>}{!source && !error && <p>Loading source details…</p>}{source && <><dl>{[['File', source.filename], ['Organization', source.source_organization], ['Published', source.publication_date], ['Page / section', source.page || source.section], ['Verification', source.verification_status]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Unknown'}</dd></div>)}</dl><blockquote>{source.original_text}</blockquote><div className="modal-actions"><a className="button primary" href={fileUrl(citation.document_id)}>Download original <ExternalLink size={14}/></a>{safeUrl(source.source_url) && <a className="button outline" href={safeUrl(source.source_url)} target="_blank" rel="noreferrer">Source website <ExternalLink size={14}/></a>}</div></>}</section></div>}
  </>;
}
