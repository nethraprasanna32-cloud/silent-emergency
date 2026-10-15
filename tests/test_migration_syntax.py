from pathlib import Path
from pglast import parse_sql

def test_all_migrations_parse_as_postgresql_sql():
    files=sorted(Path('db/migrations').glob('*.sql'))
    assert files
    for path in files:
        parse_sql(path.read_text(encoding='utf-8'))
