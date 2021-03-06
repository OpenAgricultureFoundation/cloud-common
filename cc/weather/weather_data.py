#!/usr/bin/env python3

""" Weather Data class.
    - Caches weather data from Arable units in datastore.
    - Saves weather data from Arable units in bigquery.
"""

from datetime import datetime as dt, timedelta
import os, json, logging

from typing import Dict, List

from cloud_common.cc.google import env_vars 
from cloud_common.cc.google import datastore
from cloud_common.cc.google import bigquery

class WeatherData:

    #--------------------------------------------------------------------------
    def __init__(self) -> None:
        self.__name = os.path.basename(__file__)
        self.__kind = env_vars.ds_weather_entity
        if None == self.__kind:
            logging.critical(f'{self.__name} missing required environment '
                    f'variables.')


    #--------------------------------------------------------------------------
    # Return a list of arable devices, saved by the weather service into the
    # datastore.
    def get_arable_devices(self) -> List[str]:
        return datastore.get_keys(self.__kind)


    #--------------------------------------------------------------------------
    # Return a list of dicts of the computed weather data in the date range.  
    #
    # Input date strings must be in the format 'YYYY-MM-DD' and are inclusive.
    # arable_device_name is the arable device name.
    #
    # Returned data timestamps will be between every five minutes and 
    # hours / days.  So make no assumptions on intervals, the arable devices
    # are on cellular data and solar powered, so no guaranteed data.
    # 
    # Duplicate timestamp data has been filtered out.
    # The returned data is in DESCENDING order.
    #
    def get_computed_weather_data(self, 
            start_date: str, end_date: str, 
            arable_device_name: str,
            hourly: bool = True) -> List[Dict]:
        # The datastore caches all data points from each device 
        rows = datastore.get_sharded_entity_range(self.__kind, 'computed',
                arable_device_name, start_date, end_date) 
        # Sort by timestamp
        sorted_rows = []
        for row in rows:
            row = json.loads(row)
            sorted_rows.append(row)
        sorted_rows = sorted(sorted_rows, key=lambda r: r.get('time'), 
                reverse=True)
        # Remove duplicate timestamps
        previous_ts = None
        for d in sorted_rows:
            if d['time'] == previous_ts:
                sorted_rows.remove(d)
                continue
            previous_ts = d['time'] 
        return sorted_rows # return the (5 min) data 


    #--------------------------------------------------------------------------
    # Private cache to datastore.  Sharded for performance.
    # Returns True for success, False for error.
    def __save_DS(self, data_type: str, device_name: str, data: dict) -> bool:
        try:
            if data_type is None or device_name is None or data is None:
                logging.error(f'{self.__name} __save_DS: invalid args.')
                return False
            datastore.save_dict_to_entity(  # sharded for performance
                    self.__kind,        # Weather entity
                    device_name,        # device key
                    data_type,          # property name
                    json.dumps(data))   # data to save
            return True
        except Exception as e:
            logging.error(f'{self.__name} __save_DS: {e}')
            return False

    #--------------------------------------------------------------------------
    # NOT sharded.  Just for devices
    def __save_device_to_DS(self, data_type: str, device_name: str, data: dict) -> bool:
        try:
            if data_type is None or device_name is None or data is None:
                logging.error(f'{self.__name} __save_device_to_DS: invalid args.')
                return False
            datastore.save_with_key(
                    self.__kind,        # Weather entity
                    device_name,        # device key
                    json.dumps(data))   # data to save
            return True
        except Exception as e:
            logging.error(f'{self.__name} __save_device_to_DS: {e}')
            return False


    #--------------------------------------------------------------------------
    # Save an arable device to BQ and DS.
    # Returns True for success, False for error.
    def save_device(self, timestamp: str, device_dict: dict) -> bool:
        try:
            name = device_dict.get('name')
            if timestamp is None or name is None or 0 == len(device_dict):
                logging.error(f'{self.__name} save_device: invalid args')
                return False

            if not bigquery.save('device', name, timestamp, device_dict):
                logging.error(f'{self.__name} save_device: BQ save failed.')
                return False

            if not self.__save_device_to_DS('device', name, device_dict):
                logging.error(f'{self.__name} save_device: DS save failed.')
                return False

            return True
        except Exception as e:
            logging.error(f'save_device: {e}')
            return False


    #--------------------------------------------------------------------------
    # Return the details about an arable device.
    # Use get_arable_devices() to get the list of device keys.
    def get_device_details(self, device_key: str) -> Dict:
        details = datastore.get_by_key(self.__kind, device_key)
        if 0 == len(details):
            return {}
        return details 


    #--------------------------------------------------------------------------
    # Save raw 5 min data to BQ.
    # Returns True for success, False for error.
    def save_raw_five_min(self, timestamp: str, name: str, data: dict) -> bool:
        try:
            if timestamp is None or name is None or 0 == len(data):
                logging.error(f'{self.__name} save_raw_five_min: invalid args')
                return False

            if not bigquery.save('raw_five_min', name, timestamp, data):
                logging.error(f'{self.__name} save_raw_five_min: BQ save failed.')
                return False

            # don't bother saving raw data to DS
            return True
        except Exception as e:
            logging.error(f'save_raw_five_min: {e}')
            return False


    #--------------------------------------------------------------------------
    # Save raw aux data to BQ.
    # Returns True for success, False for error.
    def save_raw_aux(self, timestamp: str, name: str, data: dict) -> bool:
        try:
            if timestamp is None or name is None or 0 == len(data):
                logging.error(f'{self.__name} save_raw_aux: invalid args')
                return False

            if not bigquery.save('raw_aux', name, timestamp, data):
                logging.error(f'{self.__name} save_raw_aux: BQ save failed.')
                return False

            # don't bother saving raw data to DS
            return True
        except Exception as e:
            logging.error(f'save_raw_aux: {e}')
            return False


    #--------------------------------------------------------------------------
    # Save a computed data to BQ and DS.
    # Returns True for success, False for error.
    def save_computed(self, timestamp: str, name: str, data: dict) -> bool:
        try:
            if timestamp is None or name is None or 0 == len(data):
                logging.error(f'{self.__name} save_computed: invalid args')
                return False

            if not bigquery.save('computed', name, timestamp, data):
                logging.error(f'{self.__name} save_computed: BQ save failed.')
                return False

            if not self.__save_DS('computed', name, data):
                logging.error(f'{self.__name} save_computed: DS save failed.')
                return False

            return True
        except Exception as e:
            logging.error(f'save_computed: {e}')
            return False

