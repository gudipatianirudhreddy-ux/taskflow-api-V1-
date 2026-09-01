import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    kwargs={
        "autocommit": True,
        "row_factory": dict_row
    }
)

checkpointer = PostgresSaver(pool)

checkpointer.setup()