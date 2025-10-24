import io
import random
import string

from django.db import connection
from psycopg2 import sql


def insert_with_copy_from_and_tmp_table(df, table_destination, insert_columns='*'):
    '''
    Uses a temporary table and insert into on conflict do nothing to prevent errors if inserting duplicates.
    :param df:
    :param table_destination:
    :return:
    '''
    with connection.cursor() as cursor, io.StringIO() as buffer:
        df.to_csv(buffer, index=False, na_rep='null')
        buffer.seek(0)
        tmp_tbl_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
        # create tmp table with 1 record from original table and truncate that record again to
        # so the tmp table has the same schema as the original table.
        cursor.execute(
            sql.SQL('create temp table {} as select * from {} limit 1').format(sql.Identifier(tmp_tbl_name),
                                                                               sql.Identifier(table_destination)))
        cursor.execute(sql.SQL('truncate table {}').format(sql.Identifier(tmp_tbl_name)))
        q = 'copy {}(' + (",".join(
            ['{}' for _ in range(len(df.columns.values.tolist()))])) + ') from stdin csv header NULL as \'null\''
        cursor.copy_expert(
            sql.SQL(
                q).format(sql.Identifier(tmp_tbl_name), *[sql.Identifier(e) for e in df.columns.values.tolist()]),
            buffer)
        query = 'insert into {}'
        if insert_columns != '*':
            query += ' (' + insert_columns + ') '  # FIXME SQL INJECTION POSSIBLE HERE
        query += 'select ' + insert_columns + ' from {} on conflict do nothing'

        cursor.execute(
            sql.SQL(query).format(
                sql.Identifier(table_destination),
                sql.Identifier(tmp_tbl_name)))
        cursor.execute(sql.SQL('drop table {}').format(sql.Identifier(tmp_tbl_name)))


def update_from_tmp_table(df, table_destination, update_columns, where_clause):
    '''

    :param df:
    :param table_destination:
    :param update_columns: the set part of the update query string. e.g. "field1 = x.field" with x being the temporary table.
    :return:
    '''
    with connection.cursor() as cursor, io.StringIO() as buffer:
        df.to_csv(buffer, index=False, na_rep='null')
        buffer.seek(0)
        tmp_tbl_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
        cursor.execute(
            sql.SQL('create temp table {} as select * from {} limit 1').format(sql.Identifier(tmp_tbl_name),
                                                                               sql.Identifier(table_destination)))
        cursor.execute(sql.SQL('truncate table {}').format(sql.Identifier(tmp_tbl_name)))

        # first insert data into tmp tbl
        insert_with_copy_from_and_tmp_table(df, tmp_tbl_name)

        query = 'update {} set ' + update_columns + ' from {} x where ' + where_clause  # FIXME SQL INJECTION POSSIBLE HERE
        q = sql.SQL(query).format(
            sql.Identifier(table_destination),
            sql.Identifier(tmp_tbl_name),
        )
        cursor.execute(q)
        cursor.execute(sql.SQL('drop table {}').format(sql.Identifier(tmp_tbl_name)))
