from dataclasses import dataclass
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from bs4 import BeautifulSoup
from defusedxml import ElementTree


@dataclass
class Section:
    text: str
    page: int | None = None
    section: str | None = None


def read_text(path):
    data = Path(path).read_bytes()
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Save text files as UTF-8 or UTF-16 before uploading.') from error


def table_text(rows):
    rows = [[str(value) if value is not None else '' for value in row] for row in rows]
    if not rows:
        return ''
    heading = rows[0]
    return '\n'.join([' | '.join(heading)] + [
        '; '.join(f'{heading[i] if i < len(heading) else i + 1}: {value}'
                  for i, value in enumerate(row)) for row in rows[1:]])


def html_text(content):
    soup = BeautifulSoup(content, 'html.parser')
    for element in soup(['script', 'style', 'iframe', 'object', 'noscript']):
        element.decompose()
    for table in soup.find_all('table'):
        rows = [[cell.get_text(' ', strip=True) for cell in row.find_all(['th', 'td'])]
                for row in table.find_all('tr')]
        table.replace_with('\n' + table_text(rows) + '\n')
    return soup.get_text('\n', strip=True)


def parse(path: Path, soffice_path='') -> list[Section]:
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        import pymupdf
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise ValueError('Password-protected PDFs are not supported.')
            sections = []
            for i, page in enumerate(document):
                text = page.get_text(sort=True)
                tables = page.find_tables().tables
                for table in tables:
                    text += '\n\n' + table_text(table.extract())
                sections.append(Section(text, i + 1))
            if not any(len(s.text.strip()) > 20 for s in sections):
                raise ValueError('This PDF has no usable text. OCR is required before upload.')
            return sections
    if suffix in {'.txt', '.md'}:
        return [Section(read_text(path))]
    if suffix in {'.html', '.htm'}:
        return [Section(html_text(read_text(path)))]
    if suffix == '.csv':
        return [Section(table_text(list(csv.reader(io.StringIO(read_text(path))))))]
    if suffix in {'.json', '.jsonl'}:
        text = read_text(path)
        records = json.loads(text) if suffix == '.json' else [json.loads(line) for line in text.splitlines() if line.strip()]
        records = records if isinstance(records, list) else [records]
        return [Section(json.dumps(item, ensure_ascii=False, indent=2), section=f'Record {i + 1}')
                for i, item in enumerate(records)]
    if suffix == '.xml':
        root = ElementTree.fromstring(read_text(path))
        return [Section('\n'.join(f'{node.tag}: {node.text.strip()}' for node in root.iter()
                                  if node.text and node.text.strip()))]
    if suffix == '.xlsx':
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            return [Section(table_text(list(sheet.values)), section=sheet.title) for sheet in workbook]
        finally:
            workbook.close()
    if suffix == '.xls':
        import xlrd
        book = xlrd.open_workbook(path)
        return [Section(table_text([sheet.row_values(i) for i in range(sheet.nrows)]), section=sheet.name)
                for sheet in book.sheets()]
    if suffix == '.docx':
        from docx import Document
        document = Document(path)
        # Preserve paragraph/table order rather than separating tables from their headings.
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        blocks = []
        for element in document.element.body:
            if element.tag.endswith('}p'):
                blocks.append(Paragraph(element, document).text)
            elif element.tag.endswith('}tbl'):
                blocks.append(table_text([[cell.text for cell in row.cells]
                                         for row in Table(element, document).rows]))
        return [Section('\n\n'.join(blocks))]
    if suffix == '.pptx':
        from pptx import Presentation
        result = []
        for i, slide in enumerate(Presentation(path).slides):
            blocks = []
            for shape in slide.shapes:
                if shape.has_table:
                    blocks.append(table_text([[cell.text for cell in row.cells] for row in shape.table.rows]))
                elif shape.has_text_frame:
                    blocks.append(shape.text)
            result.append(Section('\n'.join(blocks), i + 1, f'Slide {i + 1}'))
        return result
    if suffix == '.epub':
        import ebooklib
        from ebooklib import epub
        book = epub.read_epub(str(path), options={'ignore_ncx': True})
        return [Section(html_text(item.get_content()), section=item.get_name())
                for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
    if suffix in {'.doc', '.ppt'}:
        executable = soffice_path or shutil.which('soffice')
        if not executable:
            raise ValueError('Legacy DOC/PPT requires LibreOffice. Install it and set SOFFICE_PATH.')
        with tempfile.TemporaryDirectory() as directory:
            target = 'docx' if suffix == '.doc' else 'pptx'
            # A fresh profile disables macros and avoids reusing an interactive Office session.
            profile = Path(directory, 'profile')
            user_profile = profile / 'user'
            user_profile.mkdir(parents=True)
            (user_profile / 'registrymodifications.xcu').write_text(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
                '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
                '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
                '</item></oor:items>', encoding='utf-8')
            subprocess.run([str(executable), f'-env:UserInstallation={profile.as_uri()}',
                            '--headless', '--convert-to', target, '--outdir', directory, str(path)],
                           check=True, capture_output=True, timeout=60)
            converted = Path(directory, path.stem + '.' + target)
            if not converted.exists():
                raise ValueError('LibreOffice could not convert this document.')
            return parse(converted)
    raise ValueError('No parser is available for this format.')
