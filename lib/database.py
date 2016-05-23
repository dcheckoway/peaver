import logging, psycopg2
import psycopg2.extras

from config import Config
from model import AttributeDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class DatabaseClient():
    def __init__(self, config = None):
        self.config = config if config else Config().load()
        self.conn = None
        self.c = None

    def connect(self):
        if not self.conn:
            host = self.config.get('database', 'host')
            user = self.config.get('database', 'user')
            password = self.config.get('database', 'password')
            name = self.config.get('database', 'name')
            logger.info('Connecting to the {0} database on {1}'.format(name, host))
            conn_string = "host='{0}' user='{1}' password='{2}' dbname='{3}'".format(host, user, password, name)
            self.conn = psycopg2.connect(conn_string)
            self.conn.autocommit = True
            self.conn.set_client_encoding('UTF-8')
            self.c = self.conn.cursor(cursor_factory = psycopg2.extras.DictCursor)

    def execute(self, query, *args):
        self.connect()
        return self.c.execute(query, *args)

    def fetchone(self):
        row = self.c.fetchone()
        return AttributeDict(row) if row else None

    def fetchall(self):
        return [AttributeDict(r) for r in self.c.fetchall()]

    def rowcount(self):
        return self.c.rowcount

    def close(self):
        if self.conn:
            logger.info('Closing database connection')
            self.conn.close()
            self.c = None
            self.conn = None
