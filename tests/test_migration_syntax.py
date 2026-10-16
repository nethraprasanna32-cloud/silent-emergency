from pathlib import Path
import ast
from pglast import parse_sql

def test_all_migrations_parse_as_postgresql_sql():
    files=sorted(Path('db/migrations').glob('*.sql'))
    assert files
    for path in files:
        parse_sql(path.read_text(encoding='utf-8'))

def test_multiline_fastapi_queries_parse_as_sql():
    tree=ast.parse(Path('app/main.py').read_text(encoding='utf-8'))
    queries=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='execute' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
            query=node.args[0].value
            if '\n' in query and any(word in query.upper() for word in ('SELECT','INSERT','UPDATE','DELETE')):
                queries.append(query)
    assert queries
    for query in queries:
        parse_sql(query.replace('%s','NULL'))
