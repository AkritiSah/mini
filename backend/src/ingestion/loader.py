from collections import Counter
import re
from .parsers import Section, parse


def load_sections(path, soffice_path=''):
    sections = parse(path, soffice_path)
    # Only recognizable page furniture is removable. Repeated advice stays verbatim.
    edges = Counter()
    furniture = re.compile(r'^(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?$|'
                           r'^(?:ICAR[-– ]*)?Indian Institute of Spices Research(?:,.*)?$|'
                           r'^Government of Sikkim$|^https?://\S+$|^www\.\S+$', re.I)
    if path.suffix.lower() == '.pdf':
        for section in sections:
            lines = [line.strip() for line in section.text.splitlines() if line.strip()]
            for line in set(lines[:1] + lines[-1:]):
                if len(line) < 90 and furniture.search(line):
                    edges[line] += 1
    repeated = {line for line, count in edges.items() if count >= max(3, len(sections) * .7)}
    cleaned = []
    for section in sections:
        lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in section.text.replace('\x00', '').splitlines()]
        text = '\n'.join(line for line in lines if line not in repeated)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if text:
            cleaned.append(Section(text, section.page, section.section))
    if not cleaned:
        raise ValueError('The document contains no readable text.')
    return cleaned
