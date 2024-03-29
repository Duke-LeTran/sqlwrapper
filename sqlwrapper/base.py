"""
SQLWrapper.py
    |--> db_menu.py
    |--> prompter.py
    
DESCRIPTION: 
    SQLWrapper object to help manage database connections on unix server. It
    features a config file similar to the Oracle tnsnames.ora

SETUP:
    1. Place and edit config files in ~/.mypylib/ 
    2. Run ```chmod 600 ~/.mypylib/db_config.ini``` to protect the files

Duke LeTran <duke.letran@gmail.com; daletran@ucdavis.edu>
Research Infrastructure, IT Health Informatics, UC Davis Health
"""
# standard library
import logging
import os
# added libraries
import pandas as pd
from sqlalchemy import exc, inspect
# SQLWrapper
from sqlwrapper.prompter import Prompter
from sqlwrapper.config import config_reader
from typing import Union#, Literal
from typing_extensions import Literal
from configparser import SectionProxy

# logging
log = logging.getLogger(__name__)

p = Prompter()


class SQL: # level 0
    """ABSTRACT BASE CLASS"""
    def __init__(self, db_name='Duke', schema_name='dbo'):
        self.db_name = db_name
        self.schema_name= schema_name
        self.prefix = db_name + '.' + schema_name
        # self.msg_inaction = "No action taken. Remember to rollback or commit."
        self.sqlHx = pd.Series(dtype='object')
        self.p = Prompter()
    
    def _init_config(self, db_section:SectionProxy, db_entry:str, opt_print:bool):
        if db_section is None:
            config_result = config_reader().read(db_entry, opt_print) # local variable not saved
        else:
            config_result = db_section
        return config_result
    
    def _connect(self):
        """connect to database"""
        self._generate_engine()
        self._generate_inspector()
    
    def _test_connection(self, prefix=None):
        with self.engine.connect() as conn: # if it works, it will pass
            if prefix is not None:
                print(f'✅ New connection successfully established: {prefix}')
            else:
                print(f'✅ New connection successfully established.')
            return 1

    def _generate_inspector(self):
        from sqlalchemy import inspect
        self.inspector = inspect(self.engine)
    
    
    def _save_config(self, config):
        """obfuscates pw; saves config obj"""
        #config['world'] = 'hello'
        self._config = config
    
    @staticmethod    
    def open_config():
        os.startfile(PATH_TO_CONFIG / CONFIG_FILE)


    def columns(self,
                tbl_name:str,
                verbose=False,
                return_dtype=False) -> Union[pd.core.indexes.base.Index, list]:
        if verbose:
            return self.inspector.get_columns(tbl_name.lower())
        elif return_dtype:
            df_dtype = pd.DataFrame(self.inspector.get_columns(tbl_name.lower()))
            return {k.upper():v for k,v in zip(df_dtype['name'], df_dtype['type'])}
        else:
            df_result = self.select(tbl_name, limit=1, print_bool=False)
            return df_result.columns
    
    def truncate(self, table:str, schema:str=None, engine=None, answer=None):
        """
        You can use this to truncate other tables too, static method
        """
        # set defaults
        if schema is None:
            schema = self.schema_name
        if engine is None:
            engine = self.engine
        
        # prompt for confirmation
        if not p.prompt_confirmation(answer=answer): # if user denies
            print('Did not truncate, canceled by user.')

        # create connection and truncate
        conn = engine.raw_connection()
        cursor = conn.cursor()
        log.info("=======================================================")
        log.info(f"TRUNCATE TABLE {schema}.{table}... ")
        log.info("=======================================================")
        try:
            cursor.execute(f"TRUNCATE TABLE {schema}.{table}")
        except ProgrammingError as e:
            cursor.execute(f"TRUNCATE TABLE {schema}.{table.lower()}")
        except ProgrammingError as e:
            cursor.execute(f"TRUNCATE TABLE {schema}.{table.upper()}")
        log.info("Table truncated, done!")
        conn.close()
    
    def drop(self, tbl_name:str, what:str='TABLE', skip_prompt=False, answer=None):
        """For now this only drops tables, will expand in future to include sequences, etc."""
        if skip_prompt:
            answer = 'yes'
        if tbl_name not in self.tables():
            print(f'Table {tbl_name} does not exist in the db. Nothing to drop.')
        else:
            sql_statement = f'DROP {what} {self.schema_name}.{tbl_name}'
            if p.prompt_confirmation(msg=f'Are you sure your want to drop {tbl_name}?', answer=answer):
                self.read_sql(sql_statement)
    
    @staticmethod
    def merge_frames(frames:list, on:str=None):
        """
        Parameters: pass a list of dataframes
        Notes:
        * Uses recursion to merge frames
        * similar to pd.concat()
        * will merge on single-to-many keys -- SO BECAREFUL 
        """
        if on is None:
            print('You must pass a key to merge on. Use parameter "on=your_key".')
            return
        print('❤️' * len(frames))
        if len(frames) > 2: # if more than 2 dataframes
            # pass deeper
            ##time.sleep(1)
            result = merge_frames(frames[:-1], on=on) # drop the last one
            # merge some action item
            print('🌱' * len(frames))
            ##time.sleep(1)
            result = pd.merge(result, frames[-1])
            return result
        else: # else only two left..
            ##time.sleep(1)
            print('BOTTOM!!')
            print('🌱' * len(frames))
            # merge first pair of dataframes
            return pd.merge(frames[0], frames[1], on=on)
    
    def read_sql(self, sql_statement, silent=False):
        """ Imitation of the pandas read_sql"""
        sql = self._readify_sql(sql_statement)
        if not silent:
            print(sql)
        try:
            return pd.read_sql(sql, self.engine)
        except exc.ResourceClosedError as error:
            pass # if no rows returned
        except AttributeError:
            # AttributeError: 'OptionEngine' object has no attribute 'execute'
            # breaking error from sqlalchemy 2.0.0+
            from sqlalchemy import text
            with self.engine.connect() as conn:
                return pd.read_sql(text(sql), conn)


    def tables(self):
        try:
            return [x.upper() for x in sorted(self.inspector.get_table_names())]
        except Exception as error:
            log.error(error)

    def schemas(self):
        return self.inspector.get_schema_names()

    def tbl_exists(self, tbl_name) -> bool:
        """checks if table exists in the database"""
        return tbl_name in self.tables(silent=True)

    # @property
    # def schema(self):
    #     return self.schema_name
    
    @staticmethod
    def _readify_sql(sql_input):
        return (' ').join(sql_input.replace('\n','').split())
        
    def _save_sql_hx(self, sql_statement):
        sql_statement = ' '.join(sql_statement.split()) #remove extra whitespace
        #self.sqlHx = self.sqlHx.append(pd.Series(sql_statement), ignore_index=True)
        self.sqlHx = pd.concat([self.sqlHx, pd.Series(sql_statement)]) # fixed for pandas deprecating append()

    def close(self):
        self.__del__()
    
    @staticmethod
    def _select_cols(cols):
        if type(cols) is list: # if list is provided
            if len (cols) > 0:
                col_names = ", ".join(cols)
            else: 
                col_names = cols[0] # grab str of first and only item
            return col_names
        elif type(cols) is str: # if only one column provided as str
            return cols
    
    @staticmethod
    def _get_schema(schema, schema_default):
        """ check if schema is defined, else use default"""
        if schema is not None: #if schema is defined
            prefix = f'{schema}'
        else: # else use default
            prefix = f'{schema_default}'
        return prefix
    
    @staticmethod
    def _where(sql_statement, where):
        if where:
            sql_statement = f"{sql_statement} WHERE {where}"
        return sql_statement  
    
    @staticmethod
    def _order_by(sql_statement:str, cols:list, order_by:str, desc:bool):
        if order_by:
            sql_statement = f"{sql_statement} ORDER BY {order_by}"
        if desc:
            sql_statement = f"{sql_statement} DESC"
        return sql_statement

    @staticmethod
    def _cap_case(table:str, cap_case:Literal['lower', 'upper']):
        """doesn't have to be a table"""
        if cap_case == 'lower':
            table = table.lower()
        elif cap_case == 'upper':
            table = table.upper()
        else:
            pass
        return table
    
    @staticmethod
    def _cols_case(caps_case:str, df_input:pd.DataFrame):
        df_output = df_input.copy()
        if (caps_case is None) or (caps_case == False):
            pass
        elif caps_case.lower() == 'lower':
            df_output.columns = [x.upper() for x in df_input.columns]
        elif caps_case.upper() == 'upper':
            df_output.columns = [x.upper() for x in df_input.columns]
        else:
            pass
        return df_output
    
    
    def __del__(self):
        from cx_Oracle import OperationalError
        try:
            self.engine.dispose()
        except AttributeError as error:
            log.error(error)
        except InterfaceError as error:
            log.error(error)
        except OperationalError as error:
            log.error('db.engine likely idled and already closed, don\'t worry.')
            log.error(error)
        except Exception as error:
            log.warning(error)
        except ImportError as error:
            # python interpreter is shutting down.
            log.warning(error)


