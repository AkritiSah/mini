import re
from uuid import uuid4


def chunk_sections(sections, document, config):
    target, overlap, maximum = (config[k] for k in ('target_words', 'overlap_words', 'max_words'))
    if not 0 <= overlap < target <= maximum:
        raise ValueError('Require overlap_words < target_words <= max_words.')
    chunks = []
    for section in sections:
        # Paragraphs and sentence boundaries are preferred; long units are bounded by max_words.
        units = []
        for paragraph in re.split(r'\n\s*\n', section.text):
            if ' | ' in paragraph or '; ' in paragraph:
                units.append(paragraph.strip())
            else:
                units.extend(re.split(r'(?<=[.!?।])\s+', paragraph))
        buffer = []
        count = 0
        fresh = False
        heading = section.section

        def emit():
            text = '\n'.join(buffer).strip()
            if text and fresh:
                chunks.append({
                    '_id': uuid4().hex, 'document_id': document['_id'],
                    'original_text': text, 'retrieval_text_en': text,
                    'page': section.page, 'section': heading,
                    **{key: document.get(key) for key in ('title', 'filename', 'source_organization',
                        'source_url', 'publication_date', 'crop', 'topic', 'district', 'organic_standard', 'verification_status')},
                })

        for unit in units:
            if re.match(r'^#{1,6}\s+', unit.strip()):
                emit()
                buffer, count, fresh = [], 0, False
                heading = unit.strip().lstrip('#').strip().splitlines()[0]
            words = unit.split()
            pieces = [unit] if len(words) <= maximum else [
                ' '.join(words[i:i + maximum]) for i in range(0, len(words), maximum)]
            for piece in pieces:
                length = len(piece.split())
                if buffer and count + length > maximum:
                    emit()
                    # Keep complete trailing sentences when they fit the overlap budget.
                    tail, tail_count = [], 0
                    for previous in reversed(buffer):
                        n = len(previous.split())
                        if tail_count + n > overlap:
                            break
                        tail.insert(0, previous)
                        tail_count += n
                    buffer, count = tail, tail_count
                    if count + length > maximum:
                        buffer, count = [], 0
                buffer.append(piece)
                count += length
                fresh = True
                if count >= target:
                    emit()
                    tail, tail_count = [], 0
                    for previous in reversed(buffer):
                        n = len(previous.split())
                        if tail_count + n > overlap:
                            break
                        tail.insert(0, previous)
                        tail_count += n
                    buffer, count, fresh = tail, tail_count, False
        emit()
    return chunks
