import logging
import os
import random
import sqlite3
import time

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.base import SQLiteCursorWrapper

logger = logging.getLogger(__name__)


def _is_lock_error(exc):
    message = str(exc).lower()
    return 'database is locked' in message or 'database table is locked' in message


class RetryingSQLiteCursorWrapper(SQLiteCursorWrapper):
    """Retry transient SQLite lock failures before surfacing an OperationalError."""

    max_attempts = int(os.environ.get('SQLITE_LOCK_RETRY_ATTEMPTS', '8'))
    base_delay = float(os.environ.get('SQLITE_LOCK_RETRY_BASE_DELAY', '0.05'))
    max_delay = float(os.environ.get('SQLITE_LOCK_RETRY_MAX_DELAY', '1.0'))

    def _execute_with_retry(self, operation, *args):
        attempt = 0
        while True:
            try:
                return operation(*args)
            except sqlite3.OperationalError as exc:
                attempt += 1
                if not _is_lock_error(exc) or attempt >= self.max_attempts:
                    raise

                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                delay += random.uniform(0, delay / 4)
                logger.warning(
                    'SQLite database lock encountered; retrying query in %.3fs (attempt %s/%s)',
                    delay,
                    attempt + 1,
                    self.max_attempts,
                )
                time.sleep(delay)

    def execute(self, query, params=None):
        return self._execute_with_retry(super().execute, query, params)

    def executemany(self, query, param_list):
        return self._execute_with_retry(super().executemany, query, param_list)


class DatabaseWrapper(SQLiteDatabaseWrapper):
    def create_cursor(self, name=None):
        return self.connection.cursor(factory=RetryingSQLiteCursorWrapper)

    def get_new_connection(self, conn_params):
        connection = super().get_new_connection(conn_params)
        self._configure_sqlite_connection(connection)
        return connection

    def _configure_sqlite_connection(self, connection):
        timeout_ms = int(float(self.settings_dict.get('OPTIONS', {}).get('timeout', 60)) * 1000)
        pragmas = [
            ('busy_timeout', timeout_ms),
            ('synchronous', 'NORMAL'),
            ('temp_store', 'MEMORY'),
            ('foreign_keys', 'ON'),
        ]

        database_name = str(self.settings_dict.get('NAME') or '')
        if database_name and database_name != ':memory:':
            pragmas.insert(0, ('journal_mode', 'WAL'))

        cursor = connection.cursor()
        try:
            for key, value in pragmas:
                cursor.execute(f'PRAGMA {key}={value}')
        finally:
            cursor.close()
