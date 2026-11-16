import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, beforeEach, test, expect } from 'vitest';
import ChatPage from '../pages/ChatPage';
import FileUpload from './FileUpload';
import { api, safeUrl } from '../services/api';
vi.mock('../services/api', async importOriginal => ({ ...await importOriginal(), api: { chat: vi.fn(), upload: vi.fn(), job: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());

test('submits the actual question and displays backend failure', async () => {
  api.chat.mockRejectedValue(new Error('MongoDB unavailable'));
  const setMessages = vi.fn();
  render(<ChatPage health={{llm_configured:true}} stats={{document_count:0,chunk_count:0}} messages={[]} setMessages={setMessages}/>);
  fireEvent.change(screen.getByLabelText('Your farming question'), {target:{value:'How to make compost?'}});
  fireEvent.click(screen.getByLabelText('Send question'));
  await waitFor(() => expect(api.chat).toHaveBeenCalledWith({question:'How to make compost?',history:[]}));
  expect(await screen.findByRole('alert')).toHaveTextContent('MongoDB unavailable');
  expect(screen.getByLabelText('Your farming question')).toHaveValue('How to make compost?');
});

test('upload submits multipart content and optional source metadata', async () => {
  api.upload.mockRejectedValue(new Error('Duplicate document'));
  render(<FileUpload onChange={vi.fn()}/>);
  const file = new File(['Organic ginger guide'], 'GUIDE.PDF', {type:'application/pdf'});
  fireEvent.change(screen.getByLabelText('Select source document'), {target:{files:[file]}});
  fireEvent.click(screen.getByRole('button', {name:/Upload & index/}));
  await waitFor(() => expect(api.upload).toHaveBeenCalled());
  expect(api.upload.mock.calls[0][0].get('file')).toBe(file);
  expect(await screen.findByRole('alert')).toHaveTextContent('Duplicate document');
});

test('unsafe citation URLs cannot be opened', () => {
  expect(safeUrl('javascript:alert(1)')).toBeNull();
  expect(safeUrl('https://example.org/guide')).toBe('https://example.org/guide');
});
