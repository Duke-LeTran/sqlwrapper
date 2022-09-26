import logging
import time
import datetime
import sqlalchemy
import pandas as pd
import numpy as np

import cx_Oracle
from cx_Oracle import InterfaceError
from SQLWrapper import db_menu, PATH_TO_CONFIG, CONFIG_FILE, Prompter
from SQLWrapper.base import SQL
from typing import Union

log = logging.getLogger(__name__)

p = Prompter()

class Oracle(SQL): # level 1
    """
    Oracle Database Wrapper
    Things to note in Oracle:
        * schemas == users
        * hostname == server
        * service_name == nickname of tnsaora file`
    This assumes you have all your Oracle ENV variables set correctly, i.e.,
        * ORACLE_BASE=/opt/oracle
        * ORACLE_HOME=$ORACLE_BASE/full_or_instant_client_home
        * TNS_ADMIN=$ORACLE_HOME/network/admin
        * (full) LD_LIBRARY_PATH=$ORACLE_HOME/lib:$LD_LIBRARY_PATH
        * (instant) LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
    """
    def __init__(self, config='Velos', opt_print=False): #defaults to Velos
        config = db_menu(PATH_TO_CONFIG, CONFIG_FILE, opt_print=opt_print).read_config(db=config) # local variable not saved
        super(Oracle, self).__init__(schema_name=config['hello']) # username is schema
        self._connect(config)
        self._save_config(config)

    def __del__(self):
        try:
            self.engine.dispose()
        except AttributeError: # never successfully made an engine
            pass
        try:
            self.conn.close()
        except AttributeError: #never sucessfully made a connection :'(
            pass
    
    def _generate_engine(self, config):
        """ generate engine"""
         # A. generate using string method
        try:
            self._generate_engine_dsn_method(config) 
        # B. generate using tnsnames method
        except sqlalchemy.exc.DatabaseError: 
            self._generate_engine_tns_method(config)
        except Exception as error:
            print(f"Failed to connect to Oracle database. Error: {error}")

    def _generate_engine_dsn_method(self, config):
        """ A. generate using string method"""
        dsn = cx_Oracle.makedsn(config['hostname'], config['port'], service_name=config['service_name'])
        self.engine = sqlalchemy.create_engine(\
            f"oracle+cx_oracle://{config['hello']}:{config['world']}@{dsn}",
            connect_args={"encoding":"UTF-8"},
            max_identifier_length=128) # this removes warnings
        with self.engine.connect() as conn: # if it works, it will pass
            pass 

    def _generate_engine_tns_method(self, config):
        """ B. generate using tnsnames method"""
        self.engine = sqlalchemy.create_engine(\
            f"oracle+cx_oracle://{config['hello']}:{config['world']}@{config['tns_alias']}",
            connect_args={"encoding":"UTF-8"},
            max_identifier_length=128) # this removes warnings
        with self.engine.connect() as conn: # if it works, it will pass
            pass 

    def _connect(self, config):
        try:
            self._generate_engine(config)
            self._generate_inspector()
            #self._generate_connection(config)
        #self._generate_cursor()
        except sqlalchemy.exc.DatabaseError as error:
            print(error)
    
    def tables(self, silent=True) -> list:
        """
        * returns all table names in connected database (of this schema;user)
        * note, this version does not cache 
        """
        df_t = self.read_sql('SELECT table_name \
                              FROM user_tables \
                              ORDER BY table_name', silent=silent)
        return df_t['table_name'].tolist()

    def views(self, silent=True) -> list:
        """
        * returns all views names in connected database (of this schema;user)
        * note, this version does not cache 
        """
        df_v = self.read_sql('SELECT view_name \
                              FROM user_views \
                              ORDER BY table_name', silent=silent)
        return df_v['view_name'].tolist()
    
    def ls_schemas(self):
        sql_statement = (f'SELECT username AS schema_name ' \
                         f'FROM ' \
                         f'    SYS.all_users ' \
                         f'ORDER BY ' \
                         f'    username')
        print(self.readify_sql(sql_statement))
        return pd.read_sql(self.readify_sql(sql_statement), self.engine)
    
    def columns(self,
                tbl_name:str,
                verbose=False,
                return_dtype=False) -> pd.core.indexes.base.Index:
        if verbose:
            return self.inspector.get_columns(tbl_name.lower(), dialect_options='oracle')
        elif return_dtype:
            df_dtype = pd.DataFrame(self.inspector.get_columns(tbl_name, dialect_options='oracle'))
            return {k.upper():v for k,v in zip(df_dtype['name'], df_dtype['type'])}
        else:
            df_result = self.select(tbl_name, limit=1, print_bool=False)
            return df_result.columns

    def scope(self):
        print('[Current Scope]\n',
              'Server:', self._config['hostname'].split('.')[0], "#aka hostname", '\n',
              'Database:', self._config['service_name'].split('.')[0], '\n', 
              'Schema/User:', self.schema_name, '\n')
    
    def version(self):
        """prints the Oracle DB version"""
        conn = self.engine.raw_connection()
        str_version = conn.version
        ls_verStr = [int(x) for x in str_version.split('.')]
        d_ver = {10 : '10g',
                 11 : '11g',
                 12 : '12c',
                 1 : 'Release 1',
                 2 : 'Release 2'}
        msg = 'Oracle Database '
        msg += d_ver[ls_verStr[0]] + ' '
        msg += d_ver[ls_verStr[1]] + ' '
        msg += '['+str_version+']'
        print(msg)
        
    @staticmethod
    def _limit(sql_statement, limit):
        if type(limit) is int: # if SELECT TOP is defined correctly as int
            sql_statement = (f"SELECT * FROM ({sql_statement}) " \
                             f"WHERE ROWNUM <= {str(limit)}")
        return sql_statement
        
    def select(self,
               tbl_name:str,
               cols:Union[list, str]='*',
               schema:str=None,
               db_link:str=None,
               print_bool:bool=True,
               limit:int=10, # default to 10
               where:str=None,
               order_by:str=None,
               desc:bool=False):
        """
        Function: returns a pd.DataFrame
        cols: list of columns
        tbl: table name
        schema: schema name (or default is selected)
        limit: limit number of rows
        """
        #SELECT
        col_names = self._select_cols(cols) 
        # SCHEMA
        prefix = self._get_schema(schema, self.schema_name)
        # DB_LINK
        # SQL SKELETON
        # sql_statement = f"SELECT {col_names} FROM {prefix}.{tbl_name.lower()}"
        if db_link is not None:
            sql_statement = f"SELECT {col_names} FROM {tbl_name.lower()}@{db_link}"
        else:
            sql_statement = f"SELECT {col_names} FROM {prefix}.{tbl_name.lower()}"
        # WHERE
        sql_statement = self._where(sql_statement, where)
        # ORDER BYselect_cols
        sql_statement = self._order_by(sql_statement, cols, order_by, desc)
        # LIMIT
        sql_statement = self._limit(sql_statement, limit)
        # LOG
        if print_bool:
            self._save_sql_hx(sql_statement + ';')
        df_output = pd.read_sql(sql_statement, con=self.engine)
        # convert names to capital for consistency
        df_output.columns = [x.upper() for x in df_output.columns]
        return df_output

    def drop(self, tbl_name:str, what:str='TABLE', skip_prompt=False, answer=None):
        """For now this only drops tables, will expand in future to include sequences, etc."""
        if skip_prompt:
            answer = 'yes'
        #if tbl_name not in self.tables():
        #    print(f'Table {tbl_name} does not exist in the db. Nothing to drop.')
        #else:
        sql_statement = f'DROP {what} {self.schema_name}.{tbl_name}'
        if p.prompt_confirmation(msg=f'Are you sure your want to drop {tbl_name}?', answer=answer):
            self.read_sql(sql_statement)
    
    def insert(self):
        """use to_oracle instead"""
        pass
    
    def _fix_data(self, df_input:pd.DataFrame):
        """
        * str: replace the actual string "None" with an empty string
        * int: convert to string; convert pd.IntNull to empty string
        """
        df_temp = df_input.copy()
        ls_ints = [np.int64, int] #collect as they increase
        # A. Fix Strings,replace the actual string "None" with an empty string
        df_temp = df_temp.replace('None', '')
        df_temp = df_temp.fillna('')
        
       
        for col in df_temp.columns:
             # B. Fix Integers
            if df_temp[col].dtype in ls_ints: # if integer
                #print('INTEGER: ', col)
                log.debug('INTEGER: ' + col)
                # convert to string
                df_temp.loc[:,col] = df_temp[col].astype(str)
                log.info(df_temp.loc[:,col])
                # replace pd.IntDtype64 with empty string
                df_temp.loc[:,col] = df_temp[col].replace('<NA>', '')
            elif 'date' in col.lower():
                #print('DATE: ', col)
                log.debug('DATE: ' + col)
                try: # remove time, only date
                    df_temp[col] = df_temp[col].apply(pd.to_datetime).dt.strftime('%Y-%m-%d')
                except: # treat as null
                    df_temp[col] = ''
            elif (df_temp[col].dtype == bool) or (df_temp[col].dtype.name == 'bool'):
                #print('BOOL: ', col)
                log.debug('BOOL: ' + col)
                bool_dict = {'True' : str(1), 'False' : str(0)}
                df_temp[col] = df_temp[col].astype(str).apply(lambda x : bool_dict[x])
            else:
                #print('VARCHAR2: ', col)
                log.debug('VARCHAR2: ' + col)
        
        df_temp = df_temp.replace('None', '')
        df_temp = df_temp.fillna('')

        return df_temp
    
    def _generate_conn_cursor(self, engine=None):
        """
        * Generate a temporary cursor
        * Remember to close the cursor once done 
        """
        if engine==None:
            engine = self.engine

        conn = engine.raw_connection()
        cursor = conn.cursor()
        return conn, cursor

    def to_oracle(self, df_input, table, schema=None, engine=None, cap_cols=False):
        """
        Utilizes cx_oracle's executemany() method, which is much faster
        Credit to Bill Riedl's function, see repository:
            - gitlab/ucd-ri-pydbutils/PandasDBDataStreamer.py
        """
        from sqlalchemy.exc import DatabaseError

        # SET DEFAULTS #########################################################
        if cap_cols:
            df_input.columns = [x.upper() for x in df_input.columns]

        if engine is None:
            engine = self.engine

        if schema is None:
            schema = self.schema_name

        # A. GENERATE CONN AND CURSOR ##########################################
        # conn = self.engine.raw_connection()
        # cur = conn.cursor()
        conn, cursor = self._generate_conn_cursor()

        # B. GRAB COLS AS STRING ###############################################
        df_temp = self._fix_data(df_input.copy())
        cols = str(', '.join(df_temp.columns.tolist()))

        # C. CONVERT EACH VAL OF EACH ROW > STRING #############################
        func = lambda ls : [str(x) for x in ls]
        # converts df to a list of string values 
        lines = [tuple(func(x)) for x in df_temp.values]
        
        # D. BIND VARS #########################################################
        bind_vars = ''
        for i in range(len(df_temp.columns)):
            bind_vars = bind_vars + ':' + str(i + 1) + ','
        
        ## remove trailing
        bind_vars = bind_vars[:-1]

        # E. GENERATE INSERT STATEMENT #########################################
        sql = f'INSERT INTO {schema}.{table.upper()} ({cols}) values ({bind_vars})'
        print(sql)

        # F. EXECUTE SQL #######################################################
        cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
        log.info("=======================================================")
        log.info(f" cx_Oracle EXECUTEMANY, INSERT INTO {schema}.{table}... ")
        log.info("=======================================================")
        log.debug(sql)
        try:
            cursor.executemany(sql, lines)
            conn.commit()
        except Exception as e:
            log.warning(e)
        finally:
            cursor.close()
            conn.close()
            return sql, lines[:10]

    def update(self,
               tbl_name,
               set_col,
               set_val,
               cond_col,
               condition,
               autocommit=False,
               silent=False):
        """provides a quick way to update and commit"""
        conn, cursor = self._generate_conn_cursor()
        sql_statement = f"UPDATE {tbl_name.lower()} SET {set_col} = {set_val} WHERE {cond_col} = {condition}"
        sql = self._readify_sql(sql_statement)
        if not silent:
            print(sql)
        try:
            cursor.execute(sql)
            if autocommit==True:
                conn.commit()
            else:
                if p.prompt_confirmation(msg=f'Do you want to commit the update?'):
                    conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            log.warning(e)
            cursor.close()
            conn.close()

    def callproc(self, name_of_stored_procedure:str, engine=None, *args, **kwargs):
        """
        https://cx-oracle.readthedocs.io/en/latest/api_manual/cursor.html#Cursor.callproc
        https://cx-oracle.readthedocs.io/en/latest/user_guide/plsql_execution.html#plsqlproc
        Note, you have to know the input, output variables of the stored procedure
        """
        conn, cursor = self._generate_conn_cursor(engine=engine)
        #out_val = cursor.var(str)
        try:
            cursor.callproc(name_of_stored_procedure, *args, **kwargs)
            conn.commit()
        except Exception as e:
            log.warning(e)
        finally:
            conn.close()
            cursor.close()


