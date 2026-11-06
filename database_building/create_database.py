from argparse import ArgumentParser
import psycopg2
from psycopg2.sql import SQL
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# def create_database(
#     database:str,
#     username:str,
#     password:str,
#     host:str,
#     port:int
#     ):
#     connection = psycopg2.connect(database="postgres", user=username, password=password, host=host, port=port)

#     connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

#     cur = connection.cursor()
#     cur.execute(SQL(f"CREATE DATABASE {database} WITH OWNER {};"))

#     connection.close()

if __name__ == "__main__":
    pass