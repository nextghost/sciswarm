from django.db import DEFAULT_DB_ALIAS, connections

LOCK_ACCESS_SHARE = 'ACCESS SHARE'
LOCK_ROW_SHARE = 'ROW SHARE'
LOCK_ROW_EXCLUSIVE = 'ROW_EXCLUSIVE'
LOCK_SHARE_UPDATE_EXCLUSIVE = 'SHARE UPDATE EXCLUSIVE'
LOCK_SHARE = 'SHARE'
LOCK_SHARE_ROW_EXCLUSIVE = 'SHARE ROW EXCLUSIVE'
LOCK_EXCLUSIVE = 'EXCLUSIVE'
LOCK_ACCESS_EXCLUSIVE = 'ACCESS EXCLUSIVE'

def lock_table(model, mode=None, nowait=False, using=None):
    if using is None:
        using = DEFAULT_DB_ALIAS
    connection = connections[using]
    sql_tpl = 'LOCK TABLE {table}'
    args = dict(table=connection.ops.quote_name(model._meta.db_table))
    if mode is not None:
        sql_tpl += ' IN {mode} MODE'
        args['mode'] = mode
    if nowait:
        sql_tpl += ' NOWAIT'
    sql = sql_tpl.format(**args)
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()
