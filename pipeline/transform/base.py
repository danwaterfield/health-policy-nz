import duckdb


class BaseTransformer:
    source_key: str

    def transform(self, *args, **kwargs):
        """Read raw_path, write to DuckDB. Must be idempotent."""
        raise NotImplementedError

    def log(self, msg):
        print(f"[{self.__class__.__name__}] {msg}")
