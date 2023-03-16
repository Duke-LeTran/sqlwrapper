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
import os
import logging
from pathlib import Path, PurePath
import pandas as pd

# SQLWrapper
#from sqlwrapper.dbmenu import db_menu
from sqlwrapper.prompter import Prompter
from typing import Union
from configparser import ConfigParser, RawConfigParser
# logging
log = logging.getLogger(__name__)

################################################################################
# PATH in which sqlwrapper will look for db_config.ini
################################################################################
# setup
LS_PATH = [
    Path.home() / Path('.mypylib'),
    Path.cwd()
]

#name of your config file
LS_CONFIG_FILES = [
    'db_config.ini', 
    '.env',
    'config.env'
]

# prompter
p = Prompter()


class config_looker:
    """This looks for different config files on your computer"""
    def __init__(self, LS_PATH, LS_CONFIG_FILES):
        # setup
        self._init_paths(LS_PATH, LS_CONFIG_FILES)
        self._init_if_none()
    
    @property
    def current(self):
        return (self._PATH, self._FILE)
    
    @current.setter
    def current(self, values):
        try:
            self._PATH, self._FILE = values
            self._CONFIG = self._PATH / self._FILE
        except ValueError:
            raise ValueError("Pass an iterable with two items")

    @property
    def current_list(self):
        return self._LS_PATH, self._LS_CONFIG_FILES

    @current_list.setter
    def current_list(self, values):
        try:
            path, file = values
            if path not in self._LS_PATH:
                self._LS_PATH.append(path)
            if file not in self._LS_CONFIG_FILES:
                self._LS_CONFIG_FILES.append(file)
        except ValueError:
            raise ValueError("Pass an iterable with two items")
    
    
    @property
    def CONFIG(self):
        return self._CONFIG

    def _init_paths(self, PATH:list, FILE:list):
        self._LS_PATH = PATH
        self._LS_CONFIG_FILES = FILE
        for path in PATH:
            for file in FILE:
                if os.path.exists(path / file):
                    self.current = (path, file)
                    return path, file

    def _init_if_none(self):
        while self.df_config.empty:
            print(self.df_config_all)
            print('No config file was found.')
            msg = 'Do you want to init `db_config.ini` '
            msg += 'in your current working directory?'
            if p.prompt_confirmation(msg):
                self._init_new_config()
            elif p.prompt_confirmation('Do you want to add a path?'):
                path = input('Enter path_to_config >> ')
                self.append_path(path)
                self._init_paths(self._LS_PATH, self._LS_CONFIG_FILES)

    def _init_new_config(self):
        import shutil
        print("Initializing a new config file: ")
        path = Path(os.path.dirname(__file__))
        new_config_file = 'db_config.ini'
        src = path / '..' / 'config'
        dst = Path.cwd()
        shutil.copyfile(src / 'db_config.ini.example',
                        dst / new_config_file)

        self.current = (dst, new_config_file)
        self.current_list = (dst, new_config_file) 
        print('  path_to_config:', dst / new_config_file)


    @property
    def config_path(self):
        return self._LS_PATH
    
    def append_path(self, path:Union[str, Path]):
        if type(path) == str:
            path = Path(path)
        
        self._LS_PATH.append(path)
        #print(self.config_paths)

    @property
    def df_config(self):
        return self.df_config_all.loc[self.df_config_all['exists?'], :]

    @property
    def df_config_all(self):
        from os.path import exists
        return pd.DataFrame([(exists(path / file), path, file)
             for path in self._LS_PATH 
             for file in self._LS_CONFIG_FILES],
             columns=['exists?', 'path', 'file'])
    
    def select_config(self):
        ls_menu = [(x,y) for x,y in zip(self.df_config['path'], 
                                        self.df_config['file'])]
        new_config = p.prompt_menu('Select config', ls_menu)
        print(f"Old config: {self.current}")
        print(f"New config: {new_config}")
        self.current = new_config
    
    def open_config(self):
        """opens the db_config.ini file"""
        PATH_TO_CONFIG, CONFIG_FILE = self.current
        os.startfile(PATH_TO_CONFIG / CONFIG_FILE)


class config_reader(config_looker):
    def __init__(self):
        super(config_reader, self).__init__(LS_PATH, LS_CONFIG_FILES)
        self._init_config_path() #get setup options
    
    def _init_config_path(self):
        """
        SETUP: These need to be setup once before use
        """
        #self.config_looker = config_looker(LS_PATH, LS_CONFIG_FILES)
        os.path.basename(__file__)
        path, file = self.current
        self._config_file = path / file
    
    @property
    def config_file(self):
        """this is the Path object to the config file"""
        return self._config_file
    
    @property
    def config(self):
        
        """the actual config file"""
        config = ConfigParser()#interpolation=None)
        config.read(self.CONFIG)
        return config

    @property
    def config_raw(self):
        
        """the actual config file"""
        config = RawConfigParser()
        config.read(self.CONFIG)
        return config
    
    @property
    def entries(self) -> list:
        config = self.config
        return sorted(list(config.keys()))
    
    def read(self, 
            db_entry:str=None,
            opt_print=True, 
            return_entry=True,
            interpolate=False):
        # if verbose 
        if opt_print:
            msg = f'Initializing database connection from '
            msg += f'config file {self.CONFIG} using [{db_entry}].'
            print(msg)

        # use regular ConfigParser
        if interpolate:
            config_result = self.config
        # else use RawConfigParser (default)
        else: 
            config_result = self.config_raw
        
        # if db_entry, return only section
        if return_entry and db_entry is not None: # return only entry
            return config_result[db_entry]
        # else, return the whole config file
        else: 
            return config_result


class Missing_DBCONFIG_ValueError(Exception):
    """raised when a value is missing"""
    pass

class base_config:
    """
    For db_config parameter backwards compatability and data interoperability.

    These functions help collate synonyms that represent the same concept, e.g..
        * [username, hello]
        * [password, pw, world]
        * [server, hostname]
    """
    def __init__(self):
        pass

    @property
    def _username(self):
        result = self._config.get('username', self._config.get('hello'))
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    
    @property
    def _pw(self):
        result = self._config.get('password', self._config.get('world'))
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result

    @property
    def _hostname(self):
        result = self._config.get('server', self._config.get('hostname'))
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    
    @property
    def _database(self):
        result = self._config.get('database', self._config.get('db_name'))
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    
    @property
    def _port(self):
        result = self._config.get('port')
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    
    @property
    def _driver(self):
        result = self._config.get('driver')
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    
    @property
    def _service_name(self):
        result = self._config.get('service_name')
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
        
    @property
    def _tns_alias(self):
        result = self._config.get('tns_alias')
        if result is None:
            raise Missing_DBCONFIG_ValueError# Error
        else:
            return result
    