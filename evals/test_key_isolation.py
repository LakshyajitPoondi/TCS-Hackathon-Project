from pathlib import Path
import re
def test_key_isolation():
    root=Path(__file__).resolve().parents[1];bad=[]
    for folder in ('backend','engine','frontend/src'):
        for path in (root/folder).rglob('*'):
            if path.suffix in ('.py','.ts','.tsx','.js') and re.search(r'\b(?:docs_)?answer_key\b|evals[/\\][^\s\x27\x22<>]*key\.json',path.read_text(encoding='utf-8')):bad.append(str(path))
    assert not bad,'Evaluation key reference outside evals: '+str(bad)
