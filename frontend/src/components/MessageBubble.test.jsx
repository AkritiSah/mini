import { render, screen } from '@testing-library/react';
import { test, expect } from 'vitest';
import MessageBubble from './MessageBubble';

test('assistant answers render rich HTML and keep source citations', () => {
  const content = `## Large cardamom disease

* **Climate Change:** Rising temperatures [1].
* **Specific Pathogens:**
  * *Colletotrichum* causes blight [2].

See the [source guide](https://example.org/guide).

| Disease | Type |
| --- | --- |
| Chirkey | Viral |

> Use source-backed advice.

Use \`compost\` and ~~avoid this~~.

1. Inspect plants.
2. Record symptoms.`;
  const { container } = render(<MessageBubble message={{ role: 'assistant', content,
    citations: [{ id: 1, title: 'Cardamom guide', document_id: 'doc', chunk_id: 'chunk' }] }}/>);
  expect(screen.getByRole('heading', { name: 'Large cardamom disease' })).toBeInTheDocument();
  expect(container.querySelector('strong')).toHaveTextContent('Climate Change:');
  expect(container.querySelector('em')).toHaveTextContent('Colletotrichum');
  expect(container.querySelector('ul ul li')).toHaveTextContent('Colletotrichum causes blight [2].');
  expect(screen.getByRole('link', { name: 'source guide' })).toHaveAttribute('href', 'https://example.org/guide');
  expect(screen.getByRole('link', { name: 'source guide' })).toHaveAttribute('rel', 'noopener noreferrer');
  expect(screen.getByRole('table')).toHaveTextContent('Chirkey');
  expect(container.querySelector('blockquote')).toHaveTextContent('Use source-backed advice.');
  expect(container.querySelector('code')).toHaveTextContent('compost');
  expect(container.querySelector('del')).toHaveTextContent('avoid this');
  expect(container.querySelectorAll('ol li')).toHaveLength(2);
  expect(screen.getByRole('button', { name: /Cardamom guide/ })).toBeInTheDocument();
  expect(container.querySelector('.message-text')).not.toHaveTextContent('**Climate Change:**');
});

test('raw HTML and unsafe Markdown links cannot inject active content', () => {
  const content = `<script>alert('xss')</script>

<img src="x" onerror="alert('xss')">

[unsafe](javascript:alert%281%29)

[safe](https://example.org)

![unsafe image](javascript:alert%281%29)`;
  const { container } = render(<MessageBubble message={{ role: 'assistant', content }}/>);
  expect(container.querySelector('script, iframe, img, [onerror]')).toBeNull();
  expect(screen.queryByRole('link', { name: 'unsafe' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'safe' })).toHaveAttribute('href', 'https://example.org');
});

test('user questions remain literal text', () => {
  const { container } = render(<MessageBubble message={{ role: 'user', content: '**literal** <b>question</b>' }}/>);
  expect(container.querySelector('.message-text')).toHaveTextContent('**literal** <b>question</b>');
  expect(container.querySelector('strong, b')).toBeNull();
});
