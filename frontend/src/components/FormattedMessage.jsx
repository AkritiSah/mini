import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const components = {
  a({ href, children, title }) {
    if (!href) return <span>{children}</span>;
    const external = /^(https?:)?\/\//i.test(href);
    return <a href={href} title={title} target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}>{children}</a>;
  },
  table({ children }) {
    return <div className="message-table"><table>{children}</table></div>;
  },
  img({ src, alt, title }) {
    return src ? <img src={src} alt={alt || ''} title={title} loading="lazy" referrerPolicy="no-referrer"/> : null;
  },
};

export default function FormattedMessage({ content }) {
  return <div className="message-text message-markup">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
      {content}
    </ReactMarkdown>
  </div>;
}
