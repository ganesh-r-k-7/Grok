"""Test-specific SQLite dialect that supports PostgreSQL types."""
from sqlalchemy.dialects.sqlite import base as sqlite_base
from sqlalchemy.dialects.sqlite import aiosqlite as sqlite_aiosqlite
from sqlalchemy.types import TypeEngine, BLOB, TEXT
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, BYTEA, ARRAY
from sqlalchemy.sql.compiler import GenericTypeCompiler
import uuid
import json


class SQLiteUUID(TypeEngine):
    """UUID type that works with SQLite by storing as TEXT."""
    __visit_name__ = "UUID"
    cache_ok = True
    
    def get_col_spec(self, **kw):
        return "TEXT"
    
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(value)
        return process
    
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(value)
        return process


class SQLiteBYTEA(TypeEngine):
    """BYTEA type that works with SQLite by storing as BLOB."""
    __visit_name__ = "BYTEA"
    cache_ok = True
    
    def get_col_spec(self, **kw):
        return "BLOB"
    
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode()
            return str(value).encode()
        return process
    
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode()
            return bytes(value)
        return process


class SQLiteARRAY(TypeEngine):
    """ARRAY type that works with SQLite by storing as TEXT (JSON)."""
    __visit_name__ = "ARRAY"
    cache_ok = True
    
    def __init__(self, item_type, **kw):
        super().__init__(**kw)
        self.item_type = item_type
    
    def get_col_spec(self, **kw):
        return "TEXT"
    
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return json.dumps(value)
        return process
    
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                return json.loads(value)
            return value
        return process


class CustomSQLiteTypeCompiler(GenericTypeCompiler):
    """Custom type compiler for SQLite that handles PostgreSQL types."""
    
    def visit_UUID(self, type_, **kw):
        return "TEXT"
    
    def visit_BYTEA(self, type_, **kw):
        return "BLOB"
    
    def visit_ARRAY(self, type_, **kw):
        return "TEXT"


class CustomSQLiteDialect(sqlite_base.SQLiteDialect):
    """Custom SQLite dialect with PostgreSQL type support."""
    
    colspecs = {
        PG_UUID: SQLiteUUID,
        BYTEA: SQLiteBYTEA,
        ARRAY: SQLiteARRAY,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type_compiler_instance = CustomSQLiteTypeCompiler(self)


class CustomAsyncSQLiteDialect(sqlite_aiosqlite.SQLiteDialect_aiosqlite, CustomSQLiteDialect):
    """Custom async SQLite dialect with PostgreSQL type support."""
    pass


# Register the dialect
from sqlalchemy.dialects import registry
registry.register("sqlite.custom", "tests.test_dialect", "CustomAsyncSQLiteDialect")