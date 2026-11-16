from pathlib import Path
import zipfile

SUPPORTED = {'.pdf', '.txt', '.md', '.html', '.htm', '.csv', '.json', '.jsonl',
             '.xml', '.xls', '.xlsx', '.doc', '.docx', '.ppt', '.pptx', '.epub'}
ZIP_TYPES = {'.xlsx': 'xl/', '.docx': 'word/', '.pptx': 'ppt/', '.epub': 'META-INF/'}


def validate_filename(filename: str):
    if not filename or '/' in filename or '\\' in filename or '\x00' in filename:
        raise ValueError('Provide a filename without directory components.')
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED:
        raise ValueError('Unsupported file format.')
    return extension


def validate_file(path: Path, extension: str, max_bytes: int):
    size = path.stat().st_size
    if not 0 < size <= max_bytes:
        raise ValueError('File is empty or exceeds the configured upload size limit.')
    with path.open('rb') as stream:
        prefix = stream.read(1024)
    if extension == '.pdf' and not prefix.startswith(b'%PDF-'):
        raise ValueError('File content is not a PDF.')
    if extension in {'.doc', '.ppt', '.xls'} and not prefix.startswith(bytes.fromhex('D0CF11E0A1B11AE1')):
        raise ValueError('Expected a legacy Office compound document.')
    if extension in ZIP_TYPES:
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > 10000 or sum(x.file_size for x in entries) > 150_000_000:
                    raise ValueError('Archive has too much expanded content.')
                if any(x.file_size > max(x.compress_size, 1) * 200 for x in entries):
                    raise ValueError('Unsafe archive compression ratio.')
                names = [x.filename for x in entries]
                if not any(name.startswith(ZIP_TYPES[extension]) for name in names):
                    raise ValueError('File content does not match its extension.')
                if any('vbaproject' in name.lower() or '..' in Path(name).parts for name in names):
                    raise ValueError('Macro content or unsafe archive paths are not accepted.')
        except zipfile.BadZipFile as error:
            raise ValueError('Malformed Office/EPUB archive.') from error
    elif extension not in {'.pdf', '.doc', '.ppt', '.xls'}:
        if b'\x00' in prefix and not prefix.startswith((b'\xff\xfe', b'\xfe\xff')):
            raise ValueError('Expected a text document, but binary content was detected.')
