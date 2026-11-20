import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { api } from './services/api';

vi.mock('./services/api', async importOriginal => ({
  ...await importOriginal(), api: { health: vi.fn(), documents: vi.fn() },
}));
const emptyLibrary = { documents: [], document_count: 0, chunk_count: 0 };

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  location.hash = '';
  api.health.mockResolvedValue({ status: 'ready', llm_configured: true });
  api.documents.mockResolvedValue(emptyLibrary);
});
afterEach(() => vi.useRealTimers());

test('idle chat does not poll health or documents and refreshes on reconnection', async () => {
  render(<App/>);
  await act(async () => {});
  expect(api.health).toHaveBeenCalledTimes(1);
  expect(api.documents).toHaveBeenCalledTimes(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
  expect(api.health).toHaveBeenCalledTimes(1);
  expect(api.documents).toHaveBeenCalledTimes(1);
  await act(async () => { window.dispatchEvent(new Event('online')); });
  expect(api.health).toHaveBeenCalledTimes(2);
});

test('idle library refreshes only on demand', async () => {
  render(<KnowledgeBasePage onStats={vi.fn()}/>);
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
  expect(api.documents).toHaveBeenCalledTimes(1);
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Refresh' })); });
  expect(api.documents).toHaveBeenCalledTimes(2);
});

test('library polling stops once active indexing finishes', async () => {
  const document = { id: 'doc', title: 'Guide', filename: 'guide.txt', uploaded_at: '2026-11-17', chunk_count: 1 };
  api.documents.mockResolvedValueOnce({ documents: [{ ...document, status: 'processing' }], document_count: 1, chunk_count: 0 })
    .mockResolvedValue({ documents: [{ ...document, status: 'indexed' }], document_count: 1, chunk_count: 1 });
  render(<KnowledgeBasePage onStats={vi.fn()}/>);
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(api.documents).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
  expect(api.documents).toHaveBeenCalledTimes(2);
});

test('library keeps polling after a temporary fetch failure', async () => {
  const document = { id: 'doc', title: 'Guide', filename: 'guide.txt', uploaded_at: '2026-11-17' };
  api.documents.mockResolvedValueOnce({ documents: [{ ...document, status: 'processing' }], document_count: 1, chunk_count: 0 })
    .mockRejectedValueOnce(new Error('Temporary connection failure'))
    .mockResolvedValue({ documents: [{ ...document, status: 'indexed' }], document_count: 1, chunk_count: 1 });
  render(<KnowledgeBasePage onStats={vi.fn()}/>);
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(screen.getByRole('alert')).toHaveTextContent('Temporary connection failure');
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(api.documents).toHaveBeenCalledTimes(3);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByText('indexed')).toBeInTheDocument();
});

test('source library is fetched even when search health is degraded', async () => {
  api.health.mockRejectedValue(new Error('Search index is unavailable'));
  render(<App/>);
  await act(async () => {});
  expect(api.documents).toHaveBeenCalledTimes(1);
});
