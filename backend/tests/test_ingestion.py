import zipfile
import pytest
from src.ingestion.parsers import parse
from src.ingestion.file_validator import validate_filename, validate_file


@pytest.mark.parametrize('extension,content,expected', [
    ('.txt', 'Organic ginger', 'Organic ginger'), ('.md', '# Compost', 'Compost'),
    ('.html', '<script>bad()</script><h1>Ginger</h1>', 'Ginger'),
    ('.csv', 'Crop,Rate\nGinger,5 kg', 'Crop: Ginger'),
    ('.json', '{"crop":"ginger"}', 'ginger'),
    ('.jsonl', '{"crop":"ginger"}\n{"crop":"rice"}', 'ginger'),
    ('.xml', '<crops><crop>ginger</crop></crops>', 'ginger'),
])
def test_text_formats(tmp_path, extension, content, expected):
    path = tmp_path / ('fixture' + extension)
    path.write_text(content, encoding='utf-8')
    sections = parse(path)
    assert expected in sections[0].text and 'bad()' not in sections[0].text


def test_office_and_epub(tmp_path):
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
    from ebooklib import epub
    document = Document(); document.add_paragraph('Organic ginger guide'); document.save(tmp_path / 'a.docx')
    workbook = Workbook(); workbook.active.append(['Crop', 'Rate']); workbook.active.append(['Ginger', '5 kg']); workbook.save(tmp_path / 'a.xlsx')
    deck = Presentation(); slide = deck.slides.add_slide(deck.slide_layouts[1]); slide.shapes.title.text = 'Organic ginger'; deck.save(tmp_path / 'a.pptx')
    book = epub.EpubBook(); book.set_identifier('fixture'); book.set_title('Ginger fixture'); book.set_language('en')
    chapter = epub.EpubHtml(title='Ginger', file_name='ginger.xhtml', lang='en'); chapter.content = '<h1>Organic ginger</h1>'
    book.add_item(chapter); book.toc = (chapter,); book.spine = [chapter]; book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
    epub.write_epub(str(tmp_path / 'a.epub'), book)
    for extension in ('.docx', '.xlsx', '.pptx', '.epub'):
        path = tmp_path / ('a' + extension)
        validate_file(path, extension, 1_000_000)
        assert 'ginger' in '\n'.join(s.text for s in parse(path)).lower()


def test_unsafe_xml_and_macros_rejected(tmp_path):
    path = tmp_path / 'bad.xml'
    path.write_text('<!DOCTYPE x [<!ENTITY leak SYSTEM "file:///etc/passwd">]><x>&leak;</x>')
    with pytest.raises(Exception):
        parse(path)
    path = tmp_path / 'macro.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/vbaProject.bin', 'unsafe')
    with pytest.raises(ValueError, match='Macro'):
        validate_file(path, '.docx', 10000)
    assert validate_filename('GUIDE.PDF') == '.pdf'


def test_repeated_scientific_recommendations_are_preserved(tmp_path, monkeypatch):
    from src.ingestion import loader
    from src.ingestion.parsers import Section
    advice = 'Use compost for ginger cultivation.'
    monkeypatch.setattr(loader, 'parse', lambda *args: [Section(advice + '\nGinger guidance.\n1', i)
                                                      for i in range(4)])
    sections = loader.load_sections(tmp_path / 'guide.pdf')
    assert all(advice in section.text for section in sections)
    assert all(not section.text.endswith('\n1') for section in sections)
