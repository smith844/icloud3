"""
Platform that supports scanning iCloud.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.icloud/


Special Note: I want to thank Walt Howd, (iCloud2 fame) who inspired me to
    tackle this project. I also want to give a shout out to Kovács Bálint,
    Budapest, Hungary who wrote the Python WazeRouteCalculator and some
    awesome HA guys (Petro31, scop, tsvi, troykellt, balloob, Myrddyn1,
    mountainsandcode,  diraimondo, fabaff, squirtbrnr, and mhhbob) who
    gave me the idea of using Waze in iCloud3.
                ...Gary Cobb aka GeeksterGary, Vero Beach, Florida, USA

Thanks to all
"""

#pylint: disable=bad-whitespace, bad-indentation
#pylint: disable=bad-continuation, import-error, invalid-name, bare-except
#pylint: disable=too-many-arguments, too-many-statements, too-many-branches
#pylint: disable=too-many-locals, too-many-return-statements
#pylint: disable=unused-argument, unused-variable
#pylint: disable=too-many-instance-attributes, too-many-lines

VERSION = '2.1.0b'
'''
v2.1.0b (3/27/2020)
- Fixed a problem where the device would not be moved back into a zone when there was no zone exit trigger. The zone distance checks was comparing the current distance in meters to the limit distance in kilometers.
v2.1.0a (3/24/2020)
- The iOS app v2 trigger time was used in an event msg when a trigger change occurred. If the iOS app version running was 1, an error was being generated no tracking was being done.

'''
#Symbols = •▶¦▶ ●►◄▬▲▼◀▶ oPhone=►▶►

import logging
import os
import sys
import time
import json
import voluptuous as vol

from   homeassistant.const                import CONF_USERNAME, CONF_PASSWORD
from   homeassistant.helpers.event        import track_utc_time_change
import homeassistant.helpers.config_validation as cv

from   homeassistant.util                 import slugify
import homeassistant.util.dt              as dt_util
from   homeassistant.util.location        import distance

from   homeassistant.components.device_tracker import (
          PLATFORM_SCHEMA, DOMAIN, ATTR_ATTRIBUTES)

_LOGGER = logging.getLogger(__name__)

#Changes in device_tracker entities are not supported in HA v0.94 and
#legacy code is being used for the DeviceScanner. Try to import from the
#.legacy directory and retry from the normal directory if the .legacy
#directory does not exist.
try:
    from homeassistant.components.device_tracker.legacy import DeviceScanner
    HA_DEVICE_TRACKER_LEGACY_MODE = True
except ImportError:
    from homeassistant.components.device_tracker import DeviceScanner
    HA_DEVICE_TRACKER_LEGACY_MODE = False

#Vailidate that Waze is available and can be used
try:
    import WazeRouteCalculator
    WAZE_IMPORT_SUCCESSFUL = 'YES'
except ImportError:
    WAZE_IMPORT_SUCCESSFUL = 'NO'
    pass

try:
    from .pyicloud_ic3 import PyiCloudService
    PYICLOUD_IC3_IMPORT_SUCCESSFUL = True
except ImportError:
    PYICLOUD_IC3_IMPORT_SUCCESSFUL = False
    pass

DEBUG_TRACE_CONTROL_FLAG = False
#from .const_ic3 import "*"

HA_ENTITY_REGISTRY_FILE_NAME='/config/.storage/core.entity_registry'
ENTITY_REGISTRY_FILE_KEY    = 'core.entity_registry'
STORAGE_KEY_ICLOUD          = 'icloud'
STORAGE_KEY_ENTITY_REGISTRY = 'core.entity_registry'
STORAGE_VERSION             = 1
STORAGE_DIR                 = ".storage"

CONF_ACCOUNT_NAME           = 'account_name'
CONF_GROUP                  = 'group'
CONF_DEVICENAME             = 'device_name'
CONF_NAME                   = 'name'
CONF_TRACKING_METHOD        = 'tracking_method'
CONF_MAX_IOSAPP_LOCATE_CNT  = 'max_iosapp_locate_cnt'
CONF_TRACK_DEVICES          = 'track_devices'
CONF_TRACK_DEVICE           = 'track_device'
CONF_UNIT_OF_MEASUREMENT    = 'unit_of_measurement'
CONF_INTERVAL               = 'interval'
CONF_BASE_ZONE              = 'base_zone'
CONF_INZONE_INTERVAL        = 'inzone_interval'
CONF_STATIONARY_STILL_TIME  = 'stationary_still_time'
CONF_STATIONARY_INZONE_INTERVAL = 'stationary_inzone_interval'
CONF_MAX_INTERVAL           = 'max_interval'
CONF_TRAVEL_TIME_FACTOR     = 'travel_time_factor'
CONF_GPS_ACCURACY_THRESHOLD = 'gps_accuracy_threshold'
CONF_OLD_LOCATION_THRESHOLD = 'old_location_threshold'
CONF_IGNORE_GPS_ACC_INZONE  = 'ignore_gps_accuracy_inzone'
CONF_HIDE_GPS_COORDINATES   = 'hide_gps_coordinates'
CONF_WAZE_REGION            = 'waze_region'
CONF_WAZE_MAX_DISTANCE      = 'waze_max_distance'
CONF_WAZE_MIN_DISTANCE      = 'waze_min_distance'
CONF_WAZE_REALTIME          = 'waze_realtime'
CONF_DISTANCE_METHOD        = 'distance_method'
CONF_COMMAND                = 'command'
CONF_SENSORS                = 'create_sensors'
CONF_EXCLUDE_SENSORS        = 'exclude_sensors'
CONF_ENTITY_REGISTRY_FILE   = 'entity_registry_file_name'
CONF_LOG_LEVEL              = 'log_level'

# entity attributes (iCloud FmF & FamShr)
ATTR_ICLOUD_LOC_TIMESTAMP       = 'timeStamp'
ATTR_ICLOUD_HORIZONTAL_ACCURACY = 'horizontalAccuracy'
ATTR_ICLOUD_VERTICAL_ACCURACY   = 'verticalAccuracy'
ATTR_ICLOUD_BATTERY_STATUS      = 'batteryStatus'
ATTR_ICLOUD_BATTERY_LEVEL       = 'batteryLevel'
ATTR_ICLOUD_DEVICE_STATUS       = 'deviceStatus'

# entity attributes
ATTR_ZONE               = 'zone'
ATTR_ZONE_TIMESTAMP     = 'zone_timestamp'
ATTR_LAST_ZONE          = 'last_zone'
ATTR_GROUP              = 'group'
ATTR_TIMESTAMP          = 'timestamp'
ATTR_TRIGGER            = 'trigger'
ATTR_BATTERY            = 'battery'
ATTR_BATTERY_LEVEL      = 'battery_level'
ATTR_BATTERY_STATUS     = 'battery_status'
ATTR_INTERVAL           = 'interval'
ATTR_ZONE_DISTANCE      = 'zone_distance'
ATTR_CALC_DISTANCE      = 'calc_distance'
ATTR_WAZE_DISTANCE      = 'waze_distance'
ATTR_WAZE_TIME          = 'travel_time'
ATTR_DIR_OF_TRAVEL      = 'dir_of_travel'
ATTR_TRAVEL_DISTANCE    = 'travel_distance'
ATTR_DEVICE_STATUS      = 'device_status'
ATTR_LOW_POWER_MODE     = 'low_power_mode'
ATTR_TRACKING           = 'tracking'
ATTR_DEVICENAME_IOSAPP  = 'iosapp_device'
ATTR_AUTHENTICATED      = 'authenticated'
ATTR_LAST_UPDATE_TIME   = 'last_update'
ATTR_NEXT_UPDATE_TIME   = 'next_update'
ATTR_LAST_LOCATED       = 'last_located'
ATTR_INFO               = 'info'
ATTR_GPS_ACCURACY       = 'gps_accuracy'
ATTR_GPS                = 'gps'
ATTR_LATITUDE           = 'latitude'
ATTR_LONGITUDE          = 'longitude'
ATTR_POLL_COUNT         = 'poll_count'
ATTR_ICLOUD3_VERSION    = 'icloud3_version'
ATTR_VERTICAL_ACCURACY  = 'vertical_accuracy'
ATTR_ALTITUDE           = 'altitude'
ATTR_BADGE              = 'badge'
ATTR_EVENT_LOG          = 'event_log'
ATTR_PICTURE            = 'entity_picture'

#icloud and other attributes
ATTR_LOCATION           = 'location'
ATTR_ATTRIBUTES         = 'attributes'
ATTR_RADIUS             = 'radius'
ATTR_FRIENDLY_NAME      = 'friendly_name'
ATTR_NAME               = 'name'
ATTR_ISOLD              = 'isOld'

ISO_TIMESTAMP_ZERO      = '0000-00-00T00:00:00'
ZERO_HHMMSS             = '00:00:00'
TIME_24H                = True
UTC_TIME                = True
LOCAL_TIME              = False
NUMERIC                 = True

SENSOR_EVENT_LOG_ENTITY = 'sensor.icloud3_event_log'

DEVICE_ATTRS_BASE       = {ATTR_LATITUDE: 0,
                           ATTR_LONGITUDE: 0,
                           ATTR_BATTERY: 0,
                           ATTR_BATTERY_LEVEL: 0,
                           ATTR_BATTERY_STATUS: '',
                           ATTR_GPS_ACCURACY: 0,
                           ATTR_VERTICAL_ACCURACY: 0,
                           ATTR_TIMESTAMP: ISO_TIMESTAMP_ZERO,
                           ATTR_ICLOUD_LOC_TIMESTAMP: ZERO_HHMMSS,
                           ATTR_TRIGGER: '',
                           ATTR_DEVICE_STATUS: '',
                           ATTR_LOW_POWER_MODE: '',
                           }
TRACE_ATTRS_BASE        = {ATTR_NAME: '',
                           ATTR_ZONE: '',
                           ATTR_LAST_ZONE: '',
                           ATTR_ZONE_TIMESTAMP: '',
                           ATTR_LATITUDE: 0,
                           ATTR_LONGITUDE: 0,
                           ATTR_TRIGGER: '',
                           ATTR_TIMESTAMP: ISO_TIMESTAMP_ZERO,
                           ATTR_ZONE_DISTANCE: 0,
                           ATTR_INTERVAL: 0,
                           ATTR_DIR_OF_TRAVEL: '',
                           ATTR_TRAVEL_DISTANCE: 0,
                           ATTR_WAZE_DISTANCE: '',
                           ATTR_CALC_DISTANCE: 0,
                           ATTR_LAST_LOCATED: '',
                           ATTR_LAST_UPDATE_TIME: '',
                           ATTR_NEXT_UPDATE_TIME: '',
                           ATTR_POLL_COUNT: '',
                           ATTR_INFO: '',
                           ATTR_BATTERY: 0,
                           ATTR_BATTERY_LEVEL: 0,
                           ATTR_GPS: 0,
                           ATTR_GPS_ACCURACY: 0,
                           ATTR_VERTICAL_ACCURACY: 0,
                           }

TRACE_ICLOUD_ATTRS_BASE = {CONF_NAME: '', 'deviceStatus': '',
                           ATTR_ISOLD: False,
                           ATTR_LATITUDE: 0,
                           ATTR_LONGITUDE: 0,
                           ATTR_ICLOUD_LOC_TIMESTAMP: 0,
                           ATTR_ICLOUD_HORIZONTAL_ACCURACY: 0,
                           ATTR_ICLOUD_VERTICAL_ACCURACY: 0,
                          'positionType': 'Wifi',
                          }

SENSOR_DEVICE_ATTRS     = ['zone',
                           'zone_name1',
                           'zone_name2',
                           'zone_name3',
                           'last_zone',
                           'last_zone_name1',
                           'last_zone_name2',
                           'last_zone_name3',
                           'zone_timestamp',
                           'base_zone',
                           'zone_distance',
                           'calc_distance',
                           'waze_distance',
                           'travel_time',
                           'dir_of_travel',
                           'interval',
                           'info',
                           'last_located',
                           'last_update',
                           'next_update',
                           'poll_count',
                           'travel_distance',
                           'trigger',
                           'battery',
                           'battery_status',
                           'gps_accuracy',
                           'vertical accuracy',
                           'badge',
                           'name',
                           ]

SENSOR_ATTR_FORMAT      = {'zone_distance': 'dist',
                           'calc_distance': 'dist',
                           'waze_distance': 'diststr',
                           'travel_distance': 'dist',
                           'battery': '%',
                           'dir_of_travel': 'title',
                           'altitude': 'm-ft',
                           'badge': 'badge',
                           }

#---- iPhone Device Tracker Attribute Templates ----- Gary -----------
SENSOR_ATTR_FNAME       = {'zone': 'Zone',
                           'zone_name1': 'Zone',
                           'zone_name2': 'Zone',
                           'zone_name3': 'Zone',
                           'last_zone': 'Last Zone',
                           'last_zone_name1': 'Last Zone',
                           'last_zone_name2': 'Last Zone',
                           'last_zone_name3': 'Last Zone',
                           'zone_timestamp': 'Zone Timestamp',
                           'base_zone': 'Base Zone',
                           'zone_distance': 'Zone Distance',
                           'calc_distance': 'Calc Dist',
                           'waze_distance': 'Waze Dist',
                           'travel_time': 'Travel Time',
                           'dir_of_travel': 'Direction',
                           'interval': 'Interval',
                           'info': 'Info',
                           'last_located': 'Last Located',
                           'last_update': 'Last Update',
                           'next_update': 'Next Update',
                           'poll_count': 'Poll Count',
                           'travel_distance': 'Travel Dist',
                           'trigger': 'Trigger',
                           'battery': 'Battery',
                           'battery_status': 'Battery Status',
                           'gps_accuracy': 'GPS Accuracy',
                           'vertical_accuracy': 'Vertical Accuracy',
                           'badge': 'Badge',
                           'name': 'Name',
                           }

SENSOR_ATTR_ICON        = {'zone': 'mdi:cellphone-iphone',
                           'last_zone': 'mdi:cellphone-iphone',
                           'base_zone': 'mdi:cellphone-iphone',
                           'zone_timestamp': 'mdi:restore-clock',
                           'zone_distance': 'mdi:map-marker-distance',
                           'calc_distance': 'mdi:map-marker-distance',
                           'waze_distance': 'mdi:map-marker-distance',
                           'travel_time': 'mdi:clock-outline',
                           'dir_of_travel': 'mdi:compass-outline',
                           'interval': 'mdi:clock-start',
                           'info': 'mdi:information-outline',
                           'last_located': 'mdi:restore-clock',
                           'last_update': 'mdi:restore-clock',
                           'next_update': 'mdi:update',
                           'poll_count': 'mdi:counter',
                           'travel_distance': 'mdi:map-marker-distance',
                           'trigger': 'mdi:flash-outline',
                           'battery': 'mdi:battery',
                           'battery_status': 'mdi:battery',
                           'gps_accuracy': 'mdi:map-marker-radius',
                           'altitude': 'mdi:image-filter-hdr',
                           'vertical_accuracy': 'mdi:map-marker-radius',
                           'badge': 'mdi:shield-account',
                           'name': 'mdi:account',
                           'entity_log': 'mdi:format-list-checkbox',
                           }

SENSOR_ID_NAME_LIST     = {'zon': 'zone',
                           'zon1': 'zone_name1',
                           'zon2': 'zone_name2',
                           'zon3': 'zone_name3',
                           'bzon': 'base_zone',
                           'lzon': 'last_zone',
                           'lzon1': 'last_zone_name1',
                           'lzon2': 'last_zone_name2',
                           'lzon3': 'last_zone_name3',
                           'zonts': 'zone_timestamp',
                           'zdis': 'zone_distance',
                           'cdis': 'calc_distance',
                           'wdis': 'waze_distance',
                           'tdis': 'travel_distance',
                           'ttim': 'travel_time',
                           'dir': 'dir_of_travel',
                           'intvl':  'interval',
                           'lloc': 'last_located',
                           'lupdt': 'last_update',
                           'nupdt': 'next_update',
                           'cnt': 'poll_count',
                           'info': 'info',
                           'trig': 'trigger',
                           'bat': 'battery',
                           'batstat': 'battery_status',
                           'alt': 'altitude',
                           'gpsacc': 'gps_accuracy',
                           'vacc': 'vertical_accuracy',
                           'badge': 'badge',
                           'name': 'name',
                           }


ATTR_TIMESTAMP_FORMAT    = '%Y-%m-%dT%H:%M:%S.%f'
APPLE_DEVICE_TYPES = ['iphone', 'ipad', 'ipod', 'watch', 'iwatch', 'icloud']

#icloud_update commands
CMD_ERROR    = 1
CMD_INTERVAL = 2
CMD_PAUSE    = 3
CMD_RESUME   = 4
CMD_WAZE     = 5

#Other constants
IOSAPP_DT_ENTITY = True
ICLOUD_DT_ENTITY = False
ICLOUD_LOCATION_DATA_ERROR = [False, 0, 0, '', ZERO_HHMMSS,
                              0, 0, '', '', '', \
                              False, ZERO_HHMMSS, 0, 0]
#General constants
HOME                    = 'home'
NOT_HOME                = 'not_home'
NOT_SET                 = 'not_set'
STATIONARY              = 'stationary'
AWAY_FROM               = 'Away'
PAUSED                  = 'Paused'
STATIONARY_LAT_90       = 90
STATIONARY_LONG_180     = 180
STATIONARY_ZONE_VISIBLE = True
STATIONARY_ZONE_HIDDEN  = False
STATIONARY_ZONE_HOME_OFFSET  = .00492   #Subtrace/add from home zone latitude to make stat zone location
EVENT_LOG_CLEAR_SECS    = 600           #Clear event log data interval
EVENT_LOG_CLEAR_CNT     = 15            #Number of recds to display when clearing event log


#Devicename config parameter file extraction
DI_DEVICENAME           = 0
DI_DEVICE_TYPE          = 1
DI_NAME                 = 2
DI_EMAIL                = 3
DI_BADGE_PICTURE        = 4
DI_DEVICENAME_IOSAPP    = 5
DI_DEVICENAME_IOSAPP_ID = 6
DI_SENSOR_IOSAPP_TRIGGER= 7
DI_ZONES                = 8
DI_SENSOR_PREFIX_NAME   = 9

#Waze status codes
WAZE_REGIONS      = ['US', 'NA', 'EU', 'IL', 'AU']
WAZE_USED         = 0
WAZE_NOT_USED     = 1
WAZE_PAUSED       = 2
WAZE_OUT_OF_RANGE = 3
WAZE_ERROR        = 4

#tracking_method config parameter being used
TRK_METHOD_FMF            = 'fmf'       #Find My Friends
TRK_METHOD_FAMSHR         = 'famshr'     #icloud Family-Sharing
TRK_METHOD_IOSAPP         = 'iosapp'    #HA IOS App v1.5x or v2.x
TRK_METHOD_IOSAPP1        = 'iosapp1'   #HA IOS App v1.5x only
TRK_METHOD_FMF_FAMSHR     = [TRK_METHOD_FMF, TRK_METHOD_FAMSHR]
TRK_METHOD_IOSAPP_IOSAPP1 = [TRK_METHOD_IOSAPP, TRK_METHOD_IOSAPP1]
TRK_METHOD_VALID          = [TRK_METHOD_FMF, TRK_METHOD_FAMSHR,
                             TRK_METHOD_IOSAPP, TRK_METHOD_IOSAPP1]

TRK_METHOD_NAME = {
    'fmf': 'Find My Friends',
    'famshr': 'Family Sharing',
    'iosapp': 'IOS App',
    'iosapp1': 'IOS App v1',
}
TRK_METHOD_SHORT_NAME = {
    'fmf': 'FmF',
    'famshr': 'FamShr',
    'iosapp': 'IOSApp',
    'iosapp1': 'IOSApp1',
}
DEVICE_TYPE_FNAME = {
    'iphone': 'iPhone',
    'phone': 'iPhone',
    'ipad': 'iPad',
    'iwatch': 'iWatch',
    'watch': 'iWatch',
    'ipod': 'iPod',
}
IOS_TRIGGERS_VERIFY_LOCATION = ['Background Fetch',
                                'Initial',
                                'Manual',
                                'Significant Location Update',
                                'Push Notification']
IOS_TRIGGERS_ENTER_ZONE      = ['Geographic Region Entered',
                                'iBeacon Region Entered']
IOS_TRIGGERS_ENTER_EXIT_IC3  = ['Geographic Region Entered',
                                'Geographic Region Exited',
                                'iBeacon Region Entered',
                                '@']
IOS_TRIGGERS_ACCEPT_LOCATION_STR = ['@', 'Enter', 'Exit', 'Push', 'Manual']

#If the location data is old during the _update_device_icloud routine,
#it will retry polling the device (or all devices) after 3 seconds,
#up to 4 times. If the data is still old, it will set the next normal
#interval to C_LOCATION_ISOLD_INTERVAL and keep track of the number of
#times it overrides the normal polling interval. If it is still old after
#C_MAX_LOCATION_ISOLD_CNT retries, the normal intervl will be used and
#the cycle starts over on the next poll. This will prevent a constant
#repolling if the location data is always old.
C_LOCATION_ISOLD_INTERVAL = 15
C_MAX_LOCATION_ISOLD_CNT = 4

#Lists to hold the group names, group objects and iCloud device configuration
#The ICLOUD3_GROUPS is filled in on each platform load, the GROUP_OBJS is
#filled in after the polling timer is setup.
ICLOUD3_GROUPS     = []
ICLOUD3_GROUP_OBJS = {}
ICLOUD_ACCT_DEVICE_CONFIG = {}
ICLOUD3_TRACKED_DEVICES   = {}

DEVICE_STATUS_SET = ['deviceModel', 'rawDeviceModel', 'deviceStatus',
                    'deviceClass', 'batteryLevel', 'id', 'lowPowerMode',
                    'deviceDisplayName', 'name', 'batteryStatus', 'fmlyShare',
                    'location',
                    'locationCapable', 'locationEnabled', 'isLocating',
                    'remoteLock', 'activationLocked', 'lockedTimestamp',
                    'lostModeCapable', 'lostModeEnabled', 'locFoundEnabled',
                    'lostDevice', 'lostTimestamp',
                    'remoteWipe', 'wipeInProgress', 'wipedTimestamp',
                    'isMac']

DEVICE_STATUS_CODES = {
    '200': 'online',
    '201': 'offline',
    '203': 'pending',
    '204': 'unregistered',
}

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_GROUP):  cv.slugify,
    vol.Optional(CONF_DEVICENAME): cv.slugify,
    vol.Optional(CONF_INTERVAL): cv.slugify,
    vol.Optional(CONF_COMMAND): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_GROUP, default='group'): cv.slugify,
    vol.Optional(CONF_TRACKING_METHOD, default='fmf'): cv.slugify,
    vol.Optional(CONF_MAX_IOSAPP_LOCATE_CNT, default=100): cv.string,
    vol.Optional(CONF_ENTITY_REGISTRY_FILE): cv.string,

    #-----►►General Attributes ----------
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='mi'): cv.slugify,
    vol.Optional(CONF_INZONE_INTERVAL, default='2 hrs'): cv.string,
    vol.Optional(CONF_MAX_INTERVAL, default=0): cv.string,
    vol.Optional(CONF_TRAVEL_TIME_FACTOR, default=.60): cv.string,
    vol.Optional(CONF_GPS_ACCURACY_THRESHOLD, default=100): cv.string,
    vol.Optional(CONF_OLD_LOCATION_THRESHOLD, default='2 min'): cv.string,
    vol.Optional(CONF_IGNORE_GPS_ACC_INZONE, default=True): cv.boolean,
    vol.Optional(CONF_HIDE_GPS_COORDINATES, default=False): cv.boolean,
    vol.Optional(CONF_LOG_LEVEL, default=''): cv.string,

    #-----►►Filter, Include, Exclude Devices ----------
    vol.Optional(CONF_TRACK_DEVICES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TRACK_DEVICE, default=[]): vol.All(cv.ensure_list, [cv.string]),

    #-----►►Waze Attributes ----------
    vol.Optional(CONF_DISTANCE_METHOD, default='waze'): cv.string,
    vol.Optional(CONF_WAZE_REGION, default='US'): cv.string,
    vol.Optional(CONF_WAZE_MAX_DISTANCE, default=1000): cv.string,
    vol.Optional(CONF_WAZE_MIN_DISTANCE, default=1): cv.string,
    vol.Optional(CONF_WAZE_REALTIME, default=False): cv.boolean,

    #-----►►Other Attributes ----------
    vol.Optional(CONF_STATIONARY_INZONE_INTERVAL, default='30 min'): cv.string,
    vol.Optional(CONF_STATIONARY_STILL_TIME, default='8 min'): cv.string,
    vol.Optional(CONF_SENSORS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EXCLUDE_SENSORS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_COMMAND): cv.string,
    })


#==============================================================================
#
#   SYSTEM LEVEL FUNCTIONS
#
#==============================================================================
def _combine_lists(parm_lists):
    '''
    Take a list of lists and return a single list of all of the items.
        [['a,b,c'],['d,e,f']] --> ['a','b','c','d','e','f']
    '''
    new_list = []
    for lists in parm_lists:
        lists_items = lists.split(',')
        for lists_item in lists_items:
            new_list.append(lists_item)

    return new_list

#--------------------------------------------------------------------
def _test(parm1, parm2):
    return '{}-{}'.format(parm1, parm2)

#--------------------------------------------------------------------
def TRACE(variable_name, variable1 = '+++', variable2 = '',
            variable3 = '', variable4 = ''):
    '''
    Display a message or variable in the HA log file
    '''
    if variable_name != '':
        if variable1 == '+++':
            value_str = "►►►► {}".format(variable_name)
        else:
            value_str = "►►►► {} = {} {} {} {}".format(
                variable_name,
                variable1,
                variable2,
                variable3,
                variable4)
        _LOGGER.info(value_str)

#--------------------------------------------------------------------
def instr(string, find_string):
    return string.find(find_string) >= 0

#--------------------------------------------------------------------
def isnumber(string):

    try:
        test_number = float(string)

        return True
    except:
        return False

#--------------------------------------------------------------------
def inlist(string, list_items):
    for item in list_items:
        if string.find(item) >= 0:
            return True

    return False

#==============================================================================
#
#   SETUP DEVICE_TRACKER SCANNER
#
#==============================================================================
def setup_scanner(hass, config: dict, see, discovery_info=None):
    """Set up the iCloud Scanner."""
    username        = config.get(CONF_USERNAME)
    password        = config.get(CONF_PASSWORD)
    #account_name    = config.get(CONF_ACCOUNT_NAME)
    group           = config.get(CONF_GROUP)
    base_zone       = config.get(CONF_BASE_ZONE)
    tracking_method = config.get(CONF_TRACKING_METHOD)
    track_devices   = config.get(CONF_TRACK_DEVICES)
    track_devices.extend(config.get(CONF_TRACK_DEVICE))
    log_level       = config.get(CONF_LOG_LEVEL)
    entity_registry_file  = config.get(CONF_ENTITY_REGISTRY_FILE)
    max_iosapp_locate_cnt = int(config.get(CONF_MAX_IOSAPP_LOCATE_CNT))

    #make sure the same group is not specified in more than one platform. If so,
    #append with a number
    if group in ICLOUD3_GROUPS or group == 'group':
        group = "{}{}".format(group, len(ICLOUD3_GROUPS)+1)
    ICLOUD3_GROUPS.append(group)
    ICLOUD3_TRACKED_DEVICES[group] = track_devices

    log_msg =("Setting up iCloud3 v{} device tracker for User: {}, "
            "Group: {}").format(
            VERSION,
            username,
            group)
    if HA_DEVICE_TRACKER_LEGACY_MODE:
        log_msg = ("{}, using device_tracker.legacy code").format(log_msg)
    _LOGGER.info(log_msg)

    if config.get(CONF_MAX_INTERVAL) == '0':
        inzone_interval_str = config.get(CONF_INZONE_INTERVAL)
    else:
        inzone_interval_str = config.get(CONF_MAX_INTERVAL)

    max_interval           = config.get(CONF_MAX_INTERVAL)
    gps_accuracy_threshold = config.get(CONF_GPS_ACCURACY_THRESHOLD)
    old_location_threshold_str = config.get(CONF_OLD_LOCATION_THRESHOLD)
    ignore_gps_accuracy_inzone_flag = config.get(CONF_IGNORE_GPS_ACC_INZONE)
    hide_gps_coordinates   = config.get(CONF_HIDE_GPS_COORDINATES)
    unit_of_measurement    = config.get(CONF_UNIT_OF_MEASUREMENT)

    stationary_inzone_interval_str = config.get(CONF_STATIONARY_INZONE_INTERVAL)
    stationary_still_time_str = config.get(CONF_STATIONARY_STILL_TIME)

    sensor_ids             = _combine_lists(config.get(CONF_SENSORS))
    exclude_sensor_ids     = _combine_lists(config.get(CONF_EXCLUDE_SENSORS))

    travel_time_factor     = config.get(CONF_TRAVEL_TIME_FACTOR)
    waze_realtime          = config.get(CONF_WAZE_REALTIME)
    distance_method        = config.get(CONF_DISTANCE_METHOD).lower()
    waze_region            = config.get(CONF_WAZE_REGION)
    waze_max_distance      = config.get(CONF_WAZE_MAX_DISTANCE)
    waze_min_distance      = config.get(CONF_WAZE_MIN_DISTANCE)
    if waze_region not in WAZE_REGIONS:
        log_msg = ("Invalid Waze Region ({}). Valid Values are: "
            "NA=US or North America, EU=Europe, IL=Isreal").format(waze_region)
        _LOGGER.error(log_msg)

        waze_region       = 'US'
        waze_max_distance = 0
        waze_min_distance = 0


    #Test
    #log_msg = ("----------------- Testing dir={}").format(icloud_dir_icloud)
    #_LOGGER.info(log_msg)
    #entity_reg_file_name = hass.helpers.storage.Store(ENTITY_REGISTRY_FILE_KEY, STORAGE_KEY)
    #log_msg = ("----------------- entity reg file={}").format(entity_reg_file_name)
    #_LOGGER.info(log_msg)
    #icloud_dir_icloud = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    #log_msg = ("----------------- iCloud storage dir={}").format(icloud_dir_icloud)
    #_LOGGER.info(log_msg)
    #Test

#----------------------------------------------
    icloud_group = Icloud(
        hass, see, username, password, group, base_zone,
        tracking_method, track_devices, entity_registry_file,
        max_iosapp_locate_cnt, inzone_interval_str,
        gps_accuracy_threshold, old_location_threshold_str,
        stationary_inzone_interval_str, stationary_still_time_str,
        ignore_gps_accuracy_inzone_flag, hide_gps_coordinates,
        sensor_ids, exclude_sensor_ids,
        unit_of_measurement, travel_time_factor, distance_method,
        waze_region, waze_realtime, waze_max_distance, waze_min_distance,
        log_level
        )

    ICLOUD3_GROUP_OBJS[group] = icloud_group


#--------------------------------------------------------------------

    def service_callback_update_icloud(call):
        """Call the update function of an iCloud group."""
        groups     = call.data.get(CONF_GROUP, ICLOUD3_GROUP_OBJS)
        devicename = call.data.get(CONF_DEVICENAME)
        command    = call.data.get(CONF_COMMAND)

        for group in groups:
            if group in ICLOUD3_GROUP_OBJS:
                ICLOUD3_GROUP_OBJS[group].service_handler_icloud_update(
                                    group, devicename, command)

    hass.services.register(DOMAIN, 'icloud3_update',
                service_callback_update_icloud, schema=SERVICE_SCHEMA)


#--------------------------------------------------------------------
    def service_callback__start_icloud3(call):
        """Reset an iCloud group."""
        groups = call.data.get(CONF_GROUP, ICLOUD3_GROUP_OBJS)
        for group in groups:
            if group in ICLOUD3_GROUP_OBJS:
                ICLOUD3_GROUP_OBJS[group]._start_icloud3()

    hass.services.register(DOMAIN, 'icloud3_restart',
                service_callback__start_icloud3, schema=SERVICE_SCHEMA)

#--------------------------------------------------------------------
    def service_callback_setinterval(call):
        """Call the update function of an iCloud group."""
        '''
        groups = call.data.get(CONF_GROUP, ICLOUD3_GROUP_OBJS)
        interval = call.data.get(CONF_INTERVAL)
        devicename = call.data.get(CONF_DEVICENAME)
        _LOGGER.warning("accounts=%s",accounts)
        _LOGGER.warning("devicename=%s",devicename)
        _LOGGER.warning("=%s",)

        for group in groups:
            if group in ICLOUD3_GROUP_OBJS:
                _LOGGER.warning("account=%s",account)
                ICLOUD3_GROUP_OBJS[group].service_handler_icloud_setinterval(
                                    account, interval, devicename)
        '''
        groups     = call.data.get(CONF_GROUP, ICLOUD3_GROUP_OBJS)
        interval   = call.data.get(CONF_INTERVAL)
        devicename = call.data.get(CONF_DEVICENAME)

        for group in groups:
            if group in ICLOUD3_GROUP_OBJS:
                ICLOUD3_GROUP_OBJS[group].service_handler_icloud_setinterval(
                                    group, interval, devicename)

    hass.services.register(DOMAIN, 'icloud3_set_interval',
                service_callback_setinterval, schema=SERVICE_SCHEMA)

#--------------------------------------------------------------------
    def service_callback_lost_iphone(call):
        """Call the lost iPhone function if the device is found."""
        groups = call.data.get(CONF_GROUP, ICLOUD3_GROUP_OBJS)
        devicename = call.data.get(CONF_DEVICENAME)
        for group in groups:
            if group in ICLOUD3_GROUP_OBJS:
                ICLOUD3_GROUP_OBJS[group].service_handler_lost_iphone(
                                    group, devicename)

    hass.services.register(DOMAIN, 'icloud3_lost_iphone',
                service_callback_lost_iphone, schema=SERVICE_SCHEMA)


#--------------------------------------------------------------------
    #Keep the old service calls for compatibility

    #hass.services.register(DOMAIN, 'icloud_update',
    #            service_callback_update_icloud, schema=SERVICE_SCHEMA)
    #hass.services.register(DOMAIN, 'icloud_restart',
    #            service_callback__start_icloud3, schema=SERVICE_SCHEMA)
    #hass.services.register(DOMAIN, 'icloud_set_interval',
    #            service_callback_setinterval, schema=SERVICE_SCHEMA)
    #hass.services.register(DOMAIN, 'icloud_lost_iphone',
    #            service_callback_lost_iphone, schema=SERVICE_SCHEMA)


    # Tells the bootstrapper that the component was successfully initialized
    return True


#====================================================================
class Icloud(DeviceScanner):
    """Representation of an iCloud account."""

    def __init__(self,
        hass, see, username, password, group, base_zone,
        tracking_method, track_devices, entity_registry_file,
        max_iosapp_locate_cnt, inzone_interval_str,
        gps_accuracy_threshold, old_location_threshold_str,
        stationary_inzone_interval_str, stationary_still_time_str,
        ignore_gps_accuracy_inzone_flag, hide_gps_coordinates,
        sensor_ids, exclude_sensor_ids,
        unit_of_measurement, travel_time_factor, distance_method,
        waze_region, waze_realtime, waze_max_distance, waze_min_distance,
        log_level
        ):


        """Initialize an iCloud account."""
        self.hass                = hass
        self.username            = username
        self.username_base       = username.split('@')[0]
        self.password            = password
        self.api                 = None
        self.group               = group
        self.base_zone           = HOME
        self.entity_registry_file= entity_registry_file
        self.see                 = see
        self.verification_code   = None
        self.trusted_device      = None
        self.trusted_device_id   = None
        self.valid_trusted_device_ids = None
        self.tracking_method_config   = tracking_method

        self.max_iosapp_locate_cnt = max_iosapp_locate_cnt
        self._start_icloud3_group_request_flag   = False
        self._start_icloud3_group_inprocess_flag = False
        self.authenticated_time    = ''

        self._initialize_debug_control(log_level)

        self.attributes_initialized_flag = False
        self.track_devices               = track_devices
        self.distance_method_waze_flag   = (distance_method.lower() == 'waze')
        self.inzone_interval             = self._time_str_to_secs(inzone_interval_str)
        self.gps_accuracy_threshold      = int(gps_accuracy_threshold)
        self.old_location_threshold      = self._time_str_to_secs(old_location_threshold_str)
        self.ignore_gps_accuracy_inzone_flag = ignore_gps_accuracy_inzone_flag
        self.check_gps_accuracy_inzone_flag = not self.ignore_gps_accuracy_inzone_flag
        self.hide_gps_coordinates        = hide_gps_coordinates
        self.sensor_ids                  = sensor_ids
        self.exclude_sensor_ids          = exclude_sensor_ids
        self.unit_of_measurement         = unit_of_measurement
        self.travel_time_factor          = float(travel_time_factor)
        self.e_seconds_local_offset_secs = 0
        self.waze_region                 = waze_region
        self.waze_min_distance           = waze_min_distance
        self.waze_max_distance           = waze_max_distance
        self.waze_realtime               = waze_realtime
        self.stationary_inzone_interval_str = stationary_inzone_interval_str
        self.stationary_still_time_str   = stationary_still_time_str

        #define & initialize fields to carry across icloud3 restarts     
        self._define_event_log_fields()
        self._define_usage_counters()            

        #add HA event that will call the _polling_loop_5_sec_icloud function
        #on a 5-second interval. The interval is offset by 1-second for each
        #group to avoid update conflicts.
        self.initial_startup_flag = True
        if self._start_icloud3():
            track_utc_time_change(self.hass, self._polling_loop_5_sec_device,
                    second=[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])

        self.initial_startup_flag = False
#--------------------------------------------------------------------
    def _start_icloud3(self):
        """
        Start iCloud3, Define all variables & tables, Initialize devices
        """

        #check to see if restart is in process
        if self._start_icloud3_group_inprocess_flag:
            return

        try:
            start_timer = time.time()
            self._initialize_um_formats(self.unit_of_measurement)
            self._define_device_fields()
            self._define_device_status_fields()
            self._define_device_tracking_fields()
            
            if self.initial_startup_flag:
                start_restart_msg = 'Starting'
            else:
                start_restart_msg = 'Restarting'
            event_msg = (f"^^^ {dt_util.now().strftime('%A, %b %d')}, " 
                        f"{start_restart_msg} iCloud3 v{VERSION}")
            self._save_event("*", event_msg)
            
            event_msg = (f"Initializing v{VERSION} > Stage 1, Preparing iCloud3")
            self._save_event_halog_info("*", event_msg)
            
            self._define_tracking_control_fields()
            self._setup_tracking_method(self.tracking_method_config)
            self._initialize_zone_tables()
            self._define_stationary_zone_fields(self.stationary_inzone_interval_str,
                        self.stationary_still_time_str)
                        
            self._initialize_waze_fields(self.waze_region, self.waze_min_distance,
                        self.waze_max_distance, self.waze_realtime)
            
            self._start_icloud3_group_request_flag   = False
            self._start_icloud3_group_inprocess_flag = True

            if len(self.count_update_iosapp) > 0:
                for devicename in self.count_update_iosapp:
                    event_msg = ("Metrics: {}").format(
                        self._format_usage_counts(devicename))
                    self._save_event(devicename, event_msg)

            
            event_msg = (f"Initializing v{VERSION} > Stage 2, Verify iCloud Location Service")
            self._save_event_halog_info("*", event_msg)

            event_msg = ("iCloud3 Tracking Method: {}").format(self.trk_method_name)
            self._save_event_halog_info("*", event_msg)

        except Exception as err:
            _LOGGER.exception(err)

        self._initialize_pyicloud_device_api()

        event_msg = (f"Initializing v{VERSION} > Stage 3, Set up tracked devices")
        self._save_event_halog_info("*", event_msg)

        try:
            self.this_update_secs     = self._time_now_secs()
            self.icloud3_started_secs = self.this_update_secs

            self._define_device_tracking_fields()
            self._setup_tracked_devices_config_parm(self.track_devices)
            if self.initial_startup_flag:
                self._define_sensor_fields()
            
            if self.CURRENT_TRK_METHOD_FMF:
                self._setup_tracked_devices_for_fmf()

            elif self.CURRENT_TRK_METHOD_FAMSHR:
                self._setup_tracked_devices_for_famshr()

            elif self.CURRENT_TRK_METHOD_IOSAPP:
                self._setup_tracked_devices_for_iosapp()


            self.track_devicename_list == ''
            for devicename in self.devicename_verified:
                error_log_msg = None

                #Devicename config parameter is OK, now check to make sure the
                #entity for device name has been setup by iosapp correctly.
                #If the devicename is valid, it will be tracked
                if self.devicename_verified.get(devicename):
                    self.tracking_device_flag[devicename] = True
                    self.tracked_devices.append(devicename)

                    self.track_devicename_list = '{}, {}'.format(
                        self.track_devicename_list,
                        devicename)
                    if self.iosapp_version.get(devicename) == 2:
                        self.track_devicename_list = '{}({})'.format(
                            self.track_devicename_list,
                            self.devicename_iosapp.get(devicename))
                    event_msg_prefix = ""

                #If the devicename is not valid, it will not be tracked
                else:
                    event_msg_prefix = "Not "

                event_msg = ("{}Tracking ({}) > {}({})").format(
                    event_msg_prefix,
                    self.trk_method_short_name,
                    devicename,
                    self.friendly_name.get(devicename))
                if self.fmf_devicename_email.get(devicename):
                    event_msg = "{} via {}".format(
                        event_msg,
                        self.fmf_devicename_email.get(devicename))

                if error_log_msg:
                    self._save_event_halog_error(devicename, event_msg)
                    self._save_event_halog_error(devicename, error_log_msg)
                    
                else:
                    self._save_event_halog_info(devicename, event_msg)

                    if self.iosapp_version.get(devicename) == 1:
                        event_msg = "IOS App v1 monitoring > device_tracker.{}".format(
                            devicename)
                        self._save_event_halog_info(devicename, event_msg)
                    elif self.iosapp_version.get(devicename) == 2:
                        event_msg = ("IOS App v2 monitoring > device_tracker.{}, "
                            "sensor.{}").format(
                            self.devicename_iosapp.get(devicename),
                            self.iosapp_v2_last_trigger_entity.get(devicename))
                        self._save_event_halog_info(devicename, event_msg)
                        
            #Now that the devices have been set up, finish setting up
            #the Event Log Sensor
            if self.initial_startup_flag:
                self._setup_event_log_base_attrs()
                self._setup_sensors_custom_list()
            
            #nothing to do if no devices to track
            if self.track_devicename_list == '':
                event_msg = ("iCloud3 Error for {} ({}) > No devices to track. "
                    "Setup aborted.").format(
                    self.username, self.group)
                self._save_event_halog_error("*", event_msg)
                
                self._update_event_log_sensor_line_items("*")
                return False


            self.track_devicename_list = '{}'.format(self.track_devicename_list[1:])
            event_msg = ("Tracking Devices > {}").format(
                self.track_devicename_list)
            self._save_event_halog_info("*", event_msg)

            for devicename in self.tracked_devices:
                if len(self.track_from_zone.get(devicename)) > 1:
                    w = str(self.track_from_zone.get(devicename))
                    w = w.replace("[", "")
                    w = w.replace("]", "")
                    w = w.replace("'", "")
                    event_msg = "Tracking from zones > {}".format(w)
                    self._save_event(devicename, event_msg)
                    
                event_msg = (f"Initializing v{VERSION} > Stage 4, "
                    "Set up {}").format(devicename)
                self._save_event_halog_info(devicename, event_msg)

                self._initialize_device_fields(devicename)
                self._initialize_device_tracking_fields(devicename)
                self._initialize_usage_counters(devicename)
                self._initialize_device_zone_fields(devicename)
                
                #if devicename in self.sensor_prefix_name:
                if self.initial_startup_flag:
                    self._setup_sensor_base_attrs(devicename)

                #check to see if devicename's stationary zone already exists
                #if so, use that location. If not, use home zone +.0005
                zone_name = self._format_zone_name(devicename, STATIONARY)
                if zone_name in self.zone_lat:
                    latitude  = self.zone_lat.get(zone_name)
                    longitude = self.zone_long.get(zone_name)
                else:
                    latitude  = self.stat_zone_base_lat
                    longitude = self.stat_zone_base_long

                self._update_stationary_zone(
                    devicename,
                    latitude,
                    longitude,
                    STATIONARY_ZONE_HIDDEN)
                self.in_stationary_zone_flag[devicename] = False

                #Initialize the new attributes
                kwargs = self._setup_base_kwargs(devicename,
                            self.zone_home_lat, self.zone_home_long, 0, 0)
                attrs  = self._initialize_attrs(devicename)

                self._update_device_attributes(
                    devicename,
                    kwargs,
                    attrs,
                    '_start_icloud3')
                    
                if self.initial_startup_flag:    
                    self._update_device_sensors(devicename, kwargs)
                    self._update_device_sensors(devicename, attrs)

            self._update_event_log_sensor_line_items(self.tracked_devices[0])

            #Everying reset. Now do an iCloud update to set up the device info.
            event_msg = (f"Initializing v{VERSION} > Stage 5, Locating devices")
            self._save_event_halog_info("*", event_msg)

            if self.CURRENT_TRK_METHOD_FMF_FAMSHR:
                self._start_icloud3_group_inprocess_flag = False
                self._update_device_icloud('Initializing location')

        except Exception as err:
            _LOGGER.exception(err)

        self._start_icloud3_group_inprocess_flag = False
        event_msg = (f"Initializing v{VERSION} > Startup Complete, "
                     f" Took {round(time.time()-start_timer, 2)}s")
        self._save_event_halog_info("*", event_msg)
                
        return True

#########################################################
#
#   This function is called every 5 seconds by HA. Cycle through all
#   of the iCloud devices to see if any of the ones being tracked need
#   to be updated. If so, we might as well update the information for
#   all of the devices being tracked since PyiCloud gets data for
#   every device in the account
#
#########################################################

    def _polling_loop_5_sec_device(self, now):
        """Keep the API alive. Will be called by HA every 15 seconds"""

        try:
            fct_name = "_polling_loop_5_sec_device"

            if self._start_icloud3_group_request_flag:    #via service call
                self._start_icloud3()

            elif self.any_device_being_updated_flag:
                return

        except Exception as err:
            _LOGGER.exception(err)
            return

        self.this_update_secs = self._time_now_secs()
        count_reset_timer     = dt_util.now().strftime('%H:%M:%S')
        this_minute           = int(dt_util.now().strftime('%M'))
        this_5sec_loop_second = int(dt_util.now().strftime('%S'))

        #Reset counts on new day, check for daylight saving time new offset
        if count_reset_timer.endswith(':00:00'):
            for devicename in self.tracked_devices:
                event_msg = ("Metrics: {}").format(
                        self._format_usage_counts(devicename))
                self._save_event(devicename, event_msg)

        if count_reset_timer == '00:00:00':
            for devicename in self.tracked_devices:
                devicename_zone = self._format_devicename_zone(devicename, HOME)

                event_msg = ("^^^ {}, iCloud3 v{} Daily Summary").format(
                    dt_util.now().strftime('%A, %b %d'), VERSION)
                self._save_event_halog_info(devicename, event_msg)

                event_msg = ("Tracking Devices > {}").format(
                    self.track_devicename_list)
                self._save_event_halog_info(devicename, event_msg)

                if self.iosapp_version.get(devicename) == 1:
                    event_msg = "IOS App v1 monitoring > device_tracker.{}".format(
                        devicename)
                    self._save_event_halog_info(devicename, event_msg)
                elif self.iosapp_version.get(devicename) == 2:
                    event_msg = ("IOS App v2 monitoring > device_tracker.{}, "
                        "sensor.{}").format(
                        self.devicename_iosapp.get(devicename),
                        self.iosapp_v2_last_trigger_entity.get(devicename))
                    self._save_event_halog_info(devicename, event_msg)

                self.event_cnt[devicename]              = 0
                self.count_update_iosapp[devicename]    = 0
                self.count_update_icloud[devicename]    = 0
                self.count_update_ignore[devicename]    = 0
                self.count_request_iosapp_update[devicename] = 0
                self.count_state_changed[devicename]    = 0
                self.count_trigger_changed[devicename]  = 0
                self.iosapp_stat_zone_action_msg_cnt[devicename]= 0

            #Reset each night to get fresh data next time
            for devicename_zone in self.waze_distance_history:
                self.waze_distance_history[devicename_zone] = ''

        elif count_reset_timer == '01:00:00':
            self._calculate_time_zone_offset()

        try:
            if self.this_update_secs >= self.event_log_chear_secs:
                self._update_event_log_sensor_line_items('clear_log_items')

            for devicename in self.tracked_devices:
                devicename_zone = self._format_devicename_zone(devicename, HOME)

                if (self.tracking_device_flag.get(devicename) is False or
                   self.next_update_time.get(devicename_zone) == PAUSED):
                    continue

                update_via_iosapp_flag = False
                update_via_icloud_flag = False
                self.state_change_flag[devicename] = False

                #get tracked_devie (device_tracker.<devicename>) state & attributes
                #icloud & ios app v1 use this entity
                entity_id     = self.device_tracker_entity.get(devicename)
                current_state = self._get_current_state(entity_id)
                dev_attrs     = self._get_device_attributes(entity_id)
                #Extract only attrs needed to update the device
                dev_attrs_avail    = {k: v for k, v in dev_attrs.items() \
                                          if k in DEVICE_ATTRS_BASE}
                dev_data           = {**DEVICE_ATTRS_BASE, **dev_attrs_avail}

                dev_latitude       = dev_data[ATTR_LATITUDE]
                dev_longitude      = dev_data[ATTR_LONGITUDE]
                dev_gps_accuracy   = dev_data[ATTR_GPS_ACCURACY]
                dev_battery        = dev_data[ATTR_BATTERY_LEVEL]
                dev_trigger        = dev_data[ATTR_TRIGGER]
                dev_timestamp_secs = self._timestamp_to_secs(dev_data[ATTR_TIMESTAMP])
                v2_dev_attrs       = None

                #iosapp v2 uses the device_tracker.<devicename>_# entity for
                #location info and sensor.<devicename>_last_update_trigger entity
                #for trigger info. Get location data and trigger.
                #Use the trigger/timestamp if timestamp is newer than current
                #location timestamp.

                if self.iosapp_version.get(devicename) == 2:
                    update_via_v2_flag = False
                    entity_id    = self.device_tracker_entity_iosapp.get(devicename)
                    v2_state     = self._get_current_state(entity_id)
                    v2_dev_attrs = self._get_device_attributes(entity_id)

                    if ATTR_LATITUDE not in v2_dev_attrs:
                        self.iosapp_version[devicename] = 1
                        event_msg = ("iCloud3 Error: IOS App v2 Entity {} does not "
                            "contain location attributes (latitude, longitude). "
                            "Refresh & restart IOS App on device, "
                            "request a Manual Refresh, check Developer Tools>States "
                            "entity for location attributes, check HA "
                            "integrations for the entity. Restart HA or issue "
                            "'device_tracker.icloud3_reset' Service Call. "
                            "Reverting to IOS App v1.").format(entity_id)
                        self._save_event_halog_error(devicename, event_msg)
                        continue

                    v2_state_changed_time, v2_state_changed_secs = \
                            self._get_entity_last_changed_time(entity_id)

                    v2_trigger,  v2_trigger_changed_time, v2_trigger_changed_secs = \
                            self._get_iosappv2_device_sensor_trigger(devicename)

                    #self._trace_device_attributes(devicename, 'dev_attrs', devicename, dev_attrs)
                    #self._trace_device_attributes(devicename, 'v2_attrs ', entity_id, v2_dev_attrs)

                    #Initialize if first time through
                    if self.last_v2_trigger.get(devicename) == '':
                        self.last_v2_state[devicename]                = v2_state 
                        self.last_v2_state_changed_time[devicename]   = v2_state_changed_time
                        self.last_v2_state_changed_secs[devicename]   = v2_state_changed_secs
                        self.last_v2_trigger[devicename]              = v2_trigger
                        self.last_v2_trigger_changed_time[devicename] = v2_trigger_changed_time
                        self.last_v2_trigger_changed_secs[devicename] = v2_trigger_changed_secs

                    update_reason = ""
                    ios_update_reason = ""
                    if (v2_state != self.last_v2_state.get(devicename) and \
                            v2_state_changed_secs > dev_timestamp_secs):
                        update_via_v2_flag = True
                        ios_update_reason = "StateChange-{}".format(v2_state)

                    #Bypass if trigger contains ic3 date stamp suffix (@hhmmss)
                    #elif v2_trigger.find('@') >= 0:
                    elif instr(v2_trigger, '@'):
                        ios_update_reason = "disarded-already processed `{}`{}".format(v2_trigger,v2_trigger.find('@'))
                        pass

                    elif (v2_trigger != self.last_v2_trigger.get(devicename)):
                        update_via_v2_flag = True
                        ios_update_reason = "TriggerChange-{}".format(v2_trigger)

                    elif (v2_trigger_changed_secs > self.last_v2_trigger_changed_secs.get(devicename)):
                        update_via_v2_flag = True
                        ios_update_reason = "TriggerTime-{}".format(
                            self._secs_to_time(v2_trigger_changed_secs))

                    #if self.log_level_debug_flag or self.log_level_eventlog_flag:
                    debug_msg = ("IOSAPP Monitor > {}, LastTrigger-{}, "
                        "StateChg-`{}` to `{}`, Time(ic3~ios)-({}~{}), "
                        "Trigger(ic3~ios)-({}~{}@{}), GPS-({}, {})").format(
                        ios_update_reason, 
                        self._secs_to_time(self.last_v2_trigger_changed_secs.get(devicename)),
                        self.last_v2_state.get(devicename),
                        v2_state,
                        self._secs_to_time(dev_timestamp_secs),
                        self._secs_to_time(v2_state_changed_secs),
                        dev_trigger,
                        v2_trigger,
                        self._secs_to_time(v2_trigger_changed_secs),
                        round(v2_dev_attrs[ATTR_LATITUDE], 6),
                        round(v2_dev_attrs[ATTR_LONGITUDE], 6))
                        
                    if (update_via_v2_flag and debug_msg != self.last_debug_msg.get(devicename)):
                        self.last_debug_msg[devicename] = debug_msg
                        self.log_debug_msg(devicename, debug_msg)
                        self._save_event(devicename, debug_msg)
                        
                        
                    if update_via_v2_flag:
                        age = v2_trigger_changed_secs - self.this_update_secs
                        current_state            = v2_state
                        dev_latitude             = round(v2_dev_attrs[ATTR_LATITUDE], 6)
                        dev_longitude            = round(v2_dev_attrs[ATTR_LONGITUDE], 6)
                        dev_gps_accuracy         = v2_dev_attrs[ATTR_GPS_ACCURACY]
                        dev_battery              = v2_dev_attrs[ATTR_BATTERY_LEVEL]
                        dev_trigger              = v2_trigger
                        dev_timestamp_secs       = v2_trigger_changed_secs
                        dev_data[ATTR_LATITUDE]  = dev_latitude
                        dev_data[ATTR_LONGITUDE] = dev_longitude
                        dev_data[ATTR_GPS_ACCURACY]  = dev_gps_accuracy
                        dev_data[ATTR_BATTERY_LEVEL] = dev_battery
                        dev_data[ATTR_ALTITUDE]      = self._get_attr(v2_dev_attrs, ATTR_ALTITUDE, NUMERIC)
                        dev_data[ATTR_VERTICAL_ACCURACY] = \
                                self._get_attr(v2_dev_attrs, ATTR_VERTICAL_ACCURACY, NUMERIC)

                        self.last_v2_state[devicename]                = v2_state
                        self.last_v2_state_changed_time[devicename]   = v2_state_changed_time
                        self.last_v2_state_changed_secs[devicename]   = v2_state_changed_secs
                        self.last_v2_trigger[devicename]              = v2_trigger
                        self.last_v2_trigger_changed_time[devicename] = v2_trigger_changed_time
                        self.last_v2_trigger_changed_secs[devicename] = v2_trigger_changed_secs


                #Add update time onto trigger if it is not there already. IOS App
                #will wipe time out and cause an update to occur.

                self.last_located_secs[devicename] = dev_timestamp_secs
                current_zone = self._format_zone_name(devicename, current_state)

                if (self.CURRENT_TRK_METHOD_IOSAPP and
                        self.zone_current.get(devicename) == ''):
                    update_via_iosapp_flag = True
                    update_reason = ("Initialize Location with IOS App")

                #device_tracker.see svc all from automation wipes out
                #latitude and longitude. Reset via icloud update.
                elif dev_latitude == 0:
                    update_via_icloud_flag = True
                    self.next_update_secs[devicename_zone] = 0

                    update_reason = "GPS data = 0 {}-{}".format(
                         self.state_last_poll.get(devicename), current_state)
                    dev_trigger = "RefreshLocation"

                #if lots of accuracy errors. wait and process on 15-second icloud poll
                elif (self.location_isold_cnt.get(devicename) > 5 or
                        self.poor_gps_accuracy_cnt.get(devicename) > 5):
                    event_msg = "Discarding > Old data or Poor GPS"
                    self._save_event(devicename, event_msg)
                    continue

                #Update the device if it wasn't completed last time.
                elif (self.state_last_poll.get(devicename) == NOT_SET):
                    update_via_icloud_flag = True
                    dev_trigger  = "Retry Update"
                    update_reason = ("iCloud3 Restart not completed, "
                        "retrying location update")
                    self._save_event(devicename, update_reason)

                #The state can be changed via device_tracker.see service call
                #with a different location_name in an automation or by an
                #ios app notification that a zone is entered or exited. If
                #by the ios app, the trigger is 'Geographic Region Exited' or
                #'Geographic Region Entered'. In iosapp 2.0, the state is
                #changed without a trigger being posted and will be picked
                #up here anyway.
                elif (current_state != self.state_last_poll.get(devicename)):
                    self.state_change_flag[devicename] = True
                    update_via_iosapp_flag             = True
                    self.count_state_changed[devicename] += 1
                    update_reason = "State Change detected > {} to {}".format(
                         self.state_last_poll.get(devicename),
                         current_state)
                    self._save_event(devicename, update_reason)

                elif dev_trigger != self.trigger.get(devicename):
                    update_via_iosapp_flag = True
                    self.count_trigger_changed[devicename] += 1
                    update_reason = "Trigger Change detected > {}@{}".format(
                        dev_trigger, 
                        self._secs_to_time(v2_trigger_changed_secs))
                    self._save_event(devicename, update_reason)

                else:
                    update_reason = "Not updated, trigger-{}".format(dev_trigger)

                self.trigger[devicename] = dev_trigger


                #Update because of state or trigger change.
                #Accept the location data as it was sent by ios if the trigger
                #is for zone enter, exit, manual or push notification,
                #or if the last trigger was already handled by ic3 ( an '@hhmmss'
                #was added to it.
                #If the trigger was sometning else (Signigicant Location Change,
                #Background Fetch, etc, check to make sure it is not old or
                #has poor gps info.
                if update_via_iosapp_flag:
                    #self._trace_device_attributes(
                    #        devicename, '5sPoll', update_reason, dev_attrs)

                    dist_from_zone_m = self._current_zone_distance_m(
                                devicename,
                                current_zone,
                                dev_latitude,
                                dev_longitude)

                    #current_zone_radius_km = self.zone_radius_km.get(
                    #            current_zone, 
                    #            self.zone_radius_km.get(HOME))
                    current_zone_radius_m = self.zone_radius_m.get(
                                current_zone, 
                                self.zone_radius_m.get(HOME))

                    if dev_trigger in IOS_TRIGGERS_ENTER_ZONE:
                        if (current_zone in self.zone_lat and
                                dist_from_zone_m > self.zone_radius_m.get(current_zone)*2 and
                                dist_from_zone_m < 999999):
                            event_msg = ("Conflicting enter zone trigger, "
                                "Moving into zone > "
                                "Zone-{}, Dist-{}m, ZoneVerifyDist-{}m, "
                                "GPS-({}, {})").format(
                                current_zone,
                                dist_from_zone_m,
                                self.zone_radius_m.get(current_zone)*2,
                                dev_latitude,
                                dev_longitude)

                            self._save_event_halog_info(devicename, event_msg)

                            dev_latitude             = self.zone_lat.get(current_zone)
                            dev_longitude            = self.zone_long.get(current_zone)
                            dev_data[ATTR_LATITUDE]  = dev_latitude
                            dev_data[ATTR_LONGITUDE] = dev_longitude

                    #Check info if Background Fetch, Significant Location Update,
                    #Push, Manual, Initial
                    elif (dev_trigger in IOS_TRIGGERS_VERIFY_LOCATION):
                        old_location_flag = self._check_location_isold(
                                devicename,
                                False,
                                dev_timestamp_secs)

                        #If old location, discard
                        if old_location_flag:
                            update_via_iosapp_flag = False
                            ios_update_reason      = None
                            location_age =self._secs_since(dev_timestamp_secs)

                            event_msg = ("Discarding > Old location, Located-{} ({} ago, "
                                "GPS-({}, {}), GPSAccuracy-{}").format(
                                self._secs_to_time(dev_timestamp_secs),
                                self._secs_to_time_str(location_age),
                                dev_latitude,
                                dev_longitude,
                                dev_gps_accuracy)
                            self._save_event_halog_info(devicename, event_msg)

                        #If got these triggers and not old location check a few
                        #other things
                        else:
                            update_reason = "{} trigger".format(dev_trigger)
                            self.last_iosapp_trigger[devicename] = dev_trigger

                            #if the zone is a stationary zone and no exit trigger,
                            #the zones in the ios app may not be current.
                            if (dist_from_zone_m >= current_zone_radius_m * 2 and
                                    instr(current_zone, STATIONARY) and 
                                    instr(self.zone_last.get(devicename), STATIONARY)):
                                event_msg = ("Outside Stationary Zone without "
                                    "Exit Trigger > Check iOS App Configuration/"
                                    "Location for stationary zones. Force app "
                                    "refresh to reload zones if necessary. "
                                    f"Dist-{round(dist_from_zone_m, 2)}km, "
                                    f"StatZoneTestDist-{current_zone_radius_m * 2}m")
                                self._save_event_halog_info(devicename, event_msg) 
                                
                                self.iosapp_stat_zone_action_msg_cnt[devicename] += 1
                                if self.iosapp_stat_zone_action_msg_cnt.get(devicename) < 5:
                                    if self.iosapp_version[devicename] == 1:
                                        entity_id = f"ios_{devicename}"
                                    else:
                                        entity_id = f"mobile_app_{devicename}"
                                    service_data = {
                                        "title": "iCloud3/iOSApp Zone Action Needed", 
                                        "message": "The iCloud3 Stationary Zone may "\
                                            "not be loaded in the iOSApp. Force close "\
                                            "the iOSApp from the iOS App Switcher. "\
                                            "Then restart the iOSApp to reload the HA zones. "\
                                            f"Dist-{round(dist_from_zone_m, 2)}km, "
                                            f"StatZoneTestDist-{current_zone_radius_m * 2}m",
                                        "data": {"subtitle": "Stationary Zone Exit "\
                                            "Trigger was not received"}}
                                    self.hass.services.call("notify", entity_id, service_data)

                            #discard if between 0-zone _radius*4 due to gps errors
                            elif dist_from_zone_m <= current_zone_radius_m * 4:
                                update_via_iosapp_flag = False
                                ios_update_reason      = None

                                event_msg = ("Discarding, No Exit Zone trigger, "
                                    "Keeping in zone > Zone-{}, Dist-{}m, "
                                    "DiscardInsideRadius-{}m").format(
                                    self.state_last_poll.get(devicename),
                                    dist_from_zone_m,
                                    current_zone_radius_m*4)
                                self._save_event_halog_info(devicename, event_msg)

                            #update via icloud to verify location if less than home_radius*100
                            elif (dist_from_zone_m <= current_zone_radius_m * 100 and 
                                    self.CURRENT_TRK_METHOD_FMF_FAMSHR):
                                event_msg = ("iCloud being called to verify location > "
                                    "Zone-{}, Dist-{}m, ZoneVerifyDist-{}m, "
                                    "GPS-({}, {})").format(
                                    current_zone,
                                    dist_from_zone_m,
                                    current_zone_radius_m*100,
                                    dev_latitude,
                                    dev_longitude)
                                self._save_event_halog_info(devicename, event_msg)
                                update_via_iosapp_flag = False
                                update_via_icloud_flag = True

                    if (dev_data[ATTR_LATITUDE] == None or dev_data[ATTR_LONGITUDE] == None):
                        update_via_iosapp_flag = False
                        update_via_icloud_flag = True

                if update_via_iosapp_flag:
                    self.state_this_poll[devicename]    = current_state
                    self.iosapp_update_flag[devicename] = True

                    self._update_device_iosapp_trigger(update_reason, devicename, dev_data)

                elif update_via_icloud_flag and self.CURRENT_TRK_METHOD_FMF_FAMSHR:
                    self._update_device_icloud(update_reason, devicename)

                elif (self.iosapp_version.get(devicename) == 2 and
                        update_via_v2_flag and
                        ios_update_reason):
                    event_msg = "Discarding > Update already completed `{}`".format(ios_update_reason)
                    self._save_event(devicename, event_msg)

                if devicename in self.track_from_zone:
                    for zone in self.track_from_zone.get(devicename):
                        devicename_zone = self._format_devicename_zone(devicename, zone)
                        if devicename_zone in self.next_update_secs:
                            age_secs = self._secs_to(self.next_update_secs.get(devicename_zone))
                            if (age_secs <= 90 and age_secs >= -15):
                                self._display_time_till_update_info_msg(
                                    devicename_zone,
                                    age_secs)

                if self.device_being_updated_flag.get(devicename):
                    event_msg = ("Retrying last update with {}").format(
                        self.trk_method_short_name)
                    self._save_event(devicename, event_msg)
                    self._retry_update(devicename)

                if update_via_iosapp_flag or update_via_icloud_flag:
                    self.device_being_updated_flag[devicename] = False
                    self.state_change_flag[devicename]         = False
                    self.log_debug_msgs_trace_flag             = False
                    self.update_in_process_flag                = False

        except Exception as err:
            _LOGGER.exception(err)
            log_msg = ("Device Update Error, Error={}").format(ValueError)
            self.log_error_msg(log_msg)

        self.update_in_process_flag    = False
        self.log_debug_msgs_trace_flag = False

        #Cycle thru all devices and check to see if devices need to be
        #updated via every 15 seconds
        if (((this_5sec_loop_second) % 15) == 0):
            self._polling_loop_15_sec_icloud(now)

#--------------------------------------------------------------------
    def _retry_update(self, devicename):
        #This flag will be 'true' if the last update for this device
        #was not completed. Do another update now.
        self.device_being_updated_retry_cnt[devicename] = 0
        while (self.device_being_updated_flag.get(devicename) and
            self.device_being_updated_retry_cnt.get(devicename) < 4):
            self.device_being_updated_retry_cnt[devicename] += 1

            log_msg = ("{} Retrying Update, Update was not "
                "completed in last cycle, Retry #{}").format(
                    self._format_fname_devtype(devicename),
                self.device_being_updated_retry_cnt.get(devicename))
            self.log_info_msg(log_msg)

            self.device_being_updated_flag[devicename] = True
            self.log_debug_msgs_trace_flag = True

            self._wait_if_update_in_process()
            update_reason = "Device-retry {}".format(
                self.device_being_updated_retry_cnt.get(devicename))

            self._update_device_icloud(update_reason, devicename)

#########################################################
#
#   Cycle through all iCloud devices and update the information for the devices
#   being tracked
#     ●►●◄►●▬▲▼◀►►●◀ oPhone=►▶
#########################################################
    def _update_device_iosapp_trigger(self, update_reason, devicename, dev_data):
        """

        """

        if self._start_icloud3_group_inprocess_flag:
            return

        fct_name = "_update_device_ios_trigger"

        self.any_device_being_updated_flag = True

        try:
            devicename_zone = self._format_devicename_zone(devicename, HOME)

            if self.next_update_time.get(devicename_zone) == PAUSED:
                return

            latitude  = round(dev_data[ATTR_LATITUDE], 6)
            longitude = round(dev_data[ATTR_LONGITUDE], 6)

            if latitude == None or longitude == None:
                return

            iosapp_version_text = "ios{}".format(self.iosapp_version.get(devicename))

            event_msg = "IOS App v{} update started, GPS-({}, {})".format(
                self.iosapp_version.get(devicename),
                latitude,
                longitude)
            self._save_event(devicename, event_msg)

            self.update_timer[devicename] = time.time()

            entity_id     = self.device_tracker_entity.get(devicename)
            current_state = self._get_current_state(entity_id)

            self._log_start_finish_update_banner('▼▼▼', devicename,
                            iosapp_version_text, update_reason)

            self._trace_device_attributes(devicename, 'dev_data', fct_name, dev_data)


            timestamp      = self._timestamp_to_time(dev_data[ATTR_TIMESTAMP])

            if timestamp == ZERO_HHMMSS:
                timestamp = self._secs_to_time(self.this_update_secs)

            gps_accuracy   = dev_data[ATTR_GPS_ACCURACY]
            battery        = dev_data[ATTR_BATTERY_LEVEL]
            battery_status = dev_data[ATTR_BATTERY_STATUS]
            device_status  = dev_data[ATTR_DEVICE_STATUS]
            low_power_mode = dev_data[ATTR_LOW_POWER_MODE]
            vertical_accuracy = self._get_attr(dev_data, ATTR_VERTICAL_ACCURACY, NUMERIC)
            altitude       = self._get_attr(dev_data, ATTR_ALTITUDE, NUMERIC)

            location_isold_attr = 'False'
            location_isold_flag = False
            self.location_isold_cnt[devicename]    = 0
            self.location_isold_msg[devicename]    = False
            self.poor_gps_accuracy_cnt[devicename] = 0
            attrs = {}

            #--------------------------------------------------------
            try:
                if self.device_being_updated_flag.get(devicename):
                    info_msg = "Last update not completed, retrying"
                else:
                    info_msg = "Updating"
                info_msg = "● {} {} ●".format(info_msg,
                    self.friendly_name.get(devicename))

                self._display_info_status_msg(devicename, info_msg)
                self.device_being_updated_flag[devicename] = True

            except Exception as err:
                _LOGGER.exception(err)
                attrs = self._internal_error_msg(
                        fct_name, err, 'UpdateAttrs1')

            try:
                for zone in self.track_from_zone.get(devicename):
                    #If the state changed, only process the zone that changed
                    #to avoid delays caused calculating travel time by other zones
                    if (self.state_change_flag.get(devicename) and
                        self.state_this_poll.get(devicename) != zone and
                        zone != HOME):
                        continue

                    elif latitude == None or longitude == None:
                        continue

                    self.base_zone = zone
                    self._log_start_finish_update_banner('▼-▼', devicename,
                            iosapp_version_text, zone)

                    attrs = self._determine_interval(
                        devicename,
                        latitude,
                        longitude,
                        battery,
                        gps_accuracy,
                        location_isold_flag,
                        self.last_located_secs.get(devicename),
                        timestamp,
                        iosapp_version_text)

                    if attrs != {}:
                        self._update_device_sensors(devicename, attrs)
                    self._log_start_finish_update_banner('▲-▲', devicename,
                            iosapp_version_text, zone)

            except Exception as err:
                attrs = self._internal_error_msg(fct_name, err, 'DetInterval')
                self.any_device_being_updated_flag = False
                return

            try:
                #attrs should not be empty, but catch it and do an icloud update
                #if it does and no data is available. Exit without resetting
                # device _being _update _flag so an icloud update will be done.
                if attrs == {}:
                    self.any_device_being_updated_flag = False
                    self.iosapp_location_update_secs[devicename] = 0

                    event_msg = ("IOS update was not completed, "
                        "will retry with {}").format(self.trk_method_short_name)
                    self._save_event_halog_info(devicename, event_msg)

                    return

                #Note: Final prep and update device attributes via
                #device_tracker.see. The gps location, battery, and
                #gps accuracy are not part of the attrs variable and are
                #reformatted into device attributes by 'See'. The gps
                #location goes to 'See' as a "(latitude, longitude)" pair.
                #'See' converts them to ATTR_LATITUDE and ATTR_LONGITUDE
                #and discards the 'gps' item.

                log_msg = ("►LOCATION ATTRIBUTES, State={}, Attrs={}").format(
                    self.state_last_poll.get(devicename),
                    attrs)
                self.log_debug_msg(devicename, log_msg)

                self._update_last_latitude_longitude(devicename, latitude, longitude, 1844)
                self.count_update_iosapp[devicename] += 1
                self.last_battery[devicename]      = battery
                self.last_gps_accuracy[devicename] = gps_accuracy
                self.last_located_time[devicename] = self._time_to_12hrtime(timestamp)

                if altitude is None:
                    altitude = 0

                attrs[ATTR_LAST_LOCATED]   = self._time_to_12hrtime(timestamp)
                attrs[ATTR_DEVICE_STATUS]  = device_status
                attrs[ATTR_LOW_POWER_MODE] = low_power_mode
                attrs[ATTR_BATTERY]        = battery
                attrs[ATTR_BATTERY_STATUS] = battery_status
                attrs[ATTR_ALTITUDE]       = round(altitude, 2)
                attrs[ATTR_VERTICAL_ACCURACY] = vertical_accuracy
                attrs[ATTR_POLL_COUNT]     = self._format_poll_count(devicename)

            except Exception as err:
                _LOGGER.exception(err)
                #attrs = self._internal_error_msg(
                #        fct_name, err, 'SetAttrsDev')

            try:
                kwargs = self._setup_base_kwargs(
                    devicename,
                    latitude,
                    longitude,
                    battery,
                    gps_accuracy)

                self._update_device_attributes(devicename, kwargs, attrs, 'Final Update')
                self._update_device_sensors(devicename, kwargs)
                self._update_device_sensors(devicename, attrs)

                self.seen_this_device_flag[devicename]     = True
                self.device_being_updated_flag[devicename] = False

            except Exception as err:
                _LOGGER.exception(err)
                log_msg = ("{} Error Updating Device, {}").format(
                    self._format_fname_devtype(devicename), err)
                self.log_error_msg(log_msg)

            try:
                event_msg = ("IOS App v{} update complete").format(
                    self.iosapp_version.get(devicename))
                self._save_event(devicename, event_msg)

                self._log_start_finish_update_banner('▲▲▲', devicename,
                            iosapp_version_text, update_reason)

                entity_id = self.device_tracker_entity.get(devicename)
                dev_attrs = self._get_device_attributes(entity_id)
                #self._trace_device_attributes(devicename, 'after Final', fct_name, dev_attrs)

            except KeyError as err:
                self._internal_error_msg(fct_name, err, 'iosUpdateMsg')

        except Exception as err:
            _LOGGER.exception(err)
            self._internal_error_msg(fct_name, err, 'OverallUpdate')
            self.device_being_updated_flag[devicename] = False

        self.any_device_being_updated_flag = False
        self.iosapp_location_update_secs[devicename] = 0

#########################################################
#
#   This function is called every 15 seconds by HA. Cycle through all
#   of the iCloud devices to see if any of the ones being tracked need
#   to be updated. If so, we might as well update the information for
#   all of the devices being tracked since PyiCloud gets data for
#   every device in the account.
#
#########################################################
    def _polling_loop_15_sec_icloud(self, now):
        """Keep the API alive. Will be called by HA every 15 seconds"""

        if self.any_device_being_updated_flag:
            return

        fct_name = "_polling_loop_15_sec_icloud"

        self.this_update_secs = self._time_now_secs()
        this_update_time = dt_util.now().strftime(self.um_time_strfmt)

        try:
            for devicename in self.tracked_devices:
                update_reason = "Location Update"
                devicename_zone = self._format_devicename_zone(devicename, HOME)

                if (self.tracking_device_flag.get(devicename) is False or
                   self.next_update_time.get(devicename_zone) == PAUSED):
                    continue

                self.iosapp_update_flag[devicename] = False
                update_device_flag = False

                # If the state changed since last poll, force an update
                # This can be done via device_tracker.see service call
                # with a different location_name in an automation or
                # from entering a zone via the IOS App.
                entity_id     = self.device_tracker_entity.get(devicename)
                current_state = self._get_current_state(entity_id)

                if current_state != self.state_last_poll.get(devicename):
                    update_device_flag = True

                    update_reason = "State Change Detected for {} > {} to {}".format(
                        devicename,
                        self.state_last_poll.get(devicename),
                        current_state)
                    self._save_event('*', update_reason)

                    log_msg = ("{} {}").format(
                        self._format_fname_devtype(devicename),
                        update_reason)
                    self.log_info_msg(log_msg)

                    #event_msg = ("{} update, {}").format(
                    #    self.trk_method_short_name,
                    #    update_reason)


                if update_device_flag:
                    if 'nearzone' in current_state:
                        current_state = 'near_zone'

                    self.state_this_poll[devicename] = current_state
                    self.next_update_secs[devicename_zone] = 0

                    attrs  = {}
                    attrs[ATTR_INTERVAL]           = '0 sec'
                    attrs[ATTR_NEXT_UPDATE_TIME]   = ZERO_HHMMSS
                    self._update_device_sensors(devicename, attrs)

                #This flag will be 'true' if the last update for this device
                #was not completed. Do another update now.
                if (self.device_being_updated_flag.get(devicename) and
                    self.device_being_updated_retry_cnt.get(devicename) > 4):
                    self.device_being_updated_flag[devicename] = False
                    self.device_being_updated_retry_cnt[devicename] = 0
                    self.log_debug_msgs_trace_flag = False

                    log_msg = ("{} Canceling update retry").format(
                        self._format_fname_devtype(devicename))
                    self.log_info_msg(log_msg)

                if self._check_in_zone_and_before_next_update(devicename):
                    continue

                elif self.device_being_updated_flag.get(devicename):
                    update_device_flag = True
                    self.log_debug_msgs_trace_flag = True
                    self.device_being_updated_retry_cnt[devicename] += 1

                    event_msg = ("{} update not completed, retrying").format(
                        self.trk_method_short_name)
                    self._save_event_halog_info(devicename, event_msg)
                    update_reason = "{} update, Retrying, Cnt={}".format(
                        self.trk_method_short_name,
                        self.device_being_updated_retry_cnt.get(devicename))

                elif self.next_update_secs.get(devicename_zone) == 0:
                    update_device_flag       = True
                    self.trigger[devicename] = 'StateChange/Resume'
                    self.log_debug_msgs_trace_flag = False
                    update_reason = ("State Change or Resume Polling Requested")
                    self._save_event(devicename, update_reason)

                else:
                    update_via_other_devicename = self._check_next_update_time_reached()
                    if update_via_other_devicename is not None:
                        update_device_flag       = True
                        self.trigger[devicename] = 'NextUpdateTime'
                        self.log_debug_msgs_trace_flag = False

                        update_reason = ("NextUpdateTime reached-{}").format(
                            update_via_other_devicename)
                        self._save_event(devicename, update_reason)

                if update_device_flag:
                    self._wait_if_update_in_process()
                    self.update_in_process_flag = True

                    if self.CURRENT_TRK_METHOD_FMF_FAMSHR:
                        if self.icloud_reauthorizing_account():
                            devicename = self.tracked_devices[0]

                            self._display_info_status_msg(devicename,
                                '●●Verify iCloud/FmF Acct●●')
                            self.info_notification = ("Verification needed for "
                                "account {}").format(self.username)
                            return

                        self._update_device_icloud(update_reason)

                    else:
                        self._request_iosapp_location_update(devicename)

                self.update_in_process_flag = False

        except Exception as err:       #ValueError:
            _LOGGER.exception(err)

            if self.CURRENT_TRK_METHOD_FMF_FAMSHR:
                log_msg = ("►iCloud/FmF API Error, Error={}").format(ValueError)
                self.log_error_msg(log_msg)
                self.api.authenticate()           #Reset iCloud
                self.authenticated_time = dt_util.now().strftime(self.um_date_time_strfmt)
                self._update_device_icloud('iCloud/FmF Reauth')    #Retry update devices

            self.update_in_process_flag = False
            self.log_debug_msgs_trace_flag = False


#########################################################
#
#   Cycle through all iCloud devices and update the information for the devices
#   being tracked
#     ●►●◄►●▬▲▼◀►►●◀ oPhone=►▶
#########################################################
    def _update_device_icloud(self, update_reason = 'CheckiCloud',
            arg_devicename=None):
        """
        Request device information from iCloud (if needed) and update
        device_tracker information.
        """

        if self.CURRENT_TRK_METHOD_IOSAPP:
            return
        elif self._start_icloud3_group_inprocess_flag:
            return
        elif self.any_device_being_updated_flag:
            return

        fct_name = "_update_device_icloud"

        self.any_device_being_updated_flag = True
        refresh_fmf_location_data          = True
        self.base_zone                     = HOME

        try:
            for devicename in self.tracked_devices:
                devicename_zone = self._format_devicename_zone(devicename)

                if arg_devicename and devicename != arg_devicename:
                    continue

                elif self.next_update_time.get(devicename_zone) == PAUSED:
                    continue

                if update_reason == 'Initializing Device Data':
                    event_msg = ("{} update, Initializing device").format(
                        self.trk_method_short_name)
                    self._save_event(devicename, event_msg)

                #If the device is in a zone, and was in the same zone on the
                #last poll of another device on the account and this device
                #update time has not been reached, do not update device
                #information. Do this in case this device currently has bad gps
                #and really doesn't need to be polled at this time anyway.
                if self._check_in_zone_and_before_next_update(devicename):
                    continue

                self.update_timer[devicename] = time.time()
                self.iosapp_location_update_secs[devicename] = 0
                self._log_start_finish_update_banner('▼▼▼', devicename,
                            self.trk_method_short_name, update_reason)

                #update_reason = ("{} update started, NextUpdate time reached").format(
                    #    self.trk_method_short_name)

                event_msg = ("{} update started").format(self.trk_method_short_name)
                self._save_event_halog_info(devicename, event_msg)

                do_not_update_flag = False
                loc_timestamp      = 0

                #Updating device info. Get data from FmF or FamShr and update
                if self.CURRENT_TRK_METHOD_FMF:
                    dev_data = self._get_fmf_data(devicename, refresh_fmf_location_data)
                    refresh_fmf_location_data = False

                elif self.CURRENT_TRK_METHOD_FAMSHR:
                    dev_data = self._get_famshr_data(devicename)

                #An error ocurred accessing the iCloud acount. This can be a
                #Authentication error or an error retrieving the loction data
                if dev_data[0] is False:
                    self.icloud_acct_auth_error_cnt += 1
                    self._determine_interval_retry_after_error(
                        devicename,
                        self.icloud_acct_auth_error_cnt,
                        "iCloud Offline (Authentication or Location Error)")

                    if (self.interval_seconds.get(devicename) != 15 and
                        self.icloud_acct_auth_error_cnt > 2):
                        log_msg = ("iCloud3 Error: An error occurred accessing "
                            "the iCloud account {} for {}. This can be an account "
                            "authentication issue or no location data is "
                            "available. Retrying at next update time. "
                            "Retry #{}").format(
                            self.username,
                            devicename,
                            self.icloud_acct_auth_error_cnt)
                        self._save_event_halog_error("*", log_msg)

                    if self.icloud_acct_auth_error_cnt > 20:
                        self._setup_tracking_method(TRK_METHOD_IOSAPP)
                        log_msg = ("iCloud3 Error: More than 20 iCloud Authentication "
                            "errors. Resetting to use tracking_method <iosapp>. "
                            "Restart iCloud3 at a later time to see if iCloud "
                            "Loction Services is available.")
                        self._save_event_halog_error("*", log_msg)

                    break
                else:
                    self.icloud_acct_auth_error_cnt = 0

                #icloud date overrules device data which may be stale
                latitude            = round(float(dev_data[1]), 6)
                longitude           = round(float(dev_data[2]), 6)

                #Discard if no location coordinates
                if latitude == None or longitude == None:
                    info_msg = "No.Location Coordinates, ({}, {})".format(
                        latitude,
                        longitude)

                    self._determine_interval_retry_after_error(
                        devicename,
                        self.location_isold_cnt.get(devicename),
                        info_msg)
                    do_not_update_flag = True

                else:
                    location_isold_attr = dev_data[3]
                    timestamp           = dev_data[4]
                    gps_accuracy        = int(dev_data[5])
                    battery             = dev_data[6]
                    battery_status      = dev_data[7]
                    device_status       = dev_data[8]
                    low_power_mode      = dev_data[9]
                    location_isold_flag = dev_data[10]
                    location_time_secs  = dev_data[11]
                    altitude            = dev_data[12]
                    vertical_accuracy   = dev_data[13]

                    self.last_located_secs[devicename] = location_time_secs
                    location_age =self._secs_since(location_time_secs)

                #If not authorized or no data, don't check old or accuracy errors
                if self.icloud_acct_auth_error_cnt > 0:
                    pass

                #If initializing, nothing is set yet
                elif self.state_this_poll.get(devicename) == NOT_SET:
                    pass

                #If no location data
                elif do_not_update_flag:
                    pass

                #Discard if location is too old
                elif location_isold_flag:
                    info_msg = "Old.Location, Age-{} (#{})".format(
                        self._secs_to_time_str(location_age),
                        self.location_isold_cnt.get(devicename))

                    self._determine_interval_retry_after_error(
                        devicename,
                        self.location_isold_cnt.get(devicename),
                        info_msg)
                    do_not_update_flag = True

                #Discard if poor gps
                elif self.poor_gps_accuracy_flag.get(devicename):
                    info_msg = 'Poor.GPS.Accuracy, Dist-{}m (#{})'.format(
                        gps_accuracy,
                        self.poor_gps_accuracy_cnt.get(devicename))

                    self._determine_interval_retry_after_error(
                        devicename,
                        self.poor_gps_accuracy_cnt.get(devicename),
                        info_msg)
                    do_not_update_flag = True

                if do_not_update_flag:
                    event_msg = ("Discarding > Location-({}, {}), "
                        "GPSAccuracy-{}m, Located-{}, {}").format(
                        latitude,
                        longitude,
                        gps_accuracy,
                        timestamp,
                        info_msg)
                    self._save_event(devicename, event_msg)

                    self._log_start_finish_update_banner('▲▲▲', devicename,
                            self.trk_method_short_name, update_reason)
                    continue

                #--------------------------------------------------------
                try:
                    if self.device_being_updated_flag.get(devicename):
                        info_msg  = "Retrying > Last update not completed"
                        event_msg = info_msg
                    else:
                        info_msg = "Updating"
                        event_msg = ("Updating > Location-({}, {}), "
                            "GPSAccuracy-{}m, Located-{} ({} ago)").format(
                            latitude,
                            longitude,
                            gps_accuracy,
                            timestamp,
                            self._secs_to_time_str(location_age))

                    info_msg = "● {} {} ●".format(info_msg,
                                self.friendly_name.get(devicename))
                    self._display_info_status_msg(devicename, info_msg)
                    self._save_event(devicename, event_msg)

                    #set device being updated flag. This is checked in the
                    #'_polling_loop_15_sec_icloud' loop to make sure the last update
                    #completed successfully (Waze has a compile error bug that will
                    #kill update and everything will sit there until the next poll.
                    #if this is still set in '_polling_loop_15_sec_icloud', repoll
                    #immediately!!!
                    self.device_being_updated_flag[devicename] = True

                except Exception as err:
                    attrs = self._internal_error_msg(fct_name, err, 'UpdateAttrs1')

                try:
                    if latitude == None or longitude == None:
                        continue

                    for zone in self.track_from_zone.get(devicename):
                        self.base_zone = zone

                        self._log_start_finish_update_banner('▼-▼', devicename,
                            self.trk_method_short_name, zone)

                        attrs = self._determine_interval(
                            devicename,
                            latitude,
                            longitude,
                            battery,
                            gps_accuracy,
                            location_isold_flag,
                            location_time_secs,
                            timestamp,
                            "icld")
                        if attrs != {}:
                            self._update_device_sensors(devicename, attrs)
                        self._log_start_finish_update_banner('▲-▲', devicename,
                            self.trk_method_short_name,zone)

                except Exception as err:
                    attrs = self._internal_error_msg(fct_name, err, 'DetInterval')
                    continue

                try:
                    #Note: Final prep and update device attributes via
                    #device_tracker.see. The gps location, battery, and
                    #gps accuracy are not part of the attrs variable and are
                    #reformatted into device attributes by 'See'. The gps
                    #location goes to 'See' as a "(latitude, longitude)" pair.
                    #'See' converts them to ATTR_LATITUDE and ATTR_LONGITUDE
                    #and discards the 'gps' item.

                    log_msg = ("►LOCATION ATTRIBUTES, State={}, Attrs={}").format(
                        self.state_last_poll.get(devicename),
                        attrs)
                    self.log_debug_msg(devicename, log_msg)

                    self.count_update_icloud[devicename] += 1

                    if not location_isold_flag:
                        self._update_last_latitude_longitude(devicename, latitude, longitude, 4439)

                    if altitude is None:
                        altitude = -2

                    attrs[ATTR_DEVICE_STATUS]  = device_status
                    attrs[ATTR_LOW_POWER_MODE] = low_power_mode
                    attrs[ATTR_BATTERY]        = battery
                    attrs[ATTR_BATTERY_STATUS] = battery_status
                    attrs[ATTR_ALTITUDE]       = round(altitude, 2)
                    attrs[ATTR_VERTICAL_ACCURACY] = vertical_accuracy
                    attrs[ATTR_POLL_COUNT]     = self._format_poll_count(devicename)
                    attrs[ATTR_AUTHENTICATED]  = self.authenticated_time

                except Exception as err:
                    attrs = self._internal_error_msg(fct_name, err, 'SetAttrs')

                try:
                    kwargs = self._setup_base_kwargs(devicename,
                        latitude, longitude, battery, gps_accuracy)

                    self._update_device_sensors(devicename, kwargs)
                    self._update_device_sensors(devicename, attrs)
                    self._update_device_attributes(devicename, kwargs,
                            attrs, 'Final Update')

                    self.seen_this_device_flag[devicename]     = True
                    self.device_being_updated_flag[devicename] = False

                except Exception as err:
                    log_msg = (" {} Error Updating Device, {}").format(
                        self._format_fname_devtype(devicename),
                        err)
                    self.log_error_msg(log_msg)

                    _LOGGER.exception(err)


                try:
                    event_msg = ("{} update completed").format(self.trk_method_short_name)
                    self._save_event(devicename, event_msg)

                    self._log_start_finish_update_banner('▲▲▲', devicename,
                            self.trk_method_short_name, update_reason)

                except KeyError as err:
                    self._internal_error_msg(fct_name, err, 'icloudUpdateMsg')

        except Exception as err:
            self._internal_error_msg(fct_name, err, 'OverallUpdate')
            _LOGGER.exception(err)
            self.device_being_updated_flag[devicename] = False

        self.any_device_being_updated_flag = False

#########################################################
#
#   Get attribute information from the device
#
#########################################################
    def _get_fmf_data(self, devicename, refresh_fmf_location_data):
        '''
        Get the location data from Find My Friends.

        location_data={
            'locationStatus': None,
            'location': {
                'isInaccurate': False,
                'altitude': 0.0,
                'address': {'formattedAddressLines': ['123 Main St',
                    'Your City, NY', 'United States'],
                    'country': 'United States',
                    'streetName': 'Main St,
                    'streetAddress': '123 Main St',
                    'countryCode': 'US',
                    'locality': 'Your City',
                    'stateCode': 'NY',
                    'administrativeArea': 'New York'},
                'locSource': None,
                'latitude': 12.34567890,
                'floorLevel': 0,
                'horizontalAccuracy': 65.0,
                'labels': [{'id': '79f8e34c-d577-46b4-a6d43a7b891eca843',
                    'latitude': 12.34567890,
                    'longitude': -45.67890123,
                    'info': None,
                    'label': '_$!<home>!$_',
                    'type': 'friend'}],
                'tempLangForAddrAndPremises': None,
                'verticalAccuracy': 0.0,
                'batteryStatus': None,
                'locationId': 'a6b0ee1d-be34-578a-0d45-5432c5753d3f',
                'locationTimestamp': 0,
                'longitude': -45.67890123,
                'timestamp': 1562512615222},
            'id': 'NDM0NTU2NzE3',
            'status': None}
        '''

        fct_name = "_get_fmf_data"
        from .pyicloud_ic3 import PyiCloudNoDevicesException

        try:
            #self._save_event(devicename, 'Preparing FmF Location Data')

            if self._get_fmf_updated_location_data(devicename) is False:
                #No icloud data, reauthenticate (status=None)
                try:
                    log_msg = ("FmF Authentication for {} ({}), {}").format(
                        devicename,
                        self.group,
                        self.fmf_devicename_email.get(devicename))
                    self.log_info_msg(log_msg)
                    self.api.authenticate()

                    self.authenticated_time = dt_util.now().strftime(self.um_date_time_strfmt)
                    #self._trace_device_attributes(devicename, 'FmF Status Reauth', fct_name, status)

                except Exception as err:
                    _LOGGER.exception(err)
                    self.log_error_msg("iCloud3 Error: Initial Authentication Failed")
                    return ICLOUD_LOCATION_DATA_ERROR

            #Successful authentication, get data again and recheck
            if self._get_fmf_updated_location_data(devicename) is False:
                self.log_error_msg("iCloud3 Error: Authentication Retry Failed")
                return ICLOUD_LOCATION_DATA_ERROR

        except PyiCloudNoDevicesException:
            self.log_error_msg("iCloud3 Error: No FmF Devices found")
            return ICLOUD_LOCATION_DATA_ERROR

        except Exception as err:
            self.log_error_msg("iCloud3 Error: FmF Location Data Error")
            _LOGGER.exception(err)
            return ICLOUD_LOCATION_DATA_ERROR

        try:
            if devicename not in self.fmf_location_data:
                log_msg = ("iCloud3 Error: Devicename {} is not in location "
                    "data: {}").format(
                    devicename,
                    self.fmf_location_data)
                self.log_error_msg
                return ICLOUD_LOCATION_DATA_ERROR

            location_data = self.fmf_location_data.get(devicename)
            if location_data is None:
                if self.icloud_acct_auth_error_cnt > 3:
                    self.log_error_msg("iCloud3 Error: No FmF Location Data "
                        "Returned for {}").format(
                        devicename)
                return ICLOUD_LOCATION_DATA_ERROR

            location = location_data[ATTR_LOCATION]
            if location is None:
                if self.icloud_acct_auth_error_cnt > 3:
                    self.log_error_msg("iCloud3 Error: No FmF Location Data Returned")
                return ICLOUD_LOCATION_DATA_ERROR

            #battery_status = ''
            battery        = 0
            #if ATTR_ICLOUD_BATTERY_STATUS in location:
            #    battery_status = location.get(ATTR_ICLOUD_BATTERY_STATUS)

            battery_status  = self._get_attr(location, ATTR_ICLOUD_BATTERY_STATUS)
            device_status   = 0
            low_power_mode  = None

            location_time_secs   = int(location[ATTR_TIMESTAMP]) / 1000
            location_time_hhmmss = self._secs_to_time(location_time_secs)

            latitude        = round(location[ATTR_LATITUDE], 6)
            longitude       = round(location[ATTR_LONGITUDE], 6)
            gps_accuracy    = int(location[ATTR_ICLOUD_HORIZONTAL_ACCURACY])
            vertical_accuracy=int(location[ATTR_ICLOUD_VERTICAL_ACCURACY])
            altitude        = int(location[ATTR_ALTITUDE])
            location_isold_attr = False

            #event_msg = "Location data prepared, {} ({}, {}), Accuracy {}m".format(
            #        self._get_current_zone(devicename, latitude, longitude),
            #        latitude,
            #        longitude,
            #        gps_accuracy)
            #self._save_event(devicename, event_msg)

            try:
                location_isold_flag = self._check_location_isold(
                    devicename, location_isold_attr, location_time_secs)

                self._check_poor_gps(devicename, gps_accuracy)

                log_msg = ("►LOCATION DATA, BaseZome={}, TimeStamp={}, "
                   "GPS=({}, {}), isOldFlag={}, GPSAccuracy={}").format(
                    self.base_zone,
                    location_time_hhmmss,
                    latitude, longitude,
                    location_isold_flag,
                    gps_accuracy)
                self.log_debug_msg(devicename, log_msg)

            except Exception as err:
                _LOGGER.exception(err)
                location_isold_flag = False
                self.poor_gps_accuracy_cnt[devicename]  = 0
                self.poor_gps_accuracy_flag[devicename] = False
                x = self._internal_error_msg(fct_name, err, 'OldLocGPS')

            return (True, latitude, longitude, location_isold_attr,
                    location_time_hhmmss, gps_accuracy, battery, battery_status,
                    device_status, low_power_mode,
                    location_isold_flag, location_time_secs, altitude,
                    vertical_accuracy)

        except Exception as err:
            _LOGGER.exception(err)
            self.log_error_msg("General iCloud Location Data Error")
            return ICLOUD_LOCATION_DATA_ERROR

#----------------------------------------------------------------------------
    def _get_fmf_updated_location_data(self, devicename):
        '''
        Refresh the FmF friends data after an authentication.
        If no location data was returned from pyicloid_ic3,
        return with False
        '''
        fct_name = "_get_fmf_data"

        try:
            #self.log_debug_msg(devicename, "►Refresh FmF Location Data")
            from .pyicloud_ic3 import PyiCloudNoDevicesException

            retry_cnt = 0
            refresh_successful = False

            old_cnt = 0
            for devicename in self.tracked_devices:
                old_cnt += self.poor_gps_accuracy_cnt.get(devicename)
                old_cnt += self.location_isold_cnt.get(devicename)

            age = self._secs_since(self.last_fmf_refresh)
            log_msg = ("►Check FmF data ({}), refreshed {} secs ago").format(
                devicename,
                age)

            if old_cnt == 0 and age <= 15:
                log_msg += ", location data reused"
                self.log_debug_msg(devicename, log_msg)
                return True

            log_msg += ", GPS+OldCnt={}, will be refreshed".format(old_cnt)
            self.log_debug_msg(devicename, log_msg)

        except Exception as err:
            _LOGGER.exception(err)
            return False

        while retry_cnt < 3:
            try:
                retry_cnt += 1
                fmf = self.api.friends

                if retry_cnt > 1:
                    log_msg = ("FmF retrying data refresh, cnt={}").format(retry_cnt)
                    self.log_debug_msg('*', log_msg)

                if fmf is None:
                    self.api.authenticate()
                    self.authenticated_time = dt_util.now().strftime(self.um_date_time_strfmt)
                    fmf = self.api.friends

                    log_msg = ("Reauthenticated FmF account {}").format(
                        self.username)
                    self.log_info_msg(log_msg)

                if fmf:
                    self.fmf_location_data = {}
                    locations = fmf.locations

                    if locations:
                        refresh_msg = ''
                        for location in locations:
                            self.log_level_debug_rawdata("FmF Location Data", location)

                            contact_id = location.get('id')

                            if self.fmf_id.get(contact_id):
                                devicename = self.fmf_id[contact_id]
                                self.fmf_location_data[devicename] = location
                                refresh_successful = True

                                #if refresh_msg.find(devicename) == -1:
                                if instr(refresh_msg, devicename) == False:
                                    refresh_msg = '{}, {}({})'.format(
                                        refresh_msg,
                                        devicename,
                                        contact_id)
                        log_msg = ("FmF refresh for {} successful, {}").format(
                            self.username,
                            refresh_msg)
                        self.log_info_msg(log_msg)

                    if refresh_successful is True:
                        self.last_fmf_refresh = self.this_update_secs
                        break

            except PyiCloudNoDevicesException:
                self.log_error_msg("No FmF Devices found")

            except Exception as err:
                _LOGGER.exception(err)

        return refresh_successful

#----------------------------------------------------------------------------
    def _get_famshr_data(self, devicename):
        '''
        Extract the data needed to determine location, direction, interval,
        etc. from the iCloud data set.

        Sample data set is:
       'batteryLevel': 0.6100000143051147, 'deviceDisplayName': 'iPhone XS',
       'deviceStatus': '200', CONF_NAME: 'Lillian-iPhone',
       'deviceModel': 'iphoneXS-1-4-0', 'rawDeviceModel': 'iPhone11,2',
       'deviceClass': 'iPhone', 'id': 't0v3GV....FFZav2IsE'
       'lowPowerMode': False, 'batteryStatus': 'Charging', 'fmlyShare': True,
       'location': {ATTR_ISOLD: False, 'isInaccurate': False, 'altitude': 0.0,
       'positionType': 'Wifi', 'latitude': 12.345678, 'floorLevel': 0,
       'horizontalAccuracy': 65.0, 'locationType': '',
       'timeStamp': 1550850915898, 'locationFinished': False,
       'verticalAccuracy': 0.0, 'longitude': -23.456789},
       'locationCapable': True, 'locationEnabled': True, 'isLocating': False,
       'remoteLock': None, 'activationLocked': True, 'lockedTimestamp': None,
       'lostModeCapable': True, 'lostModeEnabled': False,
       'locFoundEnabled': False, 'lostDevice': None, 'lostTimestamp': '',
       'remoteWipe': None, 'wipeInProgress': False, 'wipedTimestamp': None,
       'isMac': False
        '''

        fct_name = "_get_famshr_data"
        from .pyicloud_ic3 import PyiCloudNoDevicesException

        try:
            log_msg = ("= = = Prep Data From FamShr = = = (Now={})").format(
                self.this_update_secs)
            self.log_debug_msg(devicename, log_msg)

            #self._save_event(devicename, 'Preparing FamShr Location Data')

            #Get device attributes from iCloud
            device   = self.icloud_api_devices.get(devicename)
            status   = device.status(DEVICE_STATUS_SET)

            self._trace_device_attributes(devicename, 'FamShr Status', fct_name, status)

        except Exception as err:
#           No icloud data, reauthenticate (status=None)
            self.api.authenticate()
            self.authenticated_time = dt_util.now().strftime(self.um_date_time_strfmt)
            device = self.icloud_api_devices.get(devicename)
            status = device.status(DEVICE_STATUS_SET)

            log_msg = ("Reauthenticated FamShr account {} for {}").format(
                self.username,
                devicename)
            self.log_info_msg(log_msg)
            self._trace_device_attributes(devicename, 'FamShr Status Reauth', fct_name, status)

            if status is None:
                return ICLOUD_LOCATION_DATA_ERROR

        try:
            location       = status['location']
            battery        = int(status.get(ATTR_ICLOUD_BATTERY_LEVEL, 0) * 100)
            battery_status = status[ATTR_ICLOUD_BATTERY_STATUS]
            device_status  = DEVICE_STATUS_CODES.get(status[ATTR_ICLOUD_DEVICE_STATUS], 'error')
            low_power_mode = status['lowPowerMode']

            self._trace_device_attributes(devicename, 'iCloud Loc', fct_name, location)

            if location:
                loc_time_secs   = location[ATTR_ICLOUD_LOC_TIMESTAMP] / 1000
                loc_time_hhmmss = self._secs_to_time(loc_time_secs)

                latitude        = round(location[ATTR_LATITUDE], 6)
                longitude       = round(location[ATTR_LONGITUDE], 6)
                gps_accuracy    = int(location[ATTR_ICLOUD_HORIZONTAL_ACCURACY])
                vertical_accuracy=int(location[ATTR_ICLOUD_VERTICAL_ACCURACY])
                altitude        = int(location[ATTR_ALTITUDE])
                location_isold_attr = location[ATTR_ISOLD]

                #event_msg = "Location data prepared, {} ({}, {}), Accuracy {}m".format(
                #    self._get_current_zone(devicename, latitude, longitude),
                #    latitude,
                #    longitude,
                #    gps_accuracy)
                #self._save_event(devicename, event_msg)

                try:
                    location_isold_flag = self._check_location_isold(
                        devicename,
                        location_isold_attr,
                        loc_time_secs)

                    log_msg = ("►LOCATION DATA, TimeStamp={}, "
                        "GPS=({}, {}), isOldFlag={}, GPSAccuracy={}").format(
                        loc_time_hhmmss,
                        longitude,
                        latitude,
                        location_isold_flag,
                        gps_accuracy)
                    self.log_debug_msg(devicename, log_msg)

                    self._check_poor_gps(devicename, gps_accuracy)

                except Exception as err:
                    _LOGGER.exception(err)
                    location_isold_flag = False
                    self.poor_gps_accuracy_cnt[devicename]  = 0
                    self.poor_gps_accuracy_flag[devicename] = False
                    x = self._internal_error_msg(fct_name, err, 'OldLocGPS')

            else:
                loc_time_hhmmss     = 'No Location Data'
                latitude            = 0
                longitude           = 0
                location_isold_attr = False
                gps_accuracy        = 0
                location_isold_flag = False
                self.state_last_poll[devicename] = NOT_SET

            return (True, latitude, longitude, location_isold_attr,
                    loc_time_hhmmss, gps_accuracy, battery, battery_status,
                    device_status, low_power_mode,
                    location_isold_flag, loc_time_secs, altitude,
                    vertical_accuracy)

        except PyiCloudNoDevicesException:
            self.log_error_msg("No FamShr Devices found")
            return ICLOUD_LOCATION_DATA_ERROR

        except Exception as err:
            _LOGGER.exception(err)
##            self.log_error_msg("FamShr Location Data Error")
            return ICLOUD_LOCATION_DATA_ERROR

#########################################################
#
#   iCloud is disabled so trigger the iosapp to send a
#   Background Fetch location transaction
#
#########################################################
    def _request_iosapp_location_update(self, devicename):
        #service: notify.ios_<your_device_id_here>
        #  data:
        #    message: "request_location_update"


        if (self.count_request_iosapp_update.get(devicename) > \
                self.max_iosapp_locate_cnt):
            return

        request_msg_suffix = ''

        try:
            #if time > 0, then waiting for requested update to occur, update age
            if self.iosapp_location_update_secs.get(devicename) > 0:
                age = self._secs_since(self.iosapp_location_update_secs.get(devicename))
                request_msg_suffix = ' {} ago'.format(self._secs_to_time_str(age))

            else:
                self.iosapp_location_update_secs[devicename] = self.this_update_secs
                self.count_request_iosapp_update[devicename] += 1
                self.count_update_icloud[devicename] += 1

                if self.iosapp_version[devicename] == 1:
                    entity_id    = "ios_{}".format(devicename)
                else:
                    entity_id    = "mobile_app_{}".format(devicename)
                service_data = {"message": "request_location_update"}

                self.hass.services.call("notify", entity_id, service_data)

                event_msg = "Request IOS App Location Update (#{})".format(
                    self.count_request_iosapp_update.get(devicename))
                self._save_event(devicename, event_msg)

                log_msg = "{} {}".format(
                    self._format_fname_devtype(devicename),
                    event_msg)
                self.log_debug_msg(devicename, log_msg)

            attrs = {}
            attrs[ATTR_POLL_COUNT] = self._format_poll_count(devicename)
            attrs[ATTR_INFO]       = '● Location update requested (#{}){} ●'.format(
                self.count_request_iosapp_update.get(devicename),
                request_msg_suffix)
            self._update_device_sensors(devicename, attrs)

        except Exception as err:
            error_msg = ("iCloud3 Error: An error was encountered processing "
                "device `location`request - {}").format(err)
            self._save_event_halog_error(devicename, error_msg)


#########################################################
#
#   Calculate polling interval based on zone, distance from home and
#   battery level. Setup triggers for next poll
#
#########################################################
    def _determine_interval(self, devicename, latitude, longitude,
                    battery, gps_accuracy,
                    location_isold_flag, location_time_secs, loc_timestamp,
                    ios_icld = ''):
        """Calculate new interval. Return location based attributes"""

        fct_name = "_determine_interval"

        base_zone_home  = (self.base_zone == HOME)
        devicename_zone = self._format_devicename_zone(devicename)

        try:
            self.base_zone_name   = self.zone_friendly_name.get(self.base_zone)
            self.base_zone_lat    = self.zone_lat.get(self.base_zone)
            self.base_zone_long   = self.zone_long.get(self.base_zone)
            self.base_zone_radius_km = float(self.zone_radius_km.get(self.base_zone))

            location_data = self._get_distance_data(
                devicename,
                latitude,
                longitude,
                gps_accuracy,
                location_isold_flag)

            log_msg = ("Location_data={}").format(location_data)
            self.log_debug_interval_msg(devicename, log_msg)

            #Abort and Retry if Internal Error
            if (location_data[0] == 'ERROR'):
                return location_data[1]     #(attrs)

            current_zone                 = location_data[0]
            dir_of_travel                = location_data[1]
            dist_from_zone_km            = location_data[2]
            dist_from_zone_moved_km      = location_data[3]
            dist_last_poll_moved_km      = location_data[4]
            waze_dist_from_zone_km       = location_data[5]
            calc_dist_from_zone_km       = location_data[6]
            waze_dist_from_zone_moved_km = location_data[7]
            calc_dist_from_zone_moved_km = location_data[8]
            waze_dist_last_poll_moved_km = location_data[9]
            calc_dist_last_poll_moved_km = location_data[10]
            waze_time_from_zone          = location_data[11]
            last_dist_from_zone_km       = location_data[12]
            last_dir_of_travel           = location_data[13]
            dir_of_trav_msg              = location_data[14]
            timestamp                    = location_data[15]

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetLocation')
            return attrs_msg

        try:
            log_msg = ("►DETERMINE INTERVAL Entered, "
                          "location_data={}").format(devicename, location_data)
            self.log_debug_interval_msg(devicename, log_msg)

    #       the following checks the distance from home and assigns a
    #       polling interval in minutes.  It assumes a varying speed and
    #       is generally set so it will poll one or twice for each distance
    #       group. When it gets real close to home, it switches to once
    #       each 15 seconds so the distance from home will be calculated
    #       more often and can then be used for triggering automations
    #       when you are real close to home. When home is reached,
    #       the distance will be 0.

            calc_interval = round(self._km_to_mi(dist_from_zone_km) / 1.5) * 60
            if self.waze_status == WAZE_USED:
                waze_interval = \
                    round(waze_time_from_zone * 60 * self.travel_time_factor , 0)
            else:
                waze_interval = 0
            interval = 15
            interval_multiplier = 1

            inzone_flag          = (self._is_inzoneZ(current_zone))
            not_inzone_flag      = (self._isnot_inzoneZ(current_zone))
            was_inzone_flag      = (self._was_inzone(devicename))
            wasnot_inzone_flag   = (self._wasnot_inzone(devicename))
            inzone_home_flag     = (current_zone == self.base_zone)     #HOME)
            was_inzone_home_flag = \
                (self.state_last_poll.get(devicename) == self.base_zone) #HOME)
            near_zone_flag       = (current_zone == 'near_zone')

            log_msg = ("Zone={} ,IZ={}, NIZ={}, WIZ={}, WNIZ={}, IZH={}, WIZH={}, "
                "NZ={}").format(
                current_zone,
                inzone_flag,
                not_inzone_flag,
                was_inzone_flag,
                wasnot_inzone_flag,
                inzone_home_flag,
                was_inzone_home_flag,
                near_zone_flag)
            self.log_debug_interval_msg(devicename, log_msg)

            log_method  = ''
            log_msg     = ''
            log_method_im  = ''

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetupZone')
            return attrs_msg

        try:
            #Note: If current_state is 'near_zone', it is reset to NOT_HOME when
            #updating the device_tracker state so it will not trigger a state chng
            if self.state_change_flag.get(devicename):
                if inzone_flag:
                    if (STATIONARY in current_zone):
                        interval = self.stat_zone_inzone_interval
                        log_method = "1sz-Stationary"
                        log_msg    = 'Zone={}'.format(current_zone)

                    #inzone & old location
                    elif location_isold_flag:
                        interval = self._get_interval_for_error_retry_cnt(
                                        self.location_isold_cnt.get(devicename))
                        log_method = '1iz-OldLoc'

                    else:
                        interval = self.inzone_interval
                        log_method="1ez-EnterZone"

                #entered 'near_zone' zone if close to HOME and last is NOT_HOME
                elif (near_zone_flag and wasnot_inzone_flag and
                        calc_dist_from_zone_km < 2):
                    interval = 15
                    dir_of_travel = 'NearZone'
                    log_method="1nz-EnterHomeNearZone"

                #entered 'near_zone' zone if close to HOME and last is NOT_HOME
                elif (near_zone_flag and was_inzone_flag and
                        calc_dist_from_zone_km < 2):
                    interval = 15
                    dir_of_travel = 'NearZone'
                    log_method="1nhz-EnterNearHomeZone"

                #exited HOME zone
                elif (not_inzone_flag and was_inzone_home_flag):
                    interval = 240
                    dir_of_travel = AWAY_FROM
                    log_method="1ehz-ExitHomeZone"

                #exited 'other' zone
                elif (not_inzone_flag and was_inzone_flag):
                    interval = 120
                    dir_of_travel = 'left_zone'
                    log_method="1ez-ExitZone"

                #entered 'other' zone
                else:
                    interval = 240
                    log_method="1zc-ZoneChanged"

                log_msg = 'Zone={}, Last={}, This={}'.format(
                    current_zone,
                    self.state_last_poll.get(devicename),
                    self.state_this_poll.get(devicename))
                self.log_debug_interval_msg(devicename, log_msg)

            #inzone & poor gps & check gps accuracy when inzone
            elif (self.poor_gps_accuracy_flag.get(devicename) and
                    inzone_flag and self.check_gps_accuracy_inzone_flag):
                interval   = 300      #poor accuracy, try again in 5 minutes
                log_method = '2iz-PoorGPS'

            #poor gps & cnt > 8
            #elif (self.poor_gps_accuracy_flag.get(devicename) and
            #        self.poor_gps_accuracy_cnt.get(devicename) >= 8):
            #    self.poor_gps_accuracy_cnt[devicename] = 0
            #    interval   = 300      #poor accuracy, try again in 5 minutes
            #    log_method = '2a-PoorGPSCnt>8'

            elif self.poor_gps_accuracy_flag.get(devicename):
                interval = self._get_interval_for_error_retry_cnt(
                                self.poor_gps_accuracy_cnt.get(devicename))
                log_method = '2niz-PoorGPS'

            elif self.overrideinterval_seconds.get(devicename) > 0:
                interval   = self.overrideinterval_seconds.get(devicename)
                log_method = '3-Override'

            elif (STATIONARY in current_zone):
                interval = self.stat_zone_inzone_interval
                log_method = "4sz-Stationary"
                log_msg    = 'Zone={}'.format(current_zone)

            elif location_isold_flag:
                interval = self._get_interval_for_error_retry_cnt(
                                self.location_isold_cnt.get(devicename))
                log_method = '4-OldLoc'
                log_msg      = 'Cnt={}'.format(
                                    self.location_isold_cnt.get(devicename))
                #if self.location_isold_cnt.get(devicename) % 4:
                #    interval   = 180
                #    log_method = '5ol-OldLoc%4'
                #else:
                #    interval   = 30
                #    log_method = '5ol-OldLoc'
                #if inzone_flag:
                #    interval_multiplier = 2

            elif (inzone_home_flag or
                    (dist_from_zone_km < .05 and dir_of_travel == 'towards')):
                interval   = self.inzone_interval
                log_method = '4iz-InZone'
                log_msg    = 'Zone={}'.format(current_zone)

            elif current_zone == 'near_zone':
                interval = 15
                log_method = '4nz-NearZone'
                log_msg    = 'Zone={}, Dir={}'.format(current_zone, dir_of_travel)

            #in another zone and inzone time > travel time
            elif (inzone_flag and self.inzone_interval > waze_interval):
                interval   = self.inzone_interval
                log_method = '4iz-InZone'
                log_msg    = 'Zone={}'.format(current_zone)

            elif dir_of_travel in ('left_zone', NOT_SET):
                interval = 150
                if inzone_home_flag:
                    dir_of_travel = AWAY_FROM
                else:
                    dir_of_travel = NOT_SET
                log_method = '5-NeedInfo'
                log_msg    = 'ZoneLeft={}'.format(current_zone)


            elif dist_from_zone_km < 2.5 and self.went_3km.get(devicename):
                interval   = 15             #1.5 mi=real close and driving
                log_method = '10a-Dist < 2.5km(1.5mi)'

            elif dist_from_zone_km < 3.5:      #2 mi=30 sec
                interval   = 30
                log_method = '10b-Dist < 3.5km(2mi)'

            elif waze_time_from_zone > 5 and waze_interval > 0:
                interval   = waze_interval
                log_method = '10c-WazeTime'
                log_msg    = 'TimeFmHome={}'.format(waze_time_from_zone)

            elif dist_from_zone_km < 5:        #3 mi=1 min
                interval   = 60
                log_method = '10d-Dist < 5km(3mi)'

            elif dist_from_zone_km < 8:        #5 mi=2 min
                interval   = 120
                log_method = '10e-Dist < 8km(5mi)'

            elif dist_from_zone_km < 12:       #7.5 mi=3 min
                interval   = 180
                log_method = '10f-Dist < 12km(7mi)'


            elif dist_from_zone_km < 20:       #12 mi=10 min
                interval   = 600
                log_method = '10g-Dist < 20km(12mi)'

            elif dist_from_zone_km < 40:       #25 mi=15 min
                interval   = 900
                log_method = '10h-Dist < 40km(25mi)'

            elif dist_from_zone_km > 150:      #90 mi=1 hr
                interval   = 3600
                log_method = '10i-Dist > 150km(90mi)'

            else:
                interval   = calc_interval
                log_method = '20-Calculated'
                log_msg    = 'Value={}/1.5'.format(self._km_to_mi(dist_from_zone_km))

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetInterval')

        try:
            #if haven't moved far for 8 minutes, put in stationary zone
            #determined in get_dist_data with dir_of_travel
            if dir_of_travel == STATIONARY:
                interval = self.stat_zone_inzone_interval
                log_method = "21-Stationary"

                if self.in_stationary_zone_flag.get(devicename) is False:
                    rtn_code = self._update_stationary_zone(
                        devicename,
                        latitude,
                        longitude,
                        STATIONARY_ZONE_VISIBLE)

                    self.zone_current[devicename]   = self._format_zone_name(devicename, STATIONARY)
                    self.zone_timestamp[devicename] = dt_util.now().strftime(
                        self.um_date_time_strfmt)
                    self.in_stationary_zone_flag[devicename] = rtn_code
                    if rtn_code:
                        event_msg = ("Stationary Zone Set, GPS-({}, {})").format(
                            latitude,
                            longitude)
                        self._save_event(devicename, event_msg)
                        log_method_im   = "●Set.Stationary.Zone"
                        current_zone    = STATIONARY
                        dir_of_travel   = 'in_zone'
                        inzone_flag     = True
                        not_inzone_flag = False
                    else:
                        dir_of_travel = NOT_SET

            if dir_of_travel in ('', AWAY_FROM) and interval < 180:
                interval = 180
                log_method_im = '30-Away(<3min)'

            elif (dir_of_travel == AWAY_FROM and
                    not self.distance_method_waze_flag):
                interval_multiplier = 2    #calc-increase timer
                log_method_im = '30-Away(Calc)'

            elif (dir_of_travel == NOT_SET and interval > 180):
                interval = 180

            #15-sec interval (close to zone) and may be going into a stationary zone,
            #increase the interval
            elif (interval == 15 and
                    devicename in self.stat_zone_timer and
                    self.this_update_secs >= self.stat_zone_timer.get(devicename)+45):
                interval = 30
                log_method_im = '31-StatTimer+45'

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetStatZone')
            _LOGGER.exception(err)


        try:
            #Turn off waze close to zone flag to use waze after leaving zone
            if inzone_flag:
                self.waze_close_to_zone_pause_flag = False

            #if triggered by ios app (Zone Enter/Exit, Manual, Fetch, etc.)
            #and interval < 3 min, set to 3 min. Leave alone if > 3 min.
            if (self.iosapp_update_flag.get(devicename) and
                    interval < 180 and
                    self.overrideinterval_seconds.get(devicename) == 0):
                interval   = 180
                log_method = '0-iosAppTrigger'

            #no longer in stationary, reset stat zone size but keep in old position
            if (not_inzone_flag and self.in_stationary_zone_flag.get(devicename)):
                self.in_stationary_zone_flag[devicename] = False

                zone_name = self._format_zone_name(devicename, STATIONARY)        
                rtn_code = self._update_stationary_zone(
                    devicename,
                    self.zone_lat.get(zone_name),
                    self.zone_long.get(zone_name),
                    STATIONARY_ZONE_HIDDEN)
                self._save_event(devicename, "Stationary Zone Exited")

            #if changed zones on this poll reset multiplier
            if self.state_change_flag.get(devicename):
                interval_multiplier = 1

            #Check accuracy again to make sure nothing changed, update counter
            if self.poor_gps_accuracy_flag.get(devicename):
                interval_multiplier = 1

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'ResetStatZone')
            return attrs_msg


        try:
            #Real close, final check to make sure interval is not adjusted
            if interval <= 60 or \
                    (battery > 0 and battery <= 33 and interval >= 120):
                interval_multiplier = 1

            interval     = interval * interval_multiplier
            interval, x  = divmod(interval, 15)
            interval     = interval * 15
            interval_str = self._secs_to_time_str(interval)

            interval_debug_msg = ("●Interval={} ({}, {}), ●DirOfTrav={}, "
                "●State={}->{}, Zone={}").format(
                interval_str,
                log_method,
                log_msg,
                dir_of_trav_msg,
                self.state_last_poll.get(devicename),
                self.state_this_poll.get(devicename),
                current_zone)
            event_msg = ("Interval basis: {}, {}, Direction {}").format(
                log_method,
                log_msg,
                dir_of_travel)
            #self._save_event(devicename, event_msg)

            if interval_multiplier != 1:
               interval_debug_msg = "{}, Multiplier={}({})".format(\
                        interval_debug_msg, interval_multiplier, log_method_im)

            #check if next update is past midnight (next day), if so, adjust it
            next_poll = round((self.this_update_secs + interval)/15, 0) * 15

            # Update all dates and other fields
            self.next_update_secs[devicename_zone] = next_poll
            self.next_update_time[devicename_zone] = self._secs_to_time(next_poll)
            self.interval_seconds[devicename_zone] = interval
            self.interval_str[devicename_zone]     = interval_str
            self.last_update_secs[devicename_zone] = self.this_update_secs
            self.last_update_time[devicename_zone] = self._secs_to_time(self.this_update_secs)

            #if more than 3km(1.8mi) then assume driving, used later above
            if dist_from_zone_km > 3:                # 1.8 mi
                self.went_3km[devicename] = True
            elif dist_from_zone_km < .03:            # home, reset flag
                 self.went_3km[devicename] = False

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetTimes')

        try:
            log_msg = ("►►INTERVAL FORMULA, {}").format(interval_debug_msg)
            self.log_debug_interval_msg(devicename, log_msg)

            if self.log_level_intervalcalc_flag == False:
                interval_debug_msg = ''

            log_msg = ("►DETERMINE INTERVAL <COMPLETE>, "
                "This poll: {}({}), Last Update: {}({}), "
                "Next Update: {}({}),  Interval: {}*{}, "
                "OverrideInterval={}, DistTraveled={}, CurrZone={}").format(
                self._secs_to_time(self.this_update_secs),
                self.this_update_secs,
                self.last_update_time.get(devicename_zone),
                self.last_update_secs.get(devicename_zone),
                self.next_update_time.get(devicename_zone),
                self.next_update_secs.get(devicename_zone),
                self.interval_str.get(devicename_zone),
                interval_multiplier,
                self.overrideinterval_seconds.get(devicename),
                dist_last_poll_moved_km, current_zone)
            self.log_debug_interval_msg(devicename, log_msg)

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'ShowMsgs')


        try:
            #if 'NearZone' zone, do not change the state
            if near_zone_flag:
                current_zone = NOT_HOME

            log_msg = ("►DIR OF TRAVEL ATTRS, Direction={}, LastDir={}, "
               "Dist={}, LastDist={}, SelfDist={}, Moved={},"
               "WazeMoved={}").format(
               dir_of_travel,
               last_dir_of_travel,
               dist_from_zone_km,
               last_dist_from_zone_km,
               self.zone_dist.get(devicename_zone),
               dist_from_zone_moved_km,
               waze_dist_from_zone_moved_km)
            self.log_debug_interval_msg(devicename, log_msg)

            #if poor gps and moved less than 1km, redisplay last distances
            if (self.state_change_flag.get(devicename) == False and
                    self.poor_gps_accuracy_flag.get(devicename) and
                            dist_last_poll_moved_km < 1):
                dist_from_zone_km      = self.zone_dist.get(devicename_zone)
                waze_dist_from_zone_km = self.waze_dist.get(devicename_zone)
                calc_dist_from_zone_km = self.calc_dist.get(devicename_zone)
                waze_time_msg       = self.waze_time.get(devicename_zone)

            else:
                waze_time_msg       = self._format_waze_time_msg(devicename,
                                                    waze_time_from_zone,
                                                    waze_dist_from_zone_km)

                #save for next poll if poor gps
                self.zone_dist[devicename_zone] = dist_from_zone_km
                self.waze_dist[devicename_zone] = waze_dist_from_zone_km
                self.waze_time[devicename_zone] = waze_time_msg
                self.calc_dist[devicename_zone] = calc_dist_from_zone_km

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetDistDir')

        try:
            #Save last and new state, set attributes
            #If first time thru, set the last state to the current state
            #so a zone change will not be triggered next time
            if self.state_last_poll.get(devicename) == NOT_SET:
                self.state_last_poll[devicename] = current_zone

            #When put into stationary zone, also set last_poll so it
            #won't trigger again on next cycle as a state change
            #elif (current_zone.endswith(STATIONARY) or
            #        self.state_this_poll.get(devicename).endswith(STATIONARY)):
            elif (instr(current_zone, STATIONARY) or
                    instr(self.state_this_poll.get(devicename), STATIONARY)):
                current_zone                     = STATIONARY
                self.state_last_poll[devicename] = STATIONARY

            else:
                self.state_last_poll[devicename] = self.state_this_poll.get(devicename)

            self.state_this_poll[devicename]   = current_zone
            self.last_located_time[devicename] = self._time_to_12hrtime(loc_timestamp)
            location_age                       = self._secs_since(location_time_secs)
            location_age_str                   = self._secs_to_time_str(location_age)
            if location_isold_flag:
                location_age_str = "Old-{}".format(location_age_str)

            log_msg=("LOCATION TIME-{} loc_timestamp={}, loc_time_secs={}({}), age={}").format(
                    devicename, loc_timestamp, self._secs_to_time(location_time_secs),
                    location_time_secs, location_age_str)
            self.log_debug_msg(devicename, log_msg)

            attrs = {}
            attrs[ATTR_ZONE]              = self.zone_current.get(devicename)
            attrs[ATTR_ZONE_TIMESTAMP]    = str(self.zone_timestamp.get(devicename))
            attrs[ATTR_LAST_ZONE]         = self.zone_last.get(devicename)
            attrs[ATTR_LAST_UPDATE_TIME]  = self._secs_to_time(self.this_update_secs)
            attrs[ATTR_LAST_LOCATED]      = self._time_to_12hrtime(loc_timestamp)

            attrs[ATTR_INTERVAL]          = interval_str
            attrs[ATTR_NEXT_UPDATE_TIME]  = self._secs_to_time(next_poll)

            attrs[ATTR_WAZE_TIME]     = ''
            if self.waze_status == WAZE_USED:
                attrs[ATTR_WAZE_TIME]     = waze_time_msg
                attrs[ATTR_WAZE_DISTANCE] = self._km_to_mi(waze_dist_from_zone_km)
            elif self.waze_status == WAZE_NOT_USED:
                attrs[ATTR_WAZE_DISTANCE] = 'WazeOff'
            elif self.waze_status == WAZE_ERROR:
                attrs[ATTR_WAZE_DISTANCE] = 'NoRoutes'
            elif self.waze_status == WAZE_OUT_OF_RANGE:
                if waze_dist_from_zone_km < 1:
                    attrs[ATTR_WAZE_DISTANCE] = ''
                elif waze_dist_from_zone_km < self.waze_min_distance:
                    attrs[ATTR_WAZE_DISTANCE] = 'DistLow'
                else:
                    attrs[ATTR_WAZE_DISTANCE] = 'DistHigh'
            elif dir_of_travel == 'in_zone':
                attrs[ATTR_WAZE_DISTANCE] = ''
            elif self.waze_status == WAZE_PAUSED:
                attrs[ATTR_WAZE_DISTANCE] = PAUSED
            elif waze_dist_from_zone_km > 0:
                attrs[ATTR_WAZE_TIME]     = waze_time_msg
                attrs[ATTR_WAZE_DISTANCE] = self._km_to_mi(waze_dist_from_zone_km)
            else:
                attrs[ATTR_WAZE_DISTANCE] = ''

            attrs[ATTR_ZONE_DISTANCE]   = self._km_to_mi(dist_from_zone_km)
            attrs[ATTR_CALC_DISTANCE]   = self._km_to_mi(calc_dist_from_zone_km)
            attrs[ATTR_DIR_OF_TRAVEL]   = dir_of_travel
            attrs[ATTR_TRAVEL_DISTANCE] = self._km_to_mi(dist_last_poll_moved_km)

            info_msg = self._format_info_attr(
                    devicename,
                    battery,
                    gps_accuracy,
                    dist_last_poll_moved_km,
                    current_zone,
                    location_isold_flag, location_time_secs)
                    #loc_timestamp)

            attrs[ATTR_INFO] = interval_debug_msg + info_msg

            #save for event log
            self.last_tavel_time[devicename_zone]   = waze_time_msg
            self.last_distance_str[devicename_zone] = '{} {}'.format(
                self._km_to_mi(dist_from_zone_km),
                self.unit_of_measurement)

            self._trace_device_attributes(devicename, 'Results', fct_name, attrs)
            results = ("BaseZone-{} > Zone-{}, GPS-({}, {}), Interval-{}, "
                "Dist-{} {}, TravTime-{} ({}), NextUpdt-{}, Located-{} ({} ago)").format(
                self.base_zone,
                attrs[ATTR_ZONE],
                latitude,
                longitude,
                interval_str,
                self._km_to_mi(dist_from_zone_km),
                self.unit_of_measurement,
                waze_time_msg,
                dir_of_travel,
                self._secs_to_time(next_poll),
                self._time_to_12hrtime(loc_timestamp),
                location_age_str)
            log_msg=("{} Device Tracking Complete, Results-{}").format(
                self._format_fname_devtype(devicename),
                results)
            self.log_info_msg(log_msg)

            event_msg = ("Results: {}").format(results)
            self._save_event(devicename, event_msg)

            return attrs

        except Exception as err:
            attrs_msg = self._internal_error_msg(fct_name, err, 'SetAttrs')
            _LOGGER.exception(err)
            return attrs_msg

#########################################################
#
#   iCloud FmF or FamShr authentication returned an error or no location
#   data is available. Update counter and device attributes and set
#   retry intervals based on current retry count.
#
#########################################################
    def _determine_interval_retry_after_error(self, devicename, retry_cnt, info_msg):
        '''
        Handle errors where the device can not be or should not be updated with
        the current data. The update will be retried 4 times on a 15 sec interval.
        If the error continues, the interval will increased based on the retry
        count using the following cycles:
            1-4   - 15 sec
            5-8   - 1 min
            9-12  - 5min
            13-16 - 15min
            >16   - 30min

        The following errors use this routine:
            - iCloud Authentication errors
            - FmF location data not available
            - Old location
            - Poor GPS Acuracy
        '''

        fct_name = "_determine_interval_retry_after_error"

        base_zone_home = (self.base_zone == HOME)
        devicename_zone = self._format_devicename_zone(devicename)

        try:
            interval = self._get_interval_for_error_retry_cnt(retry_cnt)

            #check if next update is past midnight (next day), if so, adjust it
            next_poll = round((self.this_update_secs + interval)/15, 0) * 15

            # Update all dates and other fields
            interval_str  = self._secs_to_time_str(interval)
            next_updt_str = self._secs_to_time(next_poll)
            last_updt_str = self._secs_to_time(self.this_update_secs)

            self.interval_seconds[devicename_zone] = interval
            self.last_update_secs[devicename_zone] = self.this_update_secs
            self.next_update_secs[devicename_zone] = next_poll
            self.last_update_time[devicename_zone] = last_updt_str
            self.next_update_time[devicename_zone] = next_updt_str
            self.interval_str[devicename_zone]     = interval_str
            self.count_update_ignore[devicename]  += 1

            attrs = {}
            attrs[ATTR_LAST_UPDATE_TIME] = last_updt_str
            attrs[ATTR_INTERVAL]         = interval_str
            attrs[ATTR_NEXT_UPDATE_TIME] = next_updt_str
            attrs[ATTR_POLL_COUNT]       = self._format_poll_count(devicename)
            attrs[ATTR_INFO]             = "●" + info_msg

            this_zone = self.state_this_poll.get(devicename)
            this_zone = self._format_zone_name(devicename, this_zone)
            last_zone = self.state_last_poll.get(devicename)
            last_zone = self._format_zone_name(devicename, last_zone)

            if self._is_inzone(devicename):
                latitude  = self.zone_lat.get(this_zone)
                longitude = self.zone_long.get(this_zone)

            elif self._was_inzone(devicename):
                latitude  = self.zone_lat.get(last_zone)
                longitude = self.zone_long.get(last_zone)
            else:
                latitude  = self.last_lat.get(devicename)
                longitude = self.last_long.get(devicename)

            if latitude == None or longitude == None:
                latitude  = self.last_lat.get(devicename)
                longitude = self.last_long.get(devicename)
            if latitude == None or longitude == None:
                latitude  = self.zone_lat.get(last_zone)
                longitude = self.zone_long.get(last_zone)
            if latitude == None or longitude == None:
                event_msg = "Aborting update, no location data"
                self._save_event_halog_error(devicename,event_msg)
                return

            kwargs = self._setup_base_kwargs(devicename,
                latitude, longitude, 0, 0)

            self._update_device_sensors(devicename, kwargs)
            self._update_device_sensors(devicename, attrs)
            self._update_device_attributes(devicename, kwargs, attrs, 'DetIntlErrorRetry')

            self.device_being_updated_flag[devicename] = False

            log_msg = ("►DETERMINE INTERVAL ERROR RETRY, ThisZone={}, "
                "LastZone={}, GPS = ({}, {})").format(
                this_zone,
                last_zone,
                latitude,
                longitude)
            self.log_debug_interval_msg(devicename, log_msg)
            log_msg = ("►DETERMINE INTERVAL ERROR RETRY, Interval={}, "
                "LastUpdt={}, NextUpdt={}, Info={}").format(
                interval_str,
                last_updt_str,
                next_updt_str,
                info_msg)
            self.log_debug_interval_msg(devicename, log_msg)

        except Exception as err:
            _LOGGER.exception(err)

#########################################################
#
#   UPDATE DEVICE LOCATION & INFORMATION ATTRIBUTE FUNCTIONS
#
#########################################################
    def _get_distance_data(self, devicename, latitude, longitude,
                                gps_accuracy, location_isold_flag):
        """ Determine the location of the device.
            Returns:
                - current_zone (current zone from lat & long)
                  set to HOME if distance < home zone radius
                - dist_from_zone_km (mi or km)
                - dist_traveled (since last poll)
                - dir_of_travel (towards, away_from, stationary, in_zone,
                                       left_zone, near_home)
        """

        fct_name = '_get_distance_data'

        try:
            if latitude == None or longitude == None:
                attrs = self._internal_error_msg(fct_name, 'lat/long=None', 'NoLocation')
                return ('ERROR', attrs)

            base_zone_home = (self.base_zone == HOME)
            devicename_zone = self._format_devicename_zone(devicename)

            log_msg = ("►GET DEVICE DISTANCE DATA Entered")
            self.log_debug_interval_msg(devicename, log_msg)

            last_dir_of_travel        = NOT_SET
            last_dist_from_zone_km       = 0
            last_waze_time            = 0
            last_lat                  = self.base_zone_lat
            last_long                 = self.base_zone_long
            dev_timestamp_secs        = 0

            current_zone              = self.base_zone
            calc_dist_from_zone_km       = 0
            calc_dist_last_poll_moved_km = 0
            calc_dist_from_zone_moved_km = 0


            #Get the devicename's icloud3 attributes
            entity_id = self.device_tracker_entity.get(devicename)
            attrs     = self._get_device_attributes(entity_id)

            self._trace_device_attributes(devicename, 'Read', fct_name, attrs)

        except Exception as err:
            _LOGGER.exception(err)
            error_msg = ("Entity={}, Err={}").format(entity_id, err)
            attrs = self._internal_error_msg(fct_name, error_msg, 'GetAttrs')
            return ('ERROR', attrs)

        try:
            #Not available if first time after reset
            if self.state_last_poll.get(devicename) != NOT_SET:
                log_msg = ("Distance info available")
                if ATTR_TIMESTAMP in attrs:
                    dev_timestamp_secs = attrs[ATTR_TIMESTAMP]
                    dev_timestamp_secs = self._timestamp_to_time(dev_timestamp_secs)
                else:
                    dev_timestamp_secs = 0

                last_dist_from_zone_km_s = self._get_attr(attrs, ATTR_ZONE_DISTANCE, NUMERIC)
                last_dist_from_zone_km   = self._mi_to_km(last_dist_from_zone_km_s)

                last_waze_time        = self._get_attr(attrs, ATTR_WAZE_TIME)
                last_dir_of_travel    = self._get_attr(attrs, ATTR_DIR_OF_TRAVEL)
                last_dir_of_travel    = last_dir_of_travel.replace('*', '', 99)
                last_dir_of_travel    = last_dir_of_travel.replace('?', '', 99)
                last_lat              = self.last_lat.get(devicename)
                last_long             = self.last_long.get(devicename)

            #get last interval
            interval_str = self.interval_str.get(devicename_zone)
            interval     = self._time_str_to_secs(interval_str)

            this_lat  = latitude
            this_long = longitude

        except Exception as err:
            _LOGGER.exception(err)
            attrs = self._internal_error_msg(fct_name, err, 'SetupLocation')
            return ('ERROR', attrs)

        try:
            current_zone = self._get_current_zone(devicename, this_lat, this_long)

            log_msg = ("►LAT-LONG GPS INITIALIZED {}, LastDirOfTrav={}, "
                "LastGPS=({}, {}), ThisGPS=({}, {}, UsingGPS=({}, {}), "
                "GPS.Accur={}, GPS.Threshold={}").format(
                current_zone,
                last_dir_of_travel,
                last_lat,
                last_long,
                this_lat,
                this_long,
                latitude,
                longitude,
                gps_accuracy,
                self.gps_accuracy_threshold)
            self.log_debug_interval_msg(devicename, log_msg)

        except Exception as err:
            _LOGGER.exception(err)
            attrs = self._internal_error_msg(fct_name, err, 'GetCurrZone')
            return ('ERROR', attrs)

        try:
            # Get Waze distance & time
            #   Will return [error, 0, 0, 0] if error
            #               [out_of_range, dist, time, info] if
            #                           last_dist_from_zone_km >
            #                           last distance from home
            #               [ok, 0, 0, 0]  if zone=home
            #               [ok, distFmHome, timeFmHome, info] if OK

            calc_dist_from_zone_km       = self._calc_distance_km(this_lat, this_long,
                                            self.base_zone_lat, self.base_zone_long)
            calc_dist_last_poll_moved_km = self._calc_distance_km(last_lat, last_long,
                                            this_lat, this_long)
            calc_dist_from_zone_moved_km= (calc_dist_from_zone_km - last_dist_from_zone_km)
            calc_dist_from_zone_km       = self._round_to_zero(calc_dist_from_zone_km)
            calc_dist_last_poll_moved_km = self._round_to_zero(calc_dist_last_poll_moved_km)
            calc_dist_from_zone_moved_km= self._round_to_zero(calc_dist_from_zone_moved_km)

            if self.distance_method_waze_flag:
                #If waze paused via icloud_command or close to a zone, default to pause
                if self.waze_manual_pause_flag or self.waze_close_to_zone_pause_flag:
                    self.waze_status = WAZE_PAUSED
                else:
                   self.waze_status = WAZE_USED
            else:
                self.waze_status = WAZE_NOT_USED

            debug_log = ("3664 dnZone-{}, wStatus-{}, calc_dist-{}, wManualPauseFlag-{},"
                    "wCloseToZoneFlag-{}").format(devicename_zone,
                    self.waze_status,
                    calc_dist_from_zone_km,
                    self.waze_manual_pause_flag,
                    self.waze_close_to_zone_pause_flag)
            #self._save_event(devicename, debug_log)

            #Make sure distance and zone are correct for HOME, initialize
            if calc_dist_from_zone_km <= .05 or current_zone == self.base_zone:
                current_zone              = self.base_zone
                calc_dist_from_zone_km       = 0
                calc_dist_last_poll_moved_km = 0
                calc_dist_from_zone_moved_km= 0
                self.waze_status          = WAZE_PAUSED

            #Near home & towards or in near_zone
            elif (calc_dist_from_zone_km < 1 and
                    last_dir_of_travel in ('towards', 'near_zone')):
                self.waze_status = WAZE_PAUSED
                self.waze_close_to_zone_pause_flag = True

                log_msg = "Using Calc Method (near Home & towards or Waze off)"
                self.log_debug_interval_msg(devicename, log_msg)
                event_msg = (" Using Calc method, near Home or Waze off")
                #self._save_event(devicename, event_msg)

            #Determine if Waze should be used based on calculated distance
            elif (calc_dist_from_zone_km > self.waze_max_distance or
                  calc_dist_from_zone_km < self.waze_min_distance):
                self.waze_status = WAZE_OUT_OF_RANGE

            #Initialize Waze default fields
            waze_dist_from_zone_km       = calc_dist_from_zone_km
            waze_time_from_zone       = 0
            waze_dist_last_poll_moved_km = calc_dist_last_poll_moved_km
            waze_dist_from_zone_moved_km= calc_dist_from_zone_moved_km
            self.waze_history_data_used_flag[devicename_zone] = False

            #Use Calc if close to home, Waze not accurate when close

            debug_log = ("dnZone-{}, wStatus-{}, calc_dist-{}, wManualPauseFlag-{},"
                    "wCloseToZoneFlag-{}").format(
                    devicename_zone,
                    self.waze_status,
                    calc_dist_from_zone_km,
                    self.waze_manual_pause_flag,
                    self.waze_close_to_zone_pause_flag)
            #self._save_event(devicename, debug_log)

        except Exception as err:
            _LOGGER.exception(err)
            attrs = self._internal_error_msg(fct_name, err, 'InitializeDist')
            return ('ERROR', attrs)

        try:
            if self.waze_status == WAZE_USED:
                try:
                    #See if another device is close with valid Waze data.
                    #If so, use it instead of calling Waze again.
                    waze_dist_time_info = self._get_waze_from_data_history(
                            devicename, calc_dist_from_zone_km,
                            this_lat, this_long)

                    #No Waze data from close device. Get it from Waze
                    if waze_dist_time_info is None:
                        waze_dist_time_info = self._get_waze_data(
                                                devicename,
                                                this_lat, this_long,
                                                last_lat, last_long,
                                                current_zone,
                                                last_dist_from_zone_km)

                    self.waze_status = waze_dist_time_info[0]

                    if self.waze_status != WAZE_ERROR:
                        waze_dist_from_zone_km       = waze_dist_time_info[1]
                        waze_time_from_zone       = waze_dist_time_info[2]
                        waze_dist_last_poll_moved_km = waze_dist_time_info[3]
                        waze_dist_from_zone_moved_km= round(waze_dist_from_zone_km
                                                    - last_dist_from_zone_km, 2)
                        debug_log = ("3740 Waze request successful, distance {}{}, "
                                "time {} min").format(
                                self._km_to_mi(waze_dist_from_zone_km),
                                self.unit_of_measurement,
                                waze_time_from_zone)
                        #self._save_event(devicename, debug_log)

                        #Save new Waze data or retimestamp data from another
                        #device.
                        if (gps_accuracy <= self.gps_accuracy_threshold and
                                location_isold_flag is False):
                            self.waze_distance_history[devicename_zone] = \
                                    [self._time_now_secs(),
                                    this_lat,
                                    this_long,
                                    waze_dist_time_info]

                    else:
                        self._save_event(devicename, "Waze error, no data returned")
                        self.waze_distance_history[devicename_zone] = []

                except Exception as err:
                    self.waze_status = WAZE_ERROR

        except Exception as err:
            attrs = self._internal_error_msg(fct_name, err, 'WazeError')
            #return ('ERROR', attrs)
            self.waze_status = WAZE_ERROR

        try:
            if self.waze_status == WAZE_ERROR:
                waze_dist_from_zone_km       = calc_dist_from_zone_km
                waze_time_from_zone       = 0
                waze_dist_last_poll_moved_km = calc_dist_last_poll_moved_km
                waze_dist_from_zone_moved_km = calc_dist_from_zone_moved_km
                self.waze_distance_history[devicename_zone] = []
                self.waze_history_data_used_flag[devicename_zone] = False

            #don't reset data if poor gps, use the best we have
            if current_zone == self.base_zone:
                distance_method         = 'Home/Calc'
                dist_from_zone_km       = 0
                dist_last_poll_moved_km = 0
                dist_from_zone_moved_km = 0
            elif self.waze_status == WAZE_USED:
                distance_method         = 'Waze'
                dist_from_zone_km       = waze_dist_from_zone_km
                dist_last_poll_moved_km = waze_dist_last_poll_moved_km
                dist_from_zone_moved_km = waze_dist_from_zone_moved_km
            else:
                distance_method         = 'Calc'
                dist_from_zone_km       = calc_dist_from_zone_km
                dist_last_poll_moved_km = calc_dist_last_poll_moved_km
                dist_from_zone_moved_km = calc_dist_from_zone_moved_km

            if dist_from_zone_km > 99: dist_from_zone_km = int(dist_from_zone_km)
            if dist_last_poll_moved_km > 99: dist_last_poll_moved_km = int(dist_last_poll_moved_km)
            if dist_from_zone_moved_km> 99: dist_from_zone_moved_km= int(dist_from_zone_moved_km)

            dist_from_zone_moved_km= self._round_to_zero(dist_from_zone_moved_km)

            log_msg = ("►DISTANCES CALCULATED, "
                "Zone={}, Method={},LastDistFmHome={}, WazeStatus={}").format(
                current_zone,
                distance_method,
                last_dist_from_zone_km,
                self.waze_status)
            self.log_debug_interval_msg(devicename, log_msg)
            log_msg = ("►DISTANCES ...Waze, Dist={}, LastPollMoved={}, "
                "FmHomeMoved={}, Time={}, Status={}").format(
                waze_dist_from_zone_km,
                waze_dist_last_poll_moved_km,
                waze_dist_from_zone_moved_km,
                waze_time_from_zone,
                self.waze_status)
            self.log_debug_interval_msg(devicename, log_msg)
            log_msg = ("►DISTANCES ...Calc, Dist={}, LastPollMoved={}, "
                "FmHomeMoved={}").format(
                calc_dist_from_zone_km,
                calc_dist_last_poll_moved_km,
                calc_dist_from_zone_moved_km)
            self.log_debug_interval_msg(devicename, log_msg)

            #if didn't move far enough to determine towards or away_from,
            #keep the current distance and add it to the distance on the next
            #poll
            if (dist_from_zone_moved_km> -.3 and dist_from_zone_moved_km< .3):
                dist_from_zone_moved_km+= \
                        self.dist_from_zone_km_small_move_total.get(devicename)
                self.dist_from_zone_km_small_move_total[devicename] = \
                        dist_from_zone_moved_km
            else:
                 self.dist_from_zone_km_small_move_total[devicename] = 0

        except Exception as err:
            _LOGGER.exception(err)
            attrs = self._internal_error_msg(fct_name, err, 'CalcDist')
            return ('ERROR', attrs)

        try:
            section = "dir_of_trav"
            dir_of_travel   = ''
            dir_of_trav_msg = ''
            if current_zone not in (NOT_HOME, 'near_zone'):
                dir_of_travel   = 'in_zone'
                dir_of_trav_msg = ("Zone={}").format(current_zone)

            elif last_dir_of_travel == "in_zone":
                dir_of_travel   = 'left_zone'
                dir_of_trav_msg = ("LastZone={}").format(last_dir_of_travel)

            elif dist_from_zone_moved_km<= -.3:            #.18 mi
                dir_of_travel   = 'towards'
                dir_of_trav_msg = ("Dist={}").format(dist_from_zone_moved_km)

            elif dist_from_zone_moved_km>= .3:             #.18 mi
                dir_of_travel   = AWAY_FROM
                dir_of_trav_msg = ("Dist={}").format(dist_from_zone_moved_km)

            elif self.poor_gps_accuracy_flag.get(devicename):
                dir_of_travel   = 'Poor.GPS'
                dir_of_trav_msg = ("Poor.GPS={}").format(gps_accuracy)

            else:
                #didn't move far enough to tell current direction
                dir_of_travel   = ("{}?").format(last_dir_of_travel)
                dir_of_trav_msg = ("Moved={}").format(dist_last_poll_moved_km)

            #If moved more than stationary zone limit (~.06km(200ft)),
            #reset check StatZone 5-min timer and check again next poll
            #Use calc distance rather than waze for better accuracy
            section = "test if home"
            if (calc_dist_from_zone_km > self.stat_min_dist_from_zone_km and
                current_zone == NOT_HOME):

                section = "test moved"
                reset_stat_zone_flag = False
                if devicename not in self.stat_zone_moved_total:
                    reset_stat_zone_flag = True

                elif (calc_dist_last_poll_moved_km > self.stat_dist_move_limit):
                    reset_stat_zone_flag = True

                if reset_stat_zone_flag:
                    section = "test moved-reset stat zone "
                    self.stat_zone_moved_total[devicename] = 0
                    self.stat_zone_timer[devicename] = \
                        self.this_update_secs + self.stat_zone_still_time

                    log_msg = ("►STATIONARY ZONE, Reset timer, "
                        "Moved={}, Timer={}").format(
                        calc_dist_last_poll_moved_km,
                        self._secs_to_time(self.stat_zone_timer.get(devicename)))
                    self.log_debug_interval_msg(devicename, log_msg)

                #If moved less than the stationary zone limit, update the
                #distance moved and check to see if now in a stationary zone
                elif devicename in self.stat_zone_moved_total:
                    section = "StatZonePrep"
                    move_into_stationary_zone_flag = False
                    self.stat_zone_moved_total[devicename] += calc_dist_last_poll_moved_km
                    stat_zone_timer_left       = self.stat_zone_timer.get(devicename) - self.this_update_secs
                    stat_zone_timer_close_left = stat_zone_timer_left - self.stat_zone_still_time/2

                    log_msg = ("►STATIONARY ZONE, Small movement check, "
                        "TotalMoved={}, Timer={}, TimerLeft={}, CloseTimerLeft={}, "
                        "DistFmZone={}, CloseDist={}").format(
                        self.stat_zone_moved_total.get(devicename),
                        self._secs_to_time(self.stat_zone_timer.get(devicename)),
                        stat_zone_timer_left,
                        stat_zone_timer_close_left,
                        dist_from_zone_km,
                        self.zone_radius_km.get(self.base_zone)*4)
                    self.log_debug_interval_msg(devicename, log_msg)

                    section = "CheckNowInStatZone"

                    #See if moved less than the stationary zone movement limit
                    if self.stat_zone_moved_total.get(devicename) <= self.stat_dist_move_limit:
                        #See if time has expired
                        if stat_zone_timer_left <= 0:
                            move_into_stationary_zone_flag = True

                        #See if close to zone and 1/2 of the timer is left
                        elif (dist_from_zone_km <= self.zone_radius_km.get(self.base_zone)*4 and
                              (stat_zone_timer_close_left <= 0)):
                            move_into_stationary_zone_flag = True

                    #If updating via the ios app and the current state is stationary,
                    #make sure it is kept in the stationary zone
                    elif (self.iosapp_update_flag.get(devicename) and
                          self.state_this_poll.get(devicename) == STATIONARY):
                        move_into_stationary_zone_flag = True

                    if move_into_stationary_zone_flag:
                        dir_of_travel   = STATIONARY
                        dir_of_trav_msg = "Age={}s, Moved={}".format(
                            self._secs_to(
                                self.stat_zone_timer.get(devicename)),
                                self.stat_zone_moved_total.get(devicename))
                else:
                    self.stat_zone_moved_total[devicename] = 0

            section = "Finalize"
            dir_of_trav_msg = ("{}({})").format(
                        dir_of_travel, dir_of_trav_msg)

            log_msg = ("►DIR OF TRAVEL DETERMINED, {}").format(
                        dir_of_trav_msg)
            self.log_debug_interval_msg(devicename, log_msg)

            dist_from_zone_km            = self._round_to_zero(dist_from_zone_km)
            dist_from_zone_moved_km      = self._round_to_zero(dist_from_zone_moved_km)
            dist_last_poll_moved_km      = self._round_to_zero(dist_last_poll_moved_km)
            waze_dist_from_zone_km       = self._round_to_zero(waze_dist_from_zone_km)
            calc_dist_from_zone_moved_km = self._round_to_zero(calc_dist_from_zone_moved_km)
            waze_dist_last_poll_moved_km = self._round_to_zero(waze_dist_last_poll_moved_km)
            calc_dist_last_poll_moved_km = self._round_to_zero(calc_dist_last_poll_moved_km)
            last_dist_from_zone_km       = self._round_to_zero(last_dist_from_zone_km)

            log_msg = ("►GET DEVICE DISTANCE DATA Complete, "
                        "CurrentZone={}, DistFmHome={}, DistFmHomeMoved={}, "
                        "DistLastPollMoved={}").format(
                        current_zone, dist_from_zone_km,
                        dist_from_zone_moved_km, dist_last_poll_moved_km)
            self.log_debug_interval_msg(devicename, log_msg)

            distance_data = (current_zone, dir_of_travel,
                    dist_from_zone_km, dist_from_zone_moved_km, dist_last_poll_moved_km,
                    waze_dist_from_zone_km, calc_dist_from_zone_km,
                    waze_dist_from_zone_moved_km, calc_dist_from_zone_moved_km,
                    waze_dist_last_poll_moved_km, calc_dist_last_poll_moved_km,
                    waze_time_from_zone, last_dist_from_zone_km,
                    last_dir_of_travel, dir_of_trav_msg, dev_timestamp_secs)

            log_msg = ("►DISTANCE DATA={}-{}").format(
                        devicename, distance_data)
            self.log_debug_msg(devicename, log_msg)

            return  distance_data

        except Exception as err:
           _LOGGER.exception(err)
           attrs = self._internal_error_msg(fct_name+section, err, 'Finalize')
           return ('ERROR', attrs)

#########################################################
#
#    DEVICE ATTRIBUTES ROUTINES
#
#########################################################
    def _get_current_state(self, entity_id):
        """
        Get current state of the device_tracker entity
        (home, away, other state)
        """

        try:
            device_state = self.hass.states.get(entity_id).state

            if device_state:
                if device_state.lower() == 'not set':
                    current_state = NOT_SET
                else:
                    current_state = device_state
            else:
                current_state = NOT_HOME

        except Exception as err:
            #_LOGGER.exception(err)
            current_state = NOT_SET

        return current_state.lower()
#--------------------------------------------------------------------
    def _get_entity_last_changed_time(self, entity_id):
        """
        Get entity's last changed time attribute
        Last changed time format '2019-09-09 14:02:45'
        """

        try:
            lc_time      = str(self.hass.states.get(entity_id).last_changed)
            lc_time_w    = lc_time.replace(" ","T",1)
            lc_time_secs = self._timestamp_to_secs(lc_time_w, UTC_TIME)

            return lc_time[11:19], lc_time_secs

        except Exception as err:
            _LOGGER.exception(err)
            return '', 0
#--------------------------------------------------------------------
    def _get_device_attributes(self, entity_id):
        """ Get attributes of the device """

        try:
            dev_data  = self.hass.states.get(entity_id)
            dev_attrs = dev_data.attributes

            retry_cnt = 0
            while retry_cnt < 10:
                if dev_attrs:
                    break
                retry_cnt += 1
                log_msg = ("No attribute data returned for {}. Retrying #{}").format(
                    entity_id,
                    retry_cnt)
                self.log_debug_msg('*', log_msg)

        except (KeyError, AttributeError):
            dev_attrs = {}
            pass

        except Exception as err:
            _LOGGER.exception(err)
            dev_attrs = {}
            dev_attrs[ATTR_TRIGGER] = 'Error {}'.format(err)

        return dict(dev_attrs)

#--------------------------------------------------------------------
    @staticmethod
    def _get_attr(attributes, attribute_name, numeric = False):
        ''' Get an attribute out of the attrs attributes if it exists'''
        if attribute_name in attributes:
            return attributes[attribute_name]
        elif numeric:
            return 0
        else:
            return ''

#--------------------------------------------------------------------
    def _update_device_attributes(self, devicename, kwargs: str = None,
                        attrs: str = None, fct_name: str = 'Unknown'):
        """
        Update the device and attributes with new information
        On Entry, kwargs = {} or contains the base attributes.

        Trace the interesting attributes if debugging.

        Full set of attributes is:
        'gps': (27.726639, -80.3904565), 'battery': 61, 'gps_accuracy': 65.0
        'dev_id': 'lillian_iphone', 'host_name': 'Lillian',
        'location_name': HOME, 'source_type': 'gps',
        'attributes': {'interval': '2 hrs', 'last_update': '10:55:17',
        'next_update': '12:55:15', 'travel_time': '', 'distance': 0,
        'calc_distance': 0, 'waze_distance': 0, 'dir_of_travel': 'in_zone',
        'travel_distance': 0, 'info': ' ●Battery-61%',
        'group': 'gary_icloud', 'authenticated': '02/22/19 10:55:10',
        'last_located': '10:55:15', 'device_status': 'online',
        'low_power_mode': False, 'battery_status': 'Charging',
        'tracked_devices': 'gary_icloud/gary_iphone,
        gary_icloud/lillian_iphone', 'trigger': 'iCloud',
        'timestamp': '2019-02-22T10:55:17.543', 'poll_count': '1:0:1'}

        {'source_type': 'gps', 'latitude': 27.726639, 'longitude': -80.3904565,
        'gps_accuracy': 65.0, 'battery': 93, 'zone': HOME,
        'last_zone': HOME, 'zone_timestamp': '03/13/19, 9:47:35',
        'trigger': 'iCloud', 'timestamp': '2019-03-13T09:47:35.405',
        'interval': '2 hrs', 'travel_time': '', 'distance': 0,
        'calc_distance': 0, 'waze_distance': '', 'last_located': '9:47:34',
        'last_update': '9:47:35', 'next_update': '11:47:30',
        'poll_count': '1:0:2', 'dir_of_travel': 'in_zone',
        'travel_distance': 0, 'info': ' ●Battery-93%',
        'battery_status': 'NotCharging', 'device_status':
        'online', 'low_power_mode': False,
        'authenticated': '03/13/19, 9:47:26',
        'tracked_devices': 'gary_icloud/gary_iphone, gary_icloud/lillian_iphone',
        'group': 'gary_icloud', 'friendly_name': 'Gary',
        'icon': 'mdi:cellphone-iphone',
        'entity_picture': '/local/gary-caller_id.png'}
        """

        state        = self.state_this_poll.get(devicename)
        current_zone = self.zone_current.get(devicename)


        #######################################################################
        #The current zone is based on location of the device after it is looked
        #up in the zone tables.
        #The state is from the original trigger value when the poll started.
        #If the device went from one zone to another zone, an enter/exit trigger
        #may not have been issued. If the trigger was the next update time
        #reached, the state and zone many now not match. (v2.0.2)

        if state == NOT_SET or current_zone == NOT_SET or current_zone == '':
            pass

        #If state is 'stationary' and in a stationary zone, nothing to do
        elif state == STATIONARY and instr(current_zone, STATIONARY):
            pass

        #If state is 'stationary' and in another zone, reset the state to the
        #current zone that was based on the device location.
        #If the state is in a zone but not the current zone, change the state
        #to the current zone that was based on the device location.
        elif ((state == STATIONARY and self._is_inzone(current_zone)) or
                (self._is_inzone(state) and self._is_inzone(current_zone) and
                    state != current_zone)):
            event_msg = ("State/Zone mismatch > Setting `state` value ({}) "
                    "to `zone` value ({})").format(
                    state, current_zone)
            self._save_event(devicename, event_msg)
            state = current_zone

        '''
        #Make sure stationary zone location is correct
        stat_zone_name = self._format_zone_name(devicename, STATIONARY)
        TRACE("Correcting Stationary Zone",instr(current_zone, STATIONARY), self.zone_lat.get(stat_zone_name))
        if (instr(current_zone, STATIONARY) == False and
                stat_zone_name in self.zone_lat) and
                self.zone_lat.get(stat_zone_name) != self.stat_zone_base_lat):
            self._update_stationary_zone(
                devicename,
                self.stat_zone_base_lat,
                self.stat_zone_base_long,
                STATIONARY_ZONE_HIDDEN)
            self.in_stationary_zone_flag[devicename] = False
        '''
        #######################################################################



        #Get friendly name or capitalize and reformat state
        if self._is_inzoneZ(state):
            state_fn = self.zone_friendly_name.get(state)

            if state_fn:
                state = state_fn
            else:
                state = state.replace('_', ' ', 99)
                state = state.title()

            if state == 'Home':
                state = HOME

        #Update the device timestamp
        if not attrs:
            attrs  = {}
        if ATTR_TIMESTAMP in attrs:
            timestamp = attrs[ATTR_TIMESTAMP]
        else:
            timestamp = dt_util.now().strftime(ATTR_TIMESTAMP_FORMAT)[0:19]
            attrs[ATTR_TIMESTAMP] = timestamp

        #Calculate and display how long the update took
        update_took_time =  round(time.time() - self.update_timer.get(devicename), 2)
        if update_took_time > 3 and ATTR_INFO in attrs:
            attrs[ATTR_INFO] = "{} ●Took {}s".format(
                    attrs[ATTR_INFO],
                    update_took_time)

        attrs[ATTR_NAME]            = self.friendly_name.get(devicename)
        attrs[ATTR_AUTHENTICATED]   = self.authenticated_time
        attrs[ATTR_GROUP]           = self.group
        attrs[ATTR_TRACKING]        = self.track_devicename_list
        attrs[ATTR_ICLOUD3_VERSION] = VERSION

        #Add update time to trigger to be able to detect trigger change
        new_trigger = self.trigger.get(devicename)
        #if new_trigger.find('@') == -1:
        if instr(new_trigger, '@') == False:
            new_trigger = '{}@{}'.format(new_trigger, self._secs_to_time(self.this_update_secs))
            self.trigger[devicename] = new_trigger

        attrs[ATTR_TRIGGER] = new_trigger

        #Update sensor.<devicename>_last_update_trigger if IOS App v2 detected
        #and iCloud3 has been running for at least 30 secs to let HA &
        #mobile_app start up to avoid error if iC3 lods before the mobile_app
        if self.iosapp_version.get(devicename) == 2:
            if self.this_update_secs >= self.icloud3_started_secs + 30:
                sensor_entity = 'sensor.{}'.format(
                    self.iosapp_v2_last_trigger_entity.get(devicename))
                sensor_attrs = {}
                state_value  = self.trigger.get(devicename)
                self.hass.states.set(sensor_entity, state_value, sensor_attrs)

        #Set the gps attribute and update the attributes via self.see
        if kwargs == {} or not kwargs:
            kwargs = self._setup_base_kwargs(
                devicename,
                self.last_lat.get(devicename),
                self.last_long.get(devicename),
                0, 0)

        kwargs['dev_id']        = devicename
        kwargs['host_name']     = self.friendly_name.get(devicename)
        kwargs['location_name'] = state
        kwargs['source_type']   = 'gps'
        kwargs[ATTR_ATTRIBUTES] = attrs

        self.see(**kwargs)

        if state == "Not Set":
            state = "not_set"

        self.state_this_poll[devicename] = state.lower()

        self._trace_device_attributes(devicename, 'Write', fct_name, kwargs)

        if timestamp == '':         #Bypass if not initializing
            return

        retry_cnt = 1
        timestamp = timestamp[10:]      #Strip off date

        #Quite often, the attribute update has not actually taken
        #before other code is executed and errors occur.
        #Reread the attributes of the ones just updated to make sure they
        #were updated corectly. Verify by comparing the timestamps. If
        #differet, retry the attribute update. HA runs in multiple threads.
        try:
            entity_id = self.device_tracker_entity.get(devicename)
            while retry_cnt < 99:
                chk_see_attrs  = self._get_device_attributes(entity_id)
                chk_timestamp  = str(chk_see_attrs.get(ATTR_TIMESTAMP))
                chk_timestamp  = chk_timestamp[10:]

                if timestamp == chk_timestamp:
                    break

                log_msg = (
                    "Verify Check #{}. Expected {}, Read {}").format(
                    retry_cnt,
                    timestamp,
                    chk_timestamp)
                self.log_debug_msg(devicename, log_msg)

                #retry_cnt_msg = "Write Reread{}".format(retry_cnt)
                #self._trace_device_attributes(
                #    devicename, retry_cnt_msg, fct_name, chk_see_attrs)

                if (retry_cnt % 10) == 0:
                    time.sleep(1)
                retry_cnt += 1

                self.see(**kwargs)

        except Exception as err:
            _LOGGER.exception(err)

        return

#--------------------------------------------------------------------
    def _setup_base_kwargs(self, devicename, latitude, longitude,
            battery, gps_accuracy):

        #check to see if device set up yet
        state = self.state_this_poll.get(devicename)
        zone_name = None

        if latitude == self.zone_home_lat:
            pass
        elif state == NOT_SET:
            zone_name = self.base_zone

        #if in zone, replace lat/long with zone center lat/long
        elif self._is_inzoneZ(state):
            zone_name = self._format_zone_name(devicename, state)
        
        '''
        #v2.0.4-Added 'zone_name == state' check
        if zone_name and zone_name == state:
            zone_lat  = self.zone_lat.get(zone_name)
            zone_long = self.zone_long.get(zone_name)
            #debug TRACE
            if zone_lat and (latitude != zone_lat or longitude != zone_long):
                if self._update_last_latitude_longitude(devicename, zone_lat, zone_long, 4450):
                    event_msg  = ("Moving to zone {} center, "
                        "GPS-({}, {}) to ({}, {}), {}-{}").format(
                        zone_name,
                        latitude,
                        longitude,
                        zone_lat,
                        zone_long,
                        self.state_this_poll.get(devicename),
                        state)
                    self._save_event_halog_debug(devicename, event_msg)

                    latitude  = zone_lat
                    longitude = zone_long
                    
        '''
        #v2.1
        debug_msg=(f"zone_name={zone_name}, inzone-state={self._is_inzoneZ(state)}")
        self.log_debug_msg(devicename, debug_msg)
        
        if zone_name and self._is_inzoneZ(state):
            zone_lat  = self.zone_lat.get(zone_name)
            zone_long = self.zone_long.get(zone_name)
            zone_dist = self._calc_distance_m(latitude, longitude, zone_lat, zone_long) 
            
            debug_msg=(f"zone_lat/long=({zone_lat}, {zone_long}), "
                    f"lat-long=({latitude}, {longitude}), zone_dist={zone_dist}, "
                    f"zone-radius={self.zone_radius_km.get(zone_name)}")
            self.log_debug_msg(devicename, debug_msg)
                                        
            #Move center of stationary zone to new location if more than 10m from old loc
            if instr(zone_name, STATIONARY) and zone_dist > 10:
                rtn_code = self._update_stationary_zone(
                        devicename,
                        latitude,
                        longitude,
                        STATIONARY_ZONE_VISIBLE)
                        
            #inside zone, move to center
            #elif (zone_dist <= self.zone_radius_km.get(zone_name)*1000 and 
            elif (zone_dist <= self.zone_radius_m.get(zone_name) and 
                    (latitude != zone_lat or longitude != zone_long)):
                event_msg  = ("Moving to zone center > {}, "
                    "GPS-({}, {}) to ({}, {}), Dist-{}m").format(
                    zone_name,
                    latitude,
                    longitude,
                    zone_lat,
                    zone_long,
                    zone_dist)
                self._save_event(devicename, event_msg)
                self.log_debug_msg(devicename, event_msg)
                
                latitude  = zone_lat
                longitude = zone_long
                self.last_lat[devicename]  = zone_lat
                self.last_long[devicename] = zone_long

        gps_lat_long           = (latitude, longitude)
        kwargs                 = {}
        kwargs['gps']          = gps_lat_long
        kwargs[ATTR_BATTERY]   = int(battery)
        kwargs[ATTR_GPS_ACCURACY] = gps_accuracy

        return kwargs

#--------------------------------------------------------------------
    def _format_entity_id(self, devicename):

        return '{}.{}'.format(DOMAIN, devicename)

#--------------------------------------------------------------------
    def _format_fname_devtype(self, devicename):
        return "{}({})".format(
                self.friendly_name.get(devicename),
                self.device_type.get(devicename))

#--------------------------------------------------------------------
    def _format_devicename_zone(self, devicename, zone = None):
        if zone is None:
            zone = self.base_zone
        return "{}:{}".format(devicename, zone)
#--------------------------------------------------------------------
    def _trace_device_attributes(self, devicename, description,
            fct_name, attrs):

        try:

            #Extract only attrs needed to update the device
            attrs_in_attrs = {}
            if 'iCloud' in description:
                attrs_base_elements = TRACE_ICLOUD_ATTRS_BASE
                if ATTR_LOCATION in attrs:
                    attrs_in_attrs  = attrs[ATTR_LOCATION]
            elif 'Zone' in description:
                attrs_base_elements = attrs
            else:
                attrs_base_elements = TRACE_ATTRS_BASE
                if ATTR_ATTRIBUTES in attrs:
                    attrs_in_attrs  = attrs[ATTR_ATTRIBUTES]

            trace_attrs = {k: v for k, v in attrs.items() \
                                       if k in attrs_base_elements}

            trace_attrs_in_attrs = {k: v for k, v in attrs_in_attrs.items() \
                                       if k in attrs_base_elements}

            #trace_attrs = attrs

            ls = self.state_last_poll.get(devicename)
            cs = self.state_this_poll.get(devicename)
            log_msg = ("_ {} Attrs ___ ({})".format(description, fct_name))
            self.log_debug_msg(devicename, log_msg)

            log_msg = ("{} Last State={}, This State={}".format(description, ls, cs))
            self.log_debug_msg(devicename, log_msg)

            log_msg = ("{} Attrs={}{}").format(description, trace_attrs, trace_attrs_in_attrs)
            self.log_debug_msg(devicename, log_msg)


        except Exception as err:
            _LOGGER.exception(err)

        return

#--------------------------------------------------------------------
    def _notify_device(self, message, devicename = None):
        return
        for devicename_x in self.tracked_devices:
            if devicename and devicename_x != devicename:
                continue

            entity_id    = "ios_{}".format(devicename_x)
            msg = ('"{}"').format(message)
            service_data = {"message": "test message"}

            #_LOGGER.warning(service_data_q)
            #_LOGGER.warning(service_data)
            self.hass.services.call("notify", entity_id, service_data)

#--------------------------------------------------------------------
    def _get_iosappv2_device_sensor_trigger(self, devicename):

        entity_id = 'sensor.{}'.format(
                self.iosapp_v2_last_trigger_entity.get(devicename))

        try:
            if self.iosapp_version.get(devicename) == 2:
                dev_trigger = self.hass.states.get(entity_id).state
                lc_trigger_time, lc_trigger_time_secs = \
                        self._get_entity_last_changed_time(entity_id)

                return dev_trigger, lc_trigger_time, lc_trigger_time_secs

            else:
                return '', '', 0

        except Exception as err:
            _LOGGER.exception(err)
            return '', '', 0

#########################################################
#
#   DEVICE ZONE ROUTINES
#
#########################################################
    def _get_current_zone(self, devicename, latitude, longitude):

        '''
        Get current zone of the device based on the location """

        This is the same code as (active_zone/async_active_zone) in zone.py
        but inserted here to use zone table loaded at startup rather than
        calling hass on all polls
        '''
        zone_selected_dist = 99999
        zone_selected      = None

        log_msg = f"Select Zone > GPS-({latitude}, {longitude}), "
        for zone in self.zone_lat:
            #Skip another device's stationary zone
            if instr(zone, STATIONARY) and instr(zone, devicename) == False:
                continue

            zone_dist = self._calc_distance_km(latitude, longitude,
                self.zone_lat.get(zone), self.zone_long.get(zone))

            in_zone      = zone_dist < self.zone_radius_km.get(zone)
            closer_zone  = zone_selected is None or zone_dist < zone_selected_dist
            smaller_zone = (zone_dist == zone_selected_dist and
                    self.zone_radius_km.get(zone) < self.zone_radius_km.get(zone_selected))

            if in_zone and (closer_zone or smaller_zone):
                zone_selected_dist  = round(zone_dist, 2)
                zone_selected       = zone
            
            log_msg += ("{}-{}km/r{}, ").format(
                zone,
                zone_dist,
                round(self.zone_radius_m.get(zone)))
                #round(self.zone_radius_km.get(zone)*1000)) 
               
        
        log_msg = ("{} > Selected-{}").format(log_msg[:-2], zone_selected)
        self.log_debug_msg(devicename, log_msg)
        self._save_event(devicename, log_msg)  

        if zone_selected is None:
            zone_selected      = NOT_HOME
            zone_selected_dist = 0

        elif instr(zone,'nearzone'):
            zone_selected = 'near_zone'

        #If the zone changed from a previous poll, save it and set the new one
        if (self.zone_current.get(devicename) != zone_selected):
            self.zone_last[devicename] = self.zone_current.get(devicename)

            #First time thru, initialize zone_last
            if (self.zone_last.get(devicename) == ''):
                self.zone_last[devicename]  = zone_selected

            self.zone_current[devicename]   = zone_selected
            self.zone_timestamp[devicename] = \
                        dt_util.now().strftime(self.um_date_time_strfmt)

        log_msg = ("►GET CURRENT ZONE END, Zone={}, GPS=({}, {}), "
                        "StateThisPoll={}, LastZone={}, ThisZone={}").format(
                    zone_selected, latitude, longitude,
                    self.state_this_poll.get(devicename),
                    self.zone_last.get(devicename),
                    self.zone_current.get(devicename))
        self.log_debug_msg(devicename, log_msg)

        return zone_selected

#--------------------------------------------------------------------
    @staticmethod
    def _get_zone_names(zone_name):
        """
        Make zone_names 1, 2, & 3 out of the zone_name value for sensors

        name1 = home --> Home
                not_home --> Away
                gary_iphone_stationary --> Stationary
        name2 = gary_iphone_stationary --> Gary Iphone Stationary
                office_bldg_1 --> Office Bldg 1
        name3 = gary_iphone_stationary --> GaryIphoneStationary
                office__bldg_1 --> Office Bldg1
        """
        if zone_name:
            if STATIONARY in zone_name:
                name1 = 'Stationary'
            elif NOT_HOME in zone_name:
                name1 = 'Away'
            else:
                name1 = zone_name.title()

            if zone_name == 'zone':
                badge_state = name1

            name2 = zone_name.title().replace('_', ' ', 99)
            name3 = zone_name.title().replace('_', '', 99)
        else:
            name1 = NOT_SET
            name2 = 'Not Set'
            name3 = 'NotSet'

        return [zone_name, name1, name2, name3]

#--------------------------------------------------------------------
    @staticmethod
    def _format_zone_name(devicename, zone):
        '''
        The Stationary zone info is kept by 'devicename_stationary'. Other zones
        are kept as 'zone'. Format the name based on the zone.
        '''
        return "{}_stationary".format(devicename) if zone == STATIONARY else zone

#--------------------------------------------------------------------
    def _current_zone_distance_m(self, devicename, zone, latitude, longitude):
        '''
        Get the distance from zone `zone`
        '''

        zone_dist = 99999

        if self.zone_lat.get(zone):
            zone_name = self._format_zone_name(devicename, zone)

            zone_dist = self._calc_distance_m(
                            latitude,
                            longitude,
                            self.zone_lat.get(zone_name),
                            self.zone_long.get(zone_name))

            log_msg = ("INZONE 1KM CHECK {}, Zone={}, CurrGPS=({}, {}), "
                "ZoneGPS=({}, {}), Dist={}m").format(
                devicename,
                zone_name,
                latitude,
                longitude,
                self.zone_lat.get(zone_name),
                self.zone_long.get(zone_name),
                zone_dist)
            self.log_debug_msg(devicename, log_msg)

        return zone_dist

#--------------------------------------------------------------------
    def _is_inzone(self, devicename):
        return (self.state_this_poll.get(devicename) != NOT_HOME)

    def _isnot_inzone(self, devicename):
        return (self.state_this_poll.get(devicename) == NOT_HOME)

    def _was_inzone(self, devicename):
        return (self.state_last_poll.get(devicename) != NOT_HOME)

    def _wasnot_inzone(self, devicename):
        return (self.state_last_poll.get(devicename) == NOT_HOME)

    @staticmethod
    def _is_inzoneZ(current_zone):
        return (current_zone != NOT_HOME)

    @staticmethod
    def _isnot_inzoneZ(current_zone):
        #_LOGGER.warning("_isnot_inzoneZ = %s",(current_zone == NOT_HOME))
        return (current_zone == NOT_HOME)
#--------------------------------------------------------------------
    def _wait_if_update_in_process(self, devicename=None):
        #An update is in process, must wait until done
        wait_cnt = 0
        while self.update_in_process_flag:
            wait_cnt += 1
            if devicename:
                attrs = {}
                attrs[ATTR_INTERVAL] = ("►WAIT-{}").format(wait_cnt)

                self._update_device_sensors(devicename, attrs)

            time.sleep(2)

#--------------------------------------------------------------------
    def _update_last_latitude_longitude(self, devicename, latitude, longitude, line_no=0):
        #Make sure that the last latitude/longitude is not set to the
        #base stationary one before updating. If it is, do not save them

        if latitude == None or longitude == None:
            error_log = ("Unusable location > No location available ({}, {}), "
                "Ignored (line {})").format(
                latitude,
                longitude,
                line_no)

        elif latitude == self.stat_zone_base_lat and longitude == self.stat_zone_base_long:
            error_log = ("Unusable location > Located at Stationary Base Zone ({}, {}), "
                "Ignored (line {})").format(
                latitude,
                longitude,
                line_no)
        else:
            self.last_lat[devicename]  = latitude
            self.last_long[devicename] = longitude
            return True

        self._save_event_halog_error(devicename, error_log)
        return False

#--------------------------------------------------------------------
    @staticmethod
    def _latitude_longitude_none(latitude, longitude):
        return (latitude == None or longitude == None)

#--------------------------------------------------------------------
    def _update_stationary_zone(self, devicename,
                arg_latitude, arg_longitude, visible_flag=False):
        """ Create/update dynamic stationary zone """

        try:
            latitude  = round(arg_latitude, 6)
            longitude = round(arg_longitude, 6)    
            zone_name = self._format_zone_name(devicename, STATIONARY)

            attrs = {}
            attrs[CONF_NAME]      = zone_name
            attrs[ATTR_LATITUDE]  = latitude
            attrs[ATTR_LONGITUDE] = longitude
            attrs[ATTR_RADIUS]    = self.stat_zone_radius_m
            attrs['passive']      = False
            attrs['icon']         = (f"mdi:{self.stat_zone_devicename_icon.get(devicename)}")
            attrs[ATTR_FRIENDLY_NAME] = 'Stationary'
             
            #If Stationary zone is hidden, don't hide it but reduce the size
            if visible_flag == STATIONARY_ZONE_HIDDEN:
                attrs[ATTR_RADIUS] = 3
                 
            self.log_debug_msg(devicename, f"Set Stat Zone-{attrs}")
            
            zone_dist = self._calc_distance_m(latitude, longitude,
                    self.zone_lat.get(zone_name), self.zone_long.get(zone_name)) 
            zone_dist_msg = f"{zone_dist}m" if zone_dist < 500 else f"{round(zone_dist/1000, 2)}km" 
            
            self.zone_lat[zone_name]       = latitude
            self.zone_long[zone_name]      = longitude
            self.zone_radius_km[zone_name] = self.stat_zone_radius_km
            self.zone_radius_m[zone_name]  = self.stat_zone_radius_m
            self.zone_passive[zone_name]   = not visible_flag

            self.hass.states.set("zone." + zone_name, "zoning", attrs)

            self._trace_device_attributes(
                    zone_name, "CreateStatZone", "CreateStatZone", attrs)

            event_msg = ("Set Stationary Zone > {}, GPS-({}, {}), DistFromLastLoc-{}").format(
                zone_name,
                latitude,
                longitude,
                zone_dist_msg)
            self._save_event_halog_info(devicename, event_msg)

            return True

        except Exception as err:
            _LOGGER.exception(err)
            log_msg = ("►►INTERNAL ERROR (UpdtStatZone-{})".format(err))
            self.log_error_msg(log_msg)

            return False
#--------------------------------------------------------------------
    def _update_device_sensors(self, arg_devicename, attrs:dict):
        '''
        Update/Create sensor for the device attributes

        sensor_device_attrs = ['distance', 'calc_distance', 'waze_distance',
                          'travel_time', 'dir_of_travel', 'interval', 'info',
                          'last_located', 'last_update', 'next_update',
                          'poll_count', 'trigger', 'battery', 'battery_state',
                          'gps_accuracy', 'zone', 'last_zone', 'travel_distance']

        sensor_attrs_format = {'distance': 'dist', 'calc_distance': 'dist',
                          'travel_distance': 'dist', 'battery': '%',
                          'dir_of_travel': 'title'}
        '''
        try:
            if not attrs:
                return

            #check to see if arg_devicename is really devicename_zone
            #if arg_devicename.find(':') == -1:
            if instr(arg_devicename, ":") == False:
                devicename  = arg_devicename
                prefix_zone = self.base_zone
            else:
                devicename  = arg_devicename.split(':')[0]
                prefix_zone = arg_devicename.split(':')[1]

            badge_state = None
            badge_zone  = None
            badge_dist  = None
            base_entity = self.sensor_prefix_name.get(devicename)

            if prefix_zone == HOME:
                base_entity = 'sensor.{}'.format(
                    self.sensor_prefix_name.get(devicename))
                attr_fname_prefix = self.sensor_attr_fname_prefix.get(devicename)
            else:
                base_entity = 'sensor.{}_{}'.format(
                    prefix_zone,
                    self.sensor_prefix_name.get(devicename))
                attr_fname_prefix = '{}_{}'.format(
                    prefix_zone.replace('_', ' ', 99).title(),
                    self.sensor_attr_fname_prefix.get(devicename))

            for attr_name in SENSOR_DEVICE_ATTRS:
                sensor_entity = "{}_{}".format(base_entity, attr_name)
                if attr_name in attrs:
                    state_value = attrs.get(attr_name)
                else:
                    continue

                sensor_attrs = {}
                if attr_name in SENSOR_ATTR_FORMAT:
                    format_type = SENSOR_ATTR_FORMAT.get(attr_name)
                    if format_type == "dist":
                        sensor_attrs['unit_of_measurement'] = \
                                self.unit_of_measurement
                        #state_value = round(state_value, 2) if state_value else 0.00

                    elif format_type == "diststr":
                        try:
                            x = (state_value / 2)
                            sensor_attrs['unit_of_measurement'] = \
                                self.unit_of_measurement
                        except:
                            sensor_attrs['unit_of_measurement'] = ''
                    elif format_type == "%":
                        sensor_attrs['unit_of_measurment'] = '%'
                    elif format_type == 'title':
                        state_value = state_value.title().replace('_', ' ')
                    elif format_type == 'kph-mph':
                        sensor_attrs['unit_of_measurement'] = self.um_kph_mph
                    elif format_type == 'm-ft':
                        sensor_attrs['unit_of_measurement'] = self.um_m_ft

                if attr_name in SENSOR_ATTR_ICON:
                    sensor_attrs['icon'] = SENSOR_ATTR_ICON.get(attr_name)

                if attr_name in SENSOR_ATTR_FNAME:
                    sensor_attrs['friendly_name'] = '{}{}'.format(
                        attr_fname_prefix, SENSOR_ATTR_FNAME.get(attr_name))

                self._update_device_sensors_hass(devicename, base_entity, attr_name,
                                    state_value, sensor_attrs)

                if attr_name == 'zone':
                    zone_names = self._get_zone_names(state_value)
                    if badge_state == None:
                        badge_state = zone_names[1]
                    self._update_device_sensors_hass(devicename, base_entity,
                                "zone_name1", zone_names[1], sensor_attrs)

                    self._update_device_sensors_hass(devicename, base_entity,
                                "zone_name2", zone_names[2], sensor_attrs)

                    self._update_device_sensors_hass(devicename, base_entity,
                                "zone_name3", zone_names[3], sensor_attrs)

                elif attr_name == 'last_zone':
                    zone_names = self._get_zone_names(state_value)

                    self._update_device_sensors_hass(devicename, base_entity,
                                "last_zone_name1", zone_names[1], sensor_attrs)

                    self._update_device_sensors_hass(devicename, base_entity,
                                "last_zone_name2", zone_names[2], sensor_attrs)

                    self._update_device_sensors_hass(devicename, base_entity,
                                "last_zone_name3", zone_names[3], sensor_attrs)

                elif attr_name == 'zone_distance':
                    if state_value and float(state_value) > 0:
                        badge_state = "{} {}".format(
                                state_value, self.unit_of_measurement)


            if badge_state:
                self._update_device_sensors_hass(devicename,
                            base_entity,
                            "badge",
                            badge_state,
                            self.sensor_badge_attrs.get(devicename))
                #log_msg=("Badge ={}, state_value={} {}").format(
                #        badge_entity, badge_state,
                #        self.sensor_badge_attrs.get(devicename))
                #self.log_debug_msg(devicename, log_msg)
            return True

        except Exception as err:
            _LOGGER.exception(err)
            log_msg = ("►►INTERNAL ERROR (UpdtSensorUpdate-{})".format(err))
            self.log_error_msg(log_msg)

            return False
#--------------------------------------------------------------------
    def _update_device_sensors_hass(self, devicename, base_entity, attr_name,
                                    state_value, sensor_attrs):

        try:
            state_value = state_value[0:250]
        except:
            pass

        if attr_name in self.sensors_custom_list:
            sensor_entity = "{}_{}".format(base_entity, attr_name)

            self.hass.states.set(sensor_entity, state_value, sensor_attrs)

#--------------------------------------------------------------------
    def _format_info_attr(self, devicename, battery,
                            gps_accuracy, dist_last_poll_moved_km,
                            current_zone, location_isold_flag, location_time_secs):  #loc_timestamp):

        """
        Initialize info attribute
        """
        devicename_zone = self._format_devicename_zone(devicename)
        try:
            info_msg = ''
            if self.info_notification != '':
                info_msg = '●●{}●●'.format(self.info_notification)
                self.info_notification = ''

            if self.base_zone != HOME:
                info_msg = '{} ●Base.Zone: {}'.format(info_msg, self.base_zone_name)

            if not self.CURRENT_TRK_METHOD_FMF:
                info_msg = '{} ●Track.Method: {}'.format(info_msg, self.trk_method_short_name)

            if self.overrideinterval_seconds.get(devicename) > 0:
                info_msg = '{} ●Overriding.Interval'.format(info_msg)


            if current_zone == 'near_zone':
                info_msg = '{} ●NearZone'.format(info_msg)

            if battery > 0:
                info_msg = '{} ●Battery-{}%'.format(info_msg, battery)

            if gps_accuracy > self.gps_accuracy_threshold:
                info_msg = '{} ●Poor.GPS.Accuracy, Dist-{}m'.format(
                    info_msg, gps_accuracy)
                if self.poor_gps_accuracy_cnt.get(devicename) > 0:
                    info_msg = '{} (#{})'.format(info_msg,
                    self.poor_gps_accuracy_cnt.get(devicename))
                if (self._is_inzoneZ(current_zone) and
                        self.ignore_gps_accuracy_inzone_flag):
                    info_msg = '{}-Ignored'.format(info_msg)


            isold_cnt = self.location_isold_cnt.get(devicename)

            if isold_cnt > 0:
                age = self._secs_since(self.last_located_secs.get(devicename))
                info_msg = '{} ●Old.Location, Age-{} (#{})'.format(
                    info_msg,
                    self._secs_to_time_str(age),
                    isold_cnt)

            if self.waze_data_copied_from.get(devicename) is not None:
                copied_from = self.waze_data_copied_from.get(devicename)
                if devicename != copied_from:
                    info_msg = '{} ●Using Waze data from {}'.format(info_msg,
                                self.friendly_name.get(copied_from))

            poll_cnt = self.count_update_icloud.get(devicename) + \
                        self.count_update_iosapp.get(devicename) + \
                        self.count_update_ignore.get(devicename)
            if (poll_cnt > 0 and poll_cnt % 5) == 0:
                 info_msg =('{} ●Metrics: {}').format(
                    info_msg,
                    self._format_usage_counts(devicename))

        except Exception as err:
            _LOGGER.exception(err)
            info_msg = ("Error setting up info attribute-{}").format(err)
            self.log_error_msg(info_msg)

        return info_msg

#--------------------------------------------------------------------
    def _display_info_status_msg(self, devicename_zone, info_msg):
        '''
        Display a status message in the info sensor. If the devicename_zone
        parameter contains the base one (devicename:zone), display only for that
        devicename_one, otherwise (devicename), display for all zones for
        the devicename.
        '''
        try:
            save_base_zone = self.base_zone

            #if devicename_zone.find(':') >= 0:
            if instr(devicename_zone, ':'):
                devicename = devicename_zone.split(':')[0]
                devicename_zone_list = [devicename_zone.split(':')[1]]
            else:
                devicename = devicename_zone
                devicename_zone_list = self.track_from_zone.get(devicename)

            for zone in devicename_zone_list:
                self.base_zone = zone
                attrs = {}
                attrs[ATTR_INFO] = "●{}●".format(info_msg)
                self._update_device_sensors(devicename, attrs)

        except:
            pass

        self.base_zone = save_base_zone

#--------------------------------------------------------------------
    def _update_count_update_ignore_attribute(self, devicename, info = None):
        self.count_update_ignore[devicename] += 1

        try:
            attrs  = {}
            attrs[ATTR_POLL_COUNT] = self._format_poll_count(devicename)

            self._update_device_sensors(devicename, attrs)

        except:
            pass
#--------------------------------------------------------------------
    def _format_poll_count(self, devicename):

        return "{}:{}:{}".format(
            self.count_update_icloud.get(devicename),
            self.count_update_iosapp.get(devicename),
            self.count_update_ignore.get(devicename))

#--------------------------------------------------------------------
    def _format_usage_counts(self, devicename):

        try:
            usage_msg =( "iCloud.Locates-{}, IOS.App.Updates-{}, Discarded-{}, "
                "State.Changes-{}, Trigger.Changes-{}").format(
                self.count_update_icloud.get(devicename),
                self.count_update_iosapp.get(devicename),
                self.count_update_ignore.get(devicename),
                self.count_state_changed.get(devicename),
                self.count_trigger_changed.get(devicename))
            if self.count_request_iosapp_update.get(devicename) > 0:
                usage_msg = "{}, IOS.APP.Locates-{}".format(
                    usage_msg,
                    self.count_request_iosapp_update.get(devicename))
        except Exception as err:
            _LOGGER.exception(err)
            usage_msg = "Not Available"

        return usage_msg

#########################################################
#
#   VARIABLE DEFINITION & INITIALIZATION FUNCTIONS
#
#########################################################
    def _define_tracking_control_fields(self):
        self.this_update_secs            = 0
        self.icloud3_started_secs        = 0
        self.update_timer                = {}
        self.overrideinterval_seconds    = {}
        self.immediate_retry_flag        = False
        self.time_zone_offset_seconds    = self._calculate_time_zone_offset()
        self.setinterval_cmd_devicename  = None
        self.icloud_acct_auth_error_cnt  = 0
        self.update_in_process_flag      = False
        self.track_devicename_list       = ''
        self.tracked_devices             = {}
        self.any_device_being_updated_flag = False
        self.tracked_devices_config_parm = {} #config file item for devicename
        self.tracked_devices             = []
        self.info_notification           = ''

#--------------------------------------------------------------------
    def _define_event_log_fields(self):
        self.event_cnt                   = {}
        self.event_log_table             = []
        self.event_log_base_attrs        = ''
        self.log_table_length            = 999
        self.event_log_chear_secs        = 9999999999
        self.event_log_sensor_state      = ''
        self.event_log_last_devicename   = '*'

#--------------------------------------------------------------------
    def _define_device_fields(self):
        '''
        Dictionary fields for each devicename
        '''
        self.friendly_name            = {}    #name made from status[CONF_NAME]
        self.badge_picture            = {}    #devicename picture from badge setup
        self.icloud_api_devices       = {}    #icloud.api.devices obj
        self.data_source              = {}
        self.device_type              = {}
        self.iosapp_version1_flag     = {}
        self.devicename_iosapp        = {}
        self.devicename_iosapp_id     = {}
        self.devicename_verified      = {}    #Set to True in mode setup fcts
        self.fmf_id                   = {}
        self.fmf_devicename_email     = {}
        self.seen_this_device_flag    = {}
        self.device_tracker_entity    = {}
        self.device_tracker_entity_iosapp = {}
        self.track_from_zone          = {}    #Track device from other zone

#--------------------------------------------------------------------
    def _define_device_status_fields(self):
        '''
        Dictionary fields for each devicename
        '''
        self.tracking_device_flag     = {}
        self.state_last_poll          = {}
        self.state_this_poll          = {}
        self.zone_last                = {}
        self.zone_current             = {}
        self.zone_timestamp           = {}
        self.went_3km                 = {} #>3 km/mi, probably driving
        self.overrideinterval_seconds = {}
        self.last_located_time        = {}
        self.last_located_secs        = {}    #device timestamp in seconds
        self.location_isold_cnt       = {}    # override interval while < 4
        self.location_isold_msg       = {}
        self.trigger                  = {}    #device update trigger
        self.last_iosapp_trigger      = {}    #last trigger issued by iosapp
        self.device_being_updated_flag= {}
        self.device_being_updated_retry_cnt = {}
        self.last_v2_state                = {}
        self.last_v2_state_changed_time   = {}
        self.last_v2_state_changed_secs   = {}
        self.last_v2_trigger              = {}
        self.last_v2_trigger_changed_time = {}
        self.last_v2_trigger_changed_secs = {}
        self.dist_from_zone_km_small_move_total = {}
        self.fmf_location_data             = {}
        self.iosapp_version                = {}
        self.iosapp_v2_last_trigger_entity = {} #sensor entity extracted from entity_registry
        self.iosapp_location_update_secs   = {}
        self.iosapp_stat_zone_action_msg_cnt = {}

        this_update_time = dt_util.now().strftime('%H:%M:%S')
        self.authenticated_time       = \
                        dt_util.now().strftime(self.um_date_time_strfmt)

#--------------------------------------------------------------------
    def _define_usage_counters(self):
        self.count_update_iosapp      = {}
        self.count_update_ignore      = {}
        self.count_update_icloud      = {}
        self.count_state_changed      = {}
        self.count_trigger_changed    = {}
        self.count_request_iosapp_update = {}

#--------------------------------------------------------------------
    def _define_device_tracking_fields(self):
        '''
        Dictionary fields for each devicename_zone
        '''
        self.interval_seconds       = {}
        self.interval_str           = {}
        self.last_tavel_time        = {}
        self.last_distance_str      = {}
        self.last_update_time       = {}
        self.last_update_secs       = {}
        self.next_update_secs       = {}
        self.next_update_time       = {}
        self.next_update_in_secs    = {}

        #used to calculate distance traveled since last poll
        self.last_lat               = {}
        self.last_long              = {}
        self.waze_time              = {}
        self.waze_dist              = {}
        self.calc_dist              = {}
        self.zone_dist              = {}

        self.state_change_flag      = {}
        self.iosapp_update_flag     = {}
        self.last_dev_timestamp_ses = {}
        self.poor_gps_accuracy_flag = {}
        self.poor_gps_accuracy_cnt  = {}
        self.last_battery           = {}   #used to detect iosapp v2 change
        self.last_gps_accuracy      = {}   #used to detect iosapp v2 change
        self.last_fmf_refresh       = 0


#--------------------------------------------------------------------
    def _initialize_um_formats(self, unit_of_measurement):
        #Define variables, lists & tables
        if unit_of_measurement == 'mi':
            self.um_time_strfmt          = '%I:%M:%S'
            self.um_date_time_strfmt     = '%x, %I:%M:%S'
            self.um_km_mi_factor         = 0.62137
            self.um_m_ft                 = 'ft'
            self.um_kph_mph              = 'mph'
        else:
            self.um_time_strfmt          = '%H:%M:%S'
            self.um_date_time_strfmt     = '%x, %H:%M:%S'
            self.um_km_mi_factor         = 1
            self.um_m_ft                 = 'm'
            self.um_kph_mph              = 'kph'

#--------------------------------------------------------------------
    def _setup_tracking_method(self, tracking_method):
        '''
        tracking_method: method
        tracking_method: method, iosapp1

        tracking_method can have a secondary option to use iosappv1 even if iosv2 is
        on the devices
        '''

        trk_method_split     = '{}_'.format(tracking_method).split('_')
        trk_method_primary   = trk_method_split[0]
        trk_method_secondary = trk_method_split[1]

        self.CURRENT_TRK_METHOD_FMF        = (trk_method_primary == TRK_METHOD_FMF)
        self.CURRENT_TRK_METHOD_FAMSHR     = (trk_method_primary == TRK_METHOD_FAMSHR)
        self.CURRENT_TRK_METHOD_FMF_FAMSHR = (trk_method_primary in TRK_METHOD_FMF_FAMSHR)
        if (self.CURRENT_TRK_METHOD_FMF_FAMSHR and
                PYICLOUD_IC3_IMPORT_SUCCESSFUL is False):
           trk_method_primary = TRK_METHOD_IOSAPP

        self.CURRENT_TRK_METHOD_IOSAPP = (trk_method_primary in TRK_METHOD_IOSAPP_IOSAPP1)
        self.USE_IOSAPPV1_TRK_METHOD   = (trk_method_primary == TRK_METHOD_IOSAPP1 or
                                            trk_method_secondary == TRK_METHOD_IOSAPP1)
        self.USE_IOSAPPV2_TRK_METHOD   = not self.USE_IOSAPPV1_TRK_METHOD

        self.trk_method_config     = trk_method_primary
        self.trk_method            = trk_method_primary
        self.trk_method_name       = TRK_METHOD_NAME.get(trk_method_primary)
        self.trk_method_short_name = TRK_METHOD_SHORT_NAME.get(trk_method_primary)

#--------------------------------------------------------------------
    def _initialize_zone_tables(self):
        '''
        Get friendly name of all zones to set the device_tracker state
        '''
        self.zones           = []
        self.zone_friendly_name = {}
        self.zone_lat       = {}
        self.zone_long      = {}
        self.zone_radius_km = {}
        self.zone_radius_m  = {}
        self.zone_passive   = {}

        if self.initial_startup_flag == False:
            self.hass.services.call("zone", "reload")
            
            log_msg = (f"Reloading Zone.yaml config file")
            self.log_debug_msg("*", log_msg)           
                
        zones = self.hass.states.entity_ids('zone')
        zone_msg = ''
        
        for zone in zones:
            zone_name  = zone.split(".")[1]      #zone='zone.'+zone_name
            
            try:        
                self.zones.append(zone_name.lower())
                zone_data  = self.hass.states.get(zone).attributes
                self.log_debug_msg("*",f"zone-{zone_name}, data-{zone_data}")
                
                if instr(zone_name.lower(), STATIONARY):
                    self.zone_friendly_name[zone_name] = 'Stationary'  
                
                if ATTR_LATITUDE in zone_data:
                    self.zone_lat[zone_name]       = zone_data.get(ATTR_LATITUDE, 0)
                    self.zone_long[zone_name]      = zone_data.get(ATTR_LONGITUDE, 0)
                    self.zone_passive[zone_name]   = zone_data.get('passive', True)
                    self.zone_radius_m[zone_name]  = int(zone_data.get(ATTR_RADIUS, 100))
                    self.zone_radius_km[zone_name] = round(self.zone_radius_m[zone_name]/1000, 4)
                    self.zone_friendly_name[zone_name] = zone_data.get(ATTR_FRIENDLY_NAME, zone_name.title())
                    
                else:
                    log_msg = (f"Error loading zone {zone_name} > No data was returned from HA. "
                               f"Zone data returned is `{zone_data}`")
                    self.log_error_msg(log_msg)
                    self._save_event("*", log_msg)
                  
            except KeyError:
                self.zone_passive[zone_name] = False
                
            except Exception as err:
                _LOGGER.exception(err)
                
            zone_msg = (f"{zone_msg}{zone_name}/{self.zone_friendly_name.get(zone_name)}"
                        f"-({self.zone_radius_m[zone_name]}m), ")
            
        log_msg = (f"Set up Zones-{zone_msg[:-2]}")
        self._save_event_halog_info("*", log_msg)

        self.zone_home_lat    = self.zone_lat.get(HOME)
        self.zone_home_long   = self.zone_long.get(HOME)
        self.zone_home_radius_km = float(self.zone_radius_km.get(HOME))
        self.zone_home_radius_m = self.zone_radius_m.get(HOME)

        self.base_zone        = HOME
        self.base_zone_name   = self.zone_friendly_name.get(HOME)
        self.base_zone_lat    = self.zone_lat.get(HOME)
        self.base_zone_long   = self.zone_long.get(HOME)
        self.base_zone_radius_km = float(self.zone_radius_km.get(HOME))

        return

#--------------------------------------------------------------------
    def _define_stationary_zone_fields(self, stationary_inzone_interval_str,
                    stationary_still_time_str):
        #create dynamic zone used by ios app when stationary
        
        self.stat_zone_inzone_interval = self._time_str_to_secs(stationary_inzone_interval_str)
        self.stat_zone_still_time      = self._time_str_to_secs(stationary_still_time_str)
        self.stat_zone_half_still_time = self.stat_zone_still_time / 2
        self.in_stationary_zone_flag   = {}
        self.stat_zone_devicename_icon = {}  #icon to be used for a devicename
        self.stat_zone_moved_total     = {}  #Total of small distances
        self.stat_zone_timer           = {}  #Time when distance set to 0
        self.stat_min_dist_from_zone_km   = round(self.zone_home_radius_km * 2.5, 2)
        self.stat_dist_move_limit      = round(self.zone_home_radius_km * 1.5, 2)
        self.stat_zone_radius_km       = round(self.zone_home_radius_km * 2, 2)
        self.stat_zone_radius_m        = self.zone_home_radius_m * 2
        self.stat_zone_base_long       = self.zone_home_long
        
        #Offset the stat zone 1km north of Home if north of the equator or 
        #1km south of Home is south of the equator. (offset of 0.005=1km degrees)
        #Switch direction if near the north or south pole. 
        offset = STATIONARY_ZONE_HOME_OFFSET  #0.00468    #0.005=1km
        offset = -1*offset if self.zone_home_lat < 0 else offset
        offset = -1*offset if self.zone_home_lat > 89.8 or self.zone_home_lat < -89.8 else offset
        self.stat_zone_base_lat = round(self.zone_home_lat + offset, 6)
        
        log_msg = (f"Set up Initial Stationary Zone Location > "
                   f"GPS-({self.stat_zone_base_lat}, {self.stat_zone_base_long}), "
                   f"Radius-{self.stat_zone_radius_m}m")
        self.log_debug_msg("*", log_msg)
        self._save_event("*", log_msg)
        
#--------------------------------------------------------------------
    def _initialize_debug_control(self, log_level):
        #string set using the update_icloud command to pass debug commands
        #into icloud3 to monitor operations or to set test variables
        #   interval - toggle display of interval calulation method in info fld
        #   debug - log 'debug' messages to the log file under the 'info' type
        #   debug_rawdata - log data read from records to the log file
        #   eventlog - Add debug items to ic3 event log
        #   debug+eventlog - Add debug items to HA log file and ic3 event log

        self.log_level_debug_flag         = (instr(log_level, 'debug') or DEBUG_TRACE_CONTROL_FLAG)
        self.log_level_debug_rawdata_flag = (instr(log_level, 'rawdata') and self.log_level_debug_flag)
        self.log_debug_msgs_trace_flag    = self.log_level_debug_flag

        self.log_level_intervalcalc_flag = DEBUG_TRACE_CONTROL_FLAG or instr(log_level, 'intervalcalc')
        self.log_level_eventlog_flag     = instr(log_level, 'eventlog')

        self.debug_counter = 0
        self.last_debug_msg = {} #can be used to compare changes in debug msgs

#--------------------------------------------------------------------
    def _initialize_device_fields(self, devicename):
        #Make domain name entity ids for the device_tracker and
        #sensors for each device so we don't have to do it all the
        #time. Then check to see if 'sensor.geocode_location'
        #exists. If it does, then using iosapp version 2.
        self.device_tracker_entity[devicename] = ('{}.{}').format(
                DOMAIN, devicename)
        self.device_tracker_entity_iosapp[devicename] = ('{}.{}').format(
                DOMAIN, self.devicename_iosapp.get(devicename))

        entity_id = self.device_tracker_entity.get(devicename)
        self.state_this_poll[devicename] = self._get_current_state(entity_id)

        self.state_last_poll[devicename]      = NOT_SET
        self.zone_last[devicename]            = ''
        self.zone_current[devicename]         = ''
        self.zone_timestamp[devicename]       = ''
        self.iosapp_update_flag[devicename]   = False
        self.state_change_flag[devicename]    = False
        self.trigger[devicename]              = 'iCloud3'
        self.last_iosapp_trigger[devicename]  = ''
        self.last_located_time[devicename]    = ZERO_HHMMSS
        self.last_located_secs[devicename]    = 0

        self.iosapp_location_update_secs[devicename] = 0
        self.device_being_updated_flag[devicename]   = False
        self.device_being_updated_retry_cnt[devicename] = 0
        self.seen_this_device_flag[devicename]  = False
        self.went_3km[devicename]               = False

        #if devicename not in self.sensor_prefix_name:
        self.sensor_prefix_name[devicename] = devicename

        #iosapp v2 entity info
        self.last_v2_state[devicename]        = ''
        self.last_v2_state_changed_time[devicename]  = ''
        self.last_v2_state_changed_secs[devicename]  = 0
        self.last_v2_trigger[devicename]      = ''
        self.last_v2_trigger_changed_time[devicename] = ''
        self.last_v2_trigger_changed_secs[devicename] = 0

#--------------------------------------------------------------------
    def _initialize_device_tracking_fields(self, devicename):
        #times, flags
        self.overrideinterval_seconds[devicename] = 0
        self.dist_from_zone_km_small_move_total[devicename] = 0
        self.update_timer[devicename]           = time.time()

        #location, gps
        self.location_isold_cnt[devicename]     = 0
        self.location_isold_msg[devicename]     = False
        self.last_lat[devicename]               = self.zone_home_lat
        self.last_long[devicename]              = self.zone_home_long
        self.poor_gps_accuracy_flag[devicename] = False
        self.poor_gps_accuracy_cnt[devicename]  = 0
        self.last_battery[devicename]           = 0
        self.last_gps_accuracy[devicename]      = 0
        self.data_source[devicename]            = ''
        self.event_cnt[devicename]              = 0
        self.last_debug_msg[devicename]         = ''
        self.iosapp_stat_zone_action_msg_cnt[devicename]= 0

#--------------------------------------------------------------------
    def _initialize_usage_counters(self, devicename):
        if devicename not in self.count_update_iosapp:
            self.count_update_iosapp[devicename]   = 0
            self.count_update_icloud[devicename]   = 0
            self.count_update_ignore[devicename]   = 0
            self.count_state_changed[devicename]   = 0
            self.count_trigger_changed[devicename] = 0
            self.count_request_iosapp_update[devicename] = 0


#--------------------------------------------------------------------
    def _initialize_device_zone_fields(self, devicename):
        #interval, distances, times

        for zone in self.track_from_zone.get(devicename):
            devicename_zone = self._format_devicename_zone(devicename, zone)

            self.last_update_time[devicename_zone]  = ZERO_HHMMSS
            self.last_update_secs[devicename_zone]  = 0
            self.next_update_time[devicename_zone]  = ZERO_HHMMSS
            self.next_update_secs[devicename_zone]  = 0
            self.next_update_in_secs[devicename_zone] = 0
            self.last_tavel_time[devicename_zone]   = ''
            self.last_distance_str[devicename_zone] = ''
            self.interval_seconds[devicename_zone]  = 0
            self.interval_str[devicename_zone]      = '0 sec'
            self.waze_history_data_used_flag[devicename_zone] = False
            self.waze_time[devicename_zone]         = 0
            self.waze_dist[devicename_zone]         = 0
            self.calc_dist[devicename_zone]         = 0
            self.zone_dist[devicename_zone]         = 0

        try:  
            #set up stationary zone icon for devicename
            first_initial = self.friendly_name.get(devicename)[0].lower()

            if devicename in self.stat_zone_devicename_icon:
                icon = self.stat_zone_devicename_icon.get(devicename)
            elif (f"alpha-{first_initial}-box") not in self.stat_zone_devicename_icon:
                icon_name = (f"alpha-{first_initial}-box")
            elif (f"alpha-{first_initial}-circle") not in self.stat_zone_devicename_icon:
                icon_name = (f"alpha-{first_initial}-circle")
            elif (f"alpha-{first_initial}-box-outline") not in self.stat_zone_devicename_icon:
                icon_name = (f"alpha-{first_initial}-box-outline")
            elif (f"alpha-{first_initial}-circle-outline") not in self.stat_zone_devicename_icon:
                icon_name = (f"alpha-{first_initial}-circle-outline")
            else:
                icon_name = (f"alpha-{first_initial}")

            self.stat_zone_devicename_icon[devicename] = icon_name
            self.stat_zone_devicename_icon[icon_name]  = devicename
            
        except Exception as err:
            _LOGGER.exception(err)  
            self.stat_zone_devicename_icon[devicename] = 'account'           
        
#--------------------------------------------------------------------
    def _initialize_next_update_time(self, devicename):
        for zone in self.track_from_zone.get(devicename):
            devicename_zone = self._format_devicename_zone(devicename, zone)

            self.next_update_time[devicename_zone] = ZERO_HHMMSS
            self.next_update_secs[devicename_zone] = 0

#--------------------------------------------------------------------
    def _define_sensor_fields(self):
        #Prepare sensors and base attributes
        self.sensor_devicenames       = []
        self.sensors_custom_list      = []
        self.sensor_badge_attrs       = {}
        self.sensor_prefix_name       = {}
        self.sensor_attr_fname_prefix = {}

#--------------------------------------------------------------------
    def _initialize_waze_fields(self, waze_region, waze_min_distance,
                waze_max_distance, waze_realtime):
        #Keep distance data to be used by another device if nearby. Also keep
        #source of copied data so that device won't reclone from the device
        #using it.
        self.waze_region   = waze_region
        self.waze_realtime = waze_realtime

        if self.unit_of_measurement == 'mi':
            self.waze_min_distance = self._mi_to_km(waze_min_distance)
            self.waze_max_distance = self._mi_to_km(waze_max_distance)
        else:
            self.waze_min_distance = float(waze_min_distance)
            self.waze_max_distance = float(waze_max_distance)
            
        self.waze_distance_history = {}
        self.waze_data_copied_from = {}
        self.waze_history_data_used_flag = {}

        self.waze_manual_pause_flag        = False  #If Paused vid iCloud command
        self.waze_close_to_zone_pause_flag = False  #pause if dist from zone < 1 flag
        
        if self.distance_method_waze_flag:
            log_msg = ("Set Up Waze > Region-{}, MaxDist-{} {}, "
                  "MinDist-{} {}, Realtime-{}").format(
                  self.waze_region, 
                  waze_max_distance, self.unit_of_measurement,
                  waze_min_distance, self.unit_of_measurement, 
                  self.waze_realtime)
            self.log_info_msg(log_msg)
            self._save_event("*", log_msg)

#--------------------------------------------------------------------
    def _initialize_attrs(self, devicename):
        attrs = {}
        attrs[ATTR_NAME]               = ''
        attrs[ATTR_ZONE]               = NOT_SET
        attrs[ATTR_LAST_ZONE]          = NOT_SET
        attrs[ATTR_ZONE_TIMESTAMP]     = ''
        attrs[ATTR_INTERVAL]           = ''
        attrs[ATTR_WAZE_TIME]          = ''
        attrs[ATTR_ZONE_DISTANCE]      = 1
        attrs[ATTR_CALC_DISTANCE]      = 1
        attrs[ATTR_WAZE_DISTANCE]      = 1
        attrs[ATTR_LAST_LOCATED]       = ZERO_HHMMSS
        attrs[ATTR_LAST_UPDATE_TIME]   = ZERO_HHMMSS
        attrs[ATTR_NEXT_UPDATE_TIME]   = ZERO_HHMMSS
        attrs[ATTR_POLL_COUNT]         = '0:0:0'
        attrs[ATTR_DIR_OF_TRAVEL]      = ''
        attrs[ATTR_TRAVEL_DISTANCE]    = 0
        attrs[ATTR_TRIGGER]            = ''
        attrs[ATTR_TIMESTAMP]          = dt_util.utcnow().isoformat()[0:19]
        attrs[ATTR_AUTHENTICATED]      = ''
        attrs[ATTR_BATTERY]            = 0
        attrs[ATTR_BATTERY_STATUS]     = ''
        attrs[ATTR_INFO]               = ''
        attrs[ATTR_ALTITUDE]           = 0
        attrs[ATTR_VERTICAL_ACCURACY]  = 0
        attrs[ATTR_DEVICE_STATUS]      = ''
        attrs[ATTR_LOW_POWER_MODE]     = ''
        attrs[CONF_GROUP]              = self.group
        attrs[ATTR_PICTURE]            = self.badge_picture.get(devicename)
        attrs[ATTR_TRACKING]           = self.track_devicename_list
        attrs[ATTR_ICLOUD3_VERSION]    = VERSION

        return attrs

#########################################################
#
#   INITIALIZE PYICLOUD DEVICE API
#   DEVICE SETUP SUPPORT FUNCTIONS FOR MODES FMF, FAMSHR, IOSAPP
#
#########################################################
    def _initialize_pyicloud_device_api(self):
        #See if pyicloud_ic3 is available
        if (PYICLOUD_IC3_IMPORT_SUCCESSFUL is False and self.CURRENT_TRK_METHOD_FMF_FAMSHR):
            self.trk_method = TRK_METHOD_IOSAPP
            event_msg = ("iCloud3 Error: 'pyicloud_ic3.py' module not found")
            self._save_event_halog_error("*", event_msg)

            event_msg = ("iCloud3 Error: Falling back to IOSAPP instead of {}").format(self.trk_method_s)
            self._save_event_halog_error("*", event_msg)

        from .pyicloud_ic3 import (
                PyiCloudFailedLoginException, PyiCloudNoDevicesException)

        #Set up pyicloud cookies directory & file names
        try:
            self.ICLOUD_COOKIES_DIR  = self.hass.config.path(STORAGE_DIR, STORAGE_KEY_ICLOUD)
            self.ICLOUD_COOKIES_FILE = "{}/{}".format(
                self.ICLOUD_COOKIES_DIR, self.username.replace('@','').replace('.',''))
            if not os.path.exists(self.ICLOUD_COOKIES_DIR):
                os.makedirs(self.ICLOUD_COOKIES_DIR)

        except Exception as err:
            _LOGGER.exception(err)

        if self.CURRENT_TRK_METHOD_IOSAPP:
            self.api = None

        elif self.CURRENT_TRK_METHOD_FMF_FAMSHR:
            event_msg = ("Requesting Authentication for {} ({})").format(
                self.username,
                self.group)
            self._save_event_halog_info("*", event_msg)

            #icloud_dir = self.hass.config.path('icloud')
            #if not os.path.exists(icloud_dir):
            #    os.makedirs(icloud_dir)

            try:
                self.api = PyiCloudService(self.username, self.password,
                           cookie_directory=self.ICLOUD_COOKIES_DIR, verify=True)

                event_msg = ("Authentication for {} ({}) successful").format(
                    self.username,
                    self.group)
                self._save_event_halog_info("*", event_msg)

            except PyiCloudFailedLoginException as error:
                self.api = None

                event_msg = ("iCloud3 Error for {} ({}) > "
                    "Error Authenticating account or no data was returned from "
                    "iCloud Web Services. Web Services may be down or the "
                    "Username/Password may be invalid. "
                    "iCloud {} Location Service is disabled. iCloud3 will "
                    "use the IOS App tracking_method instead.").format(
                    self.username, self.group, self.trk_method_short_name)
                self._save_event_halog_error("*", event_msg)
                self.trk_method = TRK_METHOD_IOSAPP

#--------------------------------------------------------------------
    def _setup_tracked_devices_for_fmf(self):
        '''
        Cycle thru the Find My Friends contact data. Extract the name, id &
        email address. Scan fmf_email config parameter to tie the fmf_id in
        the location record to the devicename.

                    email --> devicename <--fmf_id
        '''
        '''
        contact={
            'emails': ['gary678tw@', 'gary_2fa_acct@email.com'],
            'firstName': 'Gary',
            'lastName': '',
            'photoUrl': 'PHOTO;X-ABCROP-RECTANGLE=ABClipRect_1&64&42&1228&1228&
                    //mOVw+4cc3VJSJmspjUWg==;
                    VALUE=uri:https://p58-contacts.icloud.com:443/186297810/wbs/
                    0123efg8a51b906789fece
            'contactId': '8590AE02-7D39-42C1-A2E8-ACCFB9A5E406',60110127e5cb19d1daea',
            'phones': ['(222)\xa0m456-7899'],
            'middleName': '',
            'id': 'ABC0DEFGH2NzE3'}

        cycle thru config>track_devices devicename/email parameter
        looking for a match with the fmf contact record emails item
                fmf_devicename_email:
                   'gary_iphone'       = 'gary_2fa_acct@email.com'
                   'gary_2fa_acct@email.com' = 'gary_iphone@'
             - or -
                   'gary_iphone'       = 'gary678@'
                   'gary678@'          = 'gary_iphone@gmail'

                emails:
                   ['gary456tw@', 'gary_2fa_acct@email.com]

        When complete, erase fmf_devicename_email and replace it with full
        email list
        '''
        try:
            fmf = self.api.friends

            if fmf == None:
                log_msg = ("iCloud3 Error for {} ({}) > "
                    "Verify that the tracked devices have been set up in the "
                    "FindMe App and they can be located. "
                    "►See the iCloud3 Documentation, `Setting Up your iCloud "
                    "Acount/Find-my-Friends Tracking Method`.").format(
                    self.username, self.group)
                self._save_event_halog_error("*", log_msg)
                log_msg = ("iCloud3 Error for {} ({}) > "
                    "No FmF data was returned from Apple Web Services. "
                    "Verify that the tracked devices have been added "
                    "to the Contacts list for this iCloud account.").format(
                    self.username, self.group)
                self._save_event_halog_error("*", log_msg)

                return
                
            self.log_level_debug_rawdata("Raw iCloud Friends Raw Data", fmf.data)
                
            #cycle thru al contacts in fmf recd
            devicename_contact_emails = {}
            contacts_valid_emails = ''

            #Get contacts data from non-2fa account. If there are no contacts
            #in the fmf data, use the following data in the fmf data
            '''
            contacts = fmf.contacts
            if contacts == []:
                contacts = fmf.following
                contact_emails_field = 'invitationAcceptedHandles'

                log_msg = ('FmF Contact information is not available. '
                           'FmF Following data will be used instead.')
                self.log_debug_msg("*", log_msg)
            else:
                contact_emails_field = 'emails'
            for contact in contacts:
                contact_emails = contact.get(contact_emails_field)
                id_contact     = contact.get('id')

            '''
            for contact in fmf.following:
                contact_emails = contact.get('invitationAcceptedHandles')
                contact_id     = contact.get('id')

                title = (f"FmF iCloud fmf.following Data")
                self.log_level_debug_rawdata(title, contact)

                #cycle thru the emails on the tracked_devices config parameter
                for parm_email in self.fmf_devicename_email:
                    if instr(parm_email, '@') == False:
                        continue

                    #cycle thru the contacts emails
                    matched_friend = False
                    devicename = self.fmf_devicename_email.get(parm_email)

                    for contact_email in contact_emails:
                        #if contacts_valid_emails.find(contact_email) >= 0:
                        if instr(contacts_valid_emails, contact_email) == False:
                            contacts_valid_emails += contact_email + ", "

                        if contact_email.startswith(parm_email):
                            #update temp list with full email from contact recd
                            matched_friend = True
                            devicename_contact_emails[contact_email] = devicename
                            devicename_contact_emails[devicename]    = contact_email
                            #devicename_contact_emails[parm_email]   = devicename

                            self.fmf_id[contact_id] = devicename
                            self.fmf_id[devicename] = contact_id
                            self.devicename_verified[devicename] = True
  
                            log_msg = ("Matched FmF Contact > {}({}) with {}, Id: {}").format(
                                devicename,
                                self.friendly_name.get(devicename),
                                contact_email,
                                contact_id)
                            self.log_info_msg(log_msg)
                            break

            for devicename in self.devicename_verified:
                if self.devicename_verified.get(devicename) is False:
                    parm_email = self.fmf_devicename_email.get(devicename)
                    devicename_contact_emails[devicename] = parm_email
                    log_msg = ("iCloud3 Error for {} ({}) > "
                        "Valid contact emails are {}").format(
                        self.username, self.group,
                        contacts_valid_emails[:-2])
                    self._save_event_halog_error("*", log_msg)
                    log_msg = ("iCloud3 Error for {} ({}) > "
                        "The email address for {} ({}) is invalid or is not "
                        "in the FmF contact list.").format(
                        self.username, self.group,
                        devicename,
                        parm_email)
                    self._save_event_halog_error("*", log_msg)

            self.fmf_devicename_email = {}
            self.fmf_devicename_email.update(devicename_contact_emails)

        except Exception as err:
            _LOGGER.exception(err)

#--------------------------------------------------------------------
    def _setup_tracked_devices_for_famshr(self):
        '''
        Scan the iCloud devices data. Select devices based on the
        include & exclude devices and device_type config parameters.

        Extract the friendly_name & device_type from the icloud data
        '''
        try:
            api_devicename_list = ''
            any_device_tracked_flag = False
            for device in self.api.devices:
                self.log_level_debug_rawdata("FamShr iCloud Device Data", device)

                status      = device.status(DEVICE_STATUS_SET)
                location    = status['location']
                devicename  = slugify(status[CONF_NAME].replace(' ', '', 99))
                device_type = status['deviceClass'].lower()

                api_devicename_list = '{}, {}'.format(
                        api_devicename_list,
                        devicename)

                if devicename in self.devicename_verified:
                    self.devicename_verified[devicename] = True

                    any_device_tracked_flag = True
                    api_devicename_list += "(OK)"

                    self.icloud_api_devices[devicename] = device
                    self.device_type[devicename]        = device_type

                else:
                    api_devicename_list += "(Not Tracked)"

            event_msg = ("iCloud Account devices{}").format(
                api_devicename_list)
            if any_device_tracked_flag:
                self._save_event_halog_info("*", event_msg)
            else:
                self._save_event_halog_error("*", event_msg)

        except Exception as err:
            #_LOGGER.exception(err)

            event_msg = ("iCloud3 Error for {} ({}) > "
                "Error Authenticating account or no data was returned from "
                "iCloud Web Services. Web Services may be down or the "
                "Username/Password may be invalid.").format(
                self.username, self.group)
            self._save_event_halog_error("*", event_msg)
            self.log_error_msg(log_msg)

#--------------------------------------------------------------------
    def _setup_tracked_devices_for_iosapp(self):
        '''
        The devices to be tracked are in the track_devices or the
        include_devices  config parameters.
        '''
        for devicename in self.devicename_verified:
            self.devicename_verified[devicename] = True

        return

 #--------------------------------------------------------------------
    def _setup_tracked_devices_config_parm(self, config_parameter):
        '''
        Set up the devices to be tracked and it's associated information
        for the configuration line entry. This will fill in the following
        fields based on the extracted devicename:
            device_type
            friendly_name
            fmf email address
            sensor.picture name
            device tracking flags
            tracked_devices list
        These fields may be overridden by the routines associated with the
        operating mode (fmf, icloud, iosapp)
        '''

        if config_parameter is None:
            return

        try:
            iosapp_v2_entities = self._get_entity_registry_entities('mobile_app')

        except Exception as err:
           # _LOGGER.exception(err)
           iosapp_v2_entities = []

        try:
            for track_device_line in config_parameter:
                di = self._decode_track_device_config_parms(
                            track_device_line, iosapp_v2_entities)

                if di is None:
                    return

                devicename = di[DI_DEVICENAME]
                if self._check_devicename_in_another_thread(devicename):
                    continue
                elif (self.iosapp_version.get(devicename) == 2 and
                        devicename == di[DI_DEVICENAME_IOSAPP]):
                    event_msg = ("iCloud3 Error: iCloud3 not tracking {}").format(
                        devicename)
                    self._save_event_halog_error("*", event_msg)
                    event_msg = ("iCloud3 Error: Then do the following: (1) Select "
                        "the Mobile_App entry for `{}`. (2) Scroll to the "
                        "`device_tracker.{}` statement. (3) Select it. (4) Click "
                        "the Settings icon. (5) Add or change the suffix of "
                        "the `device_tracker.{}` Entity ID to another value "
                        "(e.g., _2, _10, _iosappv2)."
                        "(6) Restart HA.").format(devicename, devicename, devicename)
                    self._save_event_halog_error("*", event_msg)
                    event_msg = ("iCloud3 Error: Conflicting device_tracker names `{}`. "
                        "The iCloud3 tracked_device is already assigned to "
                        "the IOS App v2. Duplicate names are not allowed for HA "
                        "Integration entities. You must change the IOS App v2 "
                        "entity name on the HA `Sidebar>Configuration>Integrations` "
                        "screen.").format(devicename)
                    self._save_event_halog_error("*", event_msg)
                    continue

                if di[DI_EMAIL]:
                    email = di[DI_EMAIL]
                    self.fmf_devicename_email[email]      = devicename
                    self.fmf_devicename_email[devicename] = email
                if di[DI_DEVICE_TYPE]:
                    self.device_type[devicename]          = di[DI_DEVICE_TYPE]
                if di[DI_NAME]:
                    self.friendly_name[devicename]        = di[DI_NAME]
                if di[DI_BADGE_PICTURE]:
                    self.badge_picture[devicename]        = di[DI_BADGE_PICTURE]
                if di[DI_DEVICENAME_IOSAPP]:
                    self.devicename_iosapp[devicename]    = di[DI_DEVICENAME_IOSAPP]
                    self.devicename_iosapp_id[devicename] = di[DI_DEVICENAME_IOSAPP_ID]
                if di[DI_SENSOR_IOSAPP_TRIGGER]:
                    self.iosapp_v2_last_trigger_entity[devicename] = di[DI_SENSOR_IOSAPP_TRIGGER]
                if di[DI_ZONES]:
                    self.track_from_zone[devicename]      = di[DI_ZONES]
                if di[DI_SENSOR_PREFIX_NAME]:
                    self.sensor_prefix_name[devicename]   = di[DI_SENSOR_PREFIX_NAME]

                self.devicename_verified[devicename] = False

        except Exception as err:
            _LOGGER.exception(err)

#--------------------------------------------------------------------
    def _decode_track_device_config_parms(self,
                track_device_line, iosapp_v2_entities):
        '''
        This will decode the device's parameter in the configuration file for
        the include_devices, sensor_name_prefix, track_devices items in the
        format of:
           - devicename > email, picture, iosapp, sensornameprefix

        If the item cotains '@', it is an email item,
        If the item contains .png  or .jpg, it is a picture item.
        Otherwise, it is the prefix name item for sensors

        The device_type and friendly names are also returned in the
        following order as a list item:
            devicename, device_type, friendlyname, email, picture, sensor name

        Various formats:

        Find my Friends:
        ----------------
        devicename > email_address
        devicename > email_address, badge_picture_name
        devicename > email_address, badge_picture_name, iosapp_number, name
        devicename > email_address, iosapp_number
        devicename > email_address, iosapp_number, name
        devicename > email_address, badge_picture_name, name
        devicename > email_address, name

        Find my Phone:
        --------------
        devicename
        devicename > badge_picture_name
        devicename > badge_picture_name, name
        devicename > iosapp_number
        devicename > iosapp_number, name
        devicename > name


        IOS App Version 1:
        ------------------
        devicename
        devicename > badge_picture_name
        devicename > badge_picture_name, name

        IOS App Version 2:
        ------------------
        devicename
        devicename > iosapp_number
        devicename > badge_picture_name, iosapp_number
        devicename > badge_picture_name, iosapp_number, name
        '''

        try:
            email         = None
            badge_picture = None
            fname         = None
            scan_entity_registry = (iosapp_v2_entities is not [])
            iosappv2_id   = ''
            device_type   = None
            sensor_prefix = None
            zones         = []


            #devicename_parameters = track_device_line.lower().split('>')
            devicename_parameters = track_device_line.split('>')
            devicename  = slugify(devicename_parameters[0].replace(' ', '', 99).lower())
            log_msg = ("Decoding > {}").format(track_device_line)
            self._save_event_halog_info(devicename, log_msg)

            #If tracking method is IOSAPP or FAMSHR, try to make a friendly
            #name from the devicename. If FMF, it will be retrieved from the
            #contacts data. If it is specified on the config parms, it will be
            #overridden with the specified name later.

            fname, device_type = self._extract_name_device_type(devicename)
            self.tracked_devices_config_parm[devicename] = track_device_line

            if len(devicename_parameters) > 1:
                parameters = devicename_parameters[1].strip()
                parameters = parameters + ',,,,,,'
            else:
                parameters = ''

            items = parameters.split(',')
            for itemx in items:
                item_entered = itemx.strip().replace(' ', '_', 99)
                item = item_entered.lower()

                if item == '':
                    continue
                elif instr(item, '@'):
                    email = item
                elif instr(item, 'png') or instr(item, 'jpg'):
                    badge_picture = item
                elif item == 'iosappv1':
                    scan_entity_registry = False
                elif item.startswith("_"):
                    iosappv2_id = item
                elif isnumber(item):
                    iosappv2_id = "_" + item
                elif item in self.zones:
                    if item != HOME:
                        if zones == []:
                            zones = [item]
                        else:
                            zones.append(item)
                else:
                    fname = item_entered

            zones.append(HOME)
            if badge_picture and instr(badge_picture, '/') == False:
                badge_picture = '/local/' + badge_picture

            event_log = (f"Results > FriendlyName-{fname}, Email-{email}, "
                         f"Picture-{badge_picture}, DeviceType-{device_type}")
            if zones != []:
                event_log += f", TrackFromZone-{zones}"
            self._save_event(devicename, event_log)
            
            
            #Cycle through the mobile_app 'core.entity_registry' items and see
            #if this 'device_tracker.devicename' exists. If so, it is using
            #the iosapp v2 component. Return the devicename with the device suffix (_#)
            #and the sensor.xxxx_last_update_trigger entity for that device.
            device_id          = None
            v2er_devicename    = ''
            v2er_devicename_id = ''
            self.iosapp_version[devicename] = 1
            sensor_last_trigger_entity = ''

            #if using ios app v2, cycle through iosapp_v2_entities in
            #.storage/core.entity_registry (mobile_app pltform) and get the
            #names of the iosappv2 device_tracker and sensor.last_update_trigger
            #names for this devicename. If iosappv2_id is specified, look for
            #the device_tracker with that number.
            if scan_entity_registry:
                devicename_iosappv2_id = devicename + iosappv2_id
                log_msg = ("Scanning {} for entity registry for IOS App v2 "
                    "device_tracker for {}").format(
                    self.entity_registry_file,
                    devicename_iosappv2_id)
                if iosappv2_id != '':
                    log_msg += (", devicename suffix specified ({})").format(iosappv2_id)
                self.log_info_msg(log_msg)

                #Initial scan to find device_tracker.devicename record
                for entity in (x for x in iosapp_v2_entities \
                        if x['entity_id'].startswith("device_tracker.")):
                    v2er_devicename = entity['entity_id'].replace("device_tracker.", "", 5)
                    log_msg = ("Checking {} for {}").format(
                        v2er_devicename, devicename_iosappv2_id)
                    self.log_debug_msg(devicename, log_msg)
                    if iosappv2_id != '' and v2er_devicename != devicename_iosappv2_id:
                        continue

                    if (v2er_devicename.startswith(devicename) or
                            devicename.startswith(v2er_devicename)):
                        log_msg = ("Matched IOS App v2 entity {} with "
                            "iCloud3 tracked_device {}").format(
                            v2er_devicename, devicename)
                        self.log_info_msg(log_msg)

                        self.iosapp_version[devicename] = 2
                        device_id          = entity['device_id']
                        v2er_devicename_id = v2er_devicename.replace(devicename, '', 5)
                        break

                #Go back thru and look for sensor.last_update_trigger for deviceID
                if device_id:
                    for entity in (x for x in iosapp_v2_entities \
                            if instr(x['entity_id'], 'last_update_trigger')):

                        log_msg = ("Checking {}").format(entity['entity_id'])
                        #self.log_debug_msg(devicename, log_msg)

                        if (entity['device_id'] == device_id):
                            sensor_last_trigger_entity = entity['entity_id'].replace('sensor.', '', 5)
                            log_msg = ("Matched IOS App v2  {} with "
                                "iCloud3 tracked_device {}").format(
                                entity['entity_id'], devicename)
                            self.log_info_msg(log_msg)
                            break

            if self.iosapp_version[devicename] == 1:
                if scan_entity_registry:
                    event_msg = ("Determine IOS App version > `device_tracker.{}` "
                        " not found in Entity Registry IOS App v1 will be used.")\
                        .format(devicename_iosappv2_id)
                    self._save_event(devicename, event_msg)
                v2er_devicename    = devicename
                v2er_devicename_id = ''
                sensor_last_trigger_entity = ''

            device_info = [devicename, device_type, fname, email, badge_picture,
                           v2er_devicename, v2er_devicename_id,
                           sensor_last_trigger_entity, zones, sensor_prefix]

            log_msg = ("Extract Trk_Dev Parm, dev_info={}").format(device_info)
            self.log_debug_msg(devicename, log_msg)

        except Exception as err:
            _LOGGER.exception(err)

        return device_info
#--------------------------------------------------------------------
    def _get_entity_registry_entities(self, platform):
        '''
        Read the /config/.storage/core.entity_registry file and return
        the entities for platform ('mobile_app', 'ios', etc)
        '''

        try:
            if self.entity_registry_file == None:
                self.entity_registry_file  = self.hass.config.path(
                        STORAGE_DIR, STORAGE_KEY_ENTITY_REGISTRY)

            entities          = []
            entitity_reg_file = open(self.entity_registry_file)
            entitity_reg_str  = entitity_reg_file.read()
            entitity_reg_data = json.loads(entitity_reg_str)
            entitity_reg_entities = entitity_reg_data['data']['entities']
            entitity_reg_file.close()

            for entity in entitity_reg_entities:
                if (entity['platform'] == platform):
                    entities.append(entity)

            #TRACE("entity_registry_file",self.entity_registry_file)
            #TRACE('get_entities',entities)
            #TRACE('reading reg via hass')

        except Exception as err:
            _LOGGER.exception(err)
            pass

        return entities
#--------------------------------------------------------------------
    def _check_valid_ha_device_tracker(self, devicename):
        '''
        Validate the 'device_tracker.devicename' entity during the iCloud3
        Stage 2 initialization. If it does not exist, then it has not been set
        up in known_devices.yaml (and/or the iosapp) and can not be used ty
        the 'see' function thatupdates the location information.
        '''
        try:
            retry_cnt = 0
            entity_id = self._format_entity_id(devicename)

            while retry_cnt < 10:
                dev_data  = self.hass.states.get(entity_id)

                if dev_data:
                    dev_attrs = dev_data.attributes

                    if dev_attrs:
                        return True
                retry_cnt += 1

        #except (KeyError, AttributeError):
        #    pass

        except Exception as err:
            _LOGGER.exception(err)

        return False

#########################################################
#
#   DEVICE SENSOR SETUP ROUTINES
#
#########################################################
    def _setup_sensor_base_attrs(self, devicename):
        '''
        The sensor name prefix can be the devicename or a name specified on
        the track_device configuration parameter        '''

        #if self.sensor_prefix_name.get(devicename) == '':
        self.sensor_prefix_name[devicename] = devicename

        attr_prefix_fname = self.sensor_prefix_name.get(devicename)

        #Format sensor['friendly_name'] attribute prefix
        attr_prefix_fname = attr_prefix_fname.replace('_','-').title()
        attr_prefix_fname = attr_prefix_fname.replace('Ip','-iP')
        attr_prefix_fname = attr_prefix_fname.replace('Iw','-iW')
        attr_prefix_fname = attr_prefix_fname.replace('--','-')

        self.sensor_attr_fname_prefix[devicename] = '{}-'.format(attr_prefix_fname)

        badge_attrs = {}
        badge_attrs['entity_picture'] = self.badge_picture.get(devicename)
        badge_attrs['friendly_name']  = self.friendly_name.get(devicename)
        badge_attrs['icon']           = SENSOR_ATTR_ICON.get('badge')
        self.sensor_badge_attrs[devicename] = badge_attrs

        for zone in self.track_from_zone.get(devicename):
            if zone == 'home':
                zone_prefix = ''
            else:
                zone_prefix = zone + '_'
            event_msg = ("Sensor entity prefix > sensor.{}{}").format(
                zone_prefix,
                self.sensor_prefix_name.get(devicename))
            self._save_event(devicename, event_msg)

        log_msg = ("Set up sensor name for device, devicename={}, "
                    "entity_base={}").format(devicename,
                    self.sensor_prefix_name.get(devicename))
        self.log_debug_msg(devicename, log_msg)

        return

#--------------------------------------------------------------------
    def _setup_sensors_custom_list(self):
        '''
        This will process the 'sensors' and 'exclude_sensors' config
        parameters if 'sensors' exists, only those sensors wil be displayed.
        if 'exclude_sensors' eists, those sensors will not be displayed.
        'sensors' takes ppresidence over 'exclude_sensors'.
        '''

        if self.sensor_ids != []:
            self.sensors_custom_list = []
            for sensor_id in self.sensor_ids:
                id = sensor_id.lower().strip()
                if id in SENSOR_ID_NAME_LIST:
                    self.sensors_custom_list.append(SENSOR_ID_NAME_LIST.get(id))

        elif self.exclude_sensor_ids != []:
            self.sensors_custom_list.extend(SENSOR_DEVICE_ATTRS)
            for sensor_id in self.exclude_sensor_ids:
                id = sensor_id.lower().strip()
                if id in SENSOR_ID_NAME_LIST:
                    if SENSOR_ID_NAME_LIST.get(id) in self.sensors_custom_list:
                        self.sensors_custom_list.remove(SENSOR_ID_NAME_LIST.get(id))
        else:
            self.sensors_custom_list.extend(SENSOR_DEVICE_ATTRS)


#########################################################
#
#   DEVICE STATUS SUPPORT FUNCTIONS FOR GPS ACCURACY, OLD LOC DATA, ETC
#
#########################################################
    def _check_location_isold(self, devicename, arg_location_isold_flag, timestamp_secs):
        """
        If this is checked in the icloud location cycle,
        check if the location isold flag. Then check to see if
        the current timestamp is the same as the timestamp on the previous
        poll.

        If this is checked in the iosapp cycle,  the trigger transaction has
        already updated the lat/long so
        you don't want to discard the record just because it is old.
        If in a zone, use the trigger but check the distance from the
        zone when updating the device. If the distance from the zone = 0,
        then reset the lat/long to the center of the zone.
        """

        try:
            isold_cnt = 0
            location_isold_flag = arg_location_isold_flag

            #Set isold flag if timestamp is more than 2 minutes old
            age     = int(self._secs_since(timestamp_secs))
            age_str = self._secs_to_time_str(age)
            #location_isold_flag = (age > 120)
            location_isold_flag = (age > self.old_location_threshold)

            if location_isold_flag:
                self.last_fmf_refresh = self.this_update_secs - 120
                self.location_isold_cnt[devicename] += 1
                #self.count_update_ignore[devicename]  += 1
            else:
                self.location_isold_cnt[devicename] = 0

            log_msg = ("►CHECK ISOLD, Time={}, isOldFlag={}, Age={}").format(
                self._secs_to_time(timestamp_secs),
                arg_location_isold_flag,
                age_str)
            self.log_debug_msg(devicename, log_msg)

        except Exception as err:
            _LOGGER.exception(err)
            location_isold_flag = False

            log_msg = ("►►INTERNAL ERROR (ChkOldLoc)")
            self.log_error_msg(log_msg)

        return location_isold_flag

#--------------------------------------------------------------------
    def _check_poor_gps(self, devicename, gps_accuracy):
        if gps_accuracy > self.gps_accuracy_threshold:
            self.last_fmf_refresh = self.this_update_secs - 120
            self.poor_gps_accuracy_flag[devicename] = True
            self.poor_gps_accuracy_cnt[devicename] += 1

            event_msg = "Poor GPS Accuracy, distance {}m, (#{})".format(
                gps_accuracy,
                self.poor_gps_accuracy_cnt.get(devicename))
            self._save_event(devicename, event_msg)

        else:
            self.poor_gps_accuracy_flag[devicename] = False
            self.poor_gps_accuracy_cnt[devicename]  = 0

#--------------------------------------------------------------------
    def _check_next_update_time_reached(self, devicename = None):
        '''
        Cycle through the next_update_secs for all devices and
        determine if one of them is earlier than the current time.
        If so, the devices need to be updated.
        '''
        try:
            if self.next_update_secs is None:
                return None

            for devicename_zone in self.next_update_secs:
                if (devicename is None or devicename_zone.startswith(devicename)):
                    time_till_update = self.next_update_secs.get(devicename_zone) - \
                            self.this_update_secs
                    self.next_update_in_secs[devicename_zone] = time_till_update

                    if time_till_update <= 0:
                        return '{}@{}'.format(
                                    devicename_zone,
                                    self._secs_to_time(self.next_update_secs.get(devicename_zone)))

        except Exception as err:
            _LOGGER.exception(err)

        return None

#--------------------------------------------------------------------
    def _check_in_zone_and_before_next_update(self, devicename):
        '''
        If updated because another device was updated and this device is
        in a zone and it's next time has not been reached, do not update now
        '''
        try:
            if (self.state_this_poll.get(devicename) != NOT_SET and
                    self._is_inzone(devicename) and
                    self._was_inzone(devicename) and
                    self._check_next_update_time_reached(devicename) is None):

                #log_msg = ("{} Not updated, in zone {}").format(
                 #   self._format_fname_devtype(devicename),
                 #   self.state_this_poll.get(devicename))
                #self.log_debug_msg(devicename, log_msg)
                #event_msg = "Not updated, already in Zone {}".format(
                 #   self.state_this_poll.get(devicename))
                #self._save_event(devicename, event_msg)
                return True

        except Exception as err:
            _LOGGER.exception(err)

        return False

#--------------------------------------------------------------------
    @staticmethod
    def _get_interval_for_error_retry_cnt(retry_cnt):
        cycle, cycle_cnt = divmod(retry_cnt, 4)
        if cycle_cnt == 0:
            if cycle == 1:
                interval = 60           #1 min
            elif cycle == 2:
                interval = 300          #5 min
            elif cycle == 3:
                interval = 900          #15 min
            else:
                interval = 1800         #30 min
        else:
            interval = 15               #15 sec

        return interval
#--------------------------------------------------------------------
    def _display_time_till_update_info_msg(self, devicename_zone, age_secs):
        info_msg = "●{}●".format(self._secs_to_minsec_str(age_secs))

        attrs = {}
        attrs[ATTR_NEXT_UPDATE_TIME] = info_msg

        self._update_device_sensors(devicename_zone, attrs)

#--------------------------------------------------------------------
    def _log_device_status_attrubutes(self, status):

        """
        Status={'batteryLevel': 1.0, 'deviceDisplayName': 'iPhone X',
        'deviceStatus': '200', CONF_NAME: 'Gary-iPhone',
        'deviceModel': 'iphoneX-1-2-0', 'rawDeviceModel': 'iPhone10,6',
        'deviceClass': 'iPhone',
        'id':'qyXlfsz1BIOGxcqDxDleX63Mr63NqBxvJcajuZT3y05RyahM3/OMpuHYVN
        SUzmWV', 'lowPowerMode': False, 'batteryStatus': 'NotCharging',
        'fmlyShare': False, 'location': {'isOld': False,
        'isInaccurate': False, 'altitude': 0.0, 'positionType': 'GPS'
        'latitude': 27.726843548976, 'floorLevel': 0,
        'horizontalAccuracy': 48.00000000000001,
        'locationType': '', 'timeStamp': 1539662398966,
        'locationFinished': False, 'verticalAccuracy': 0.0,
        'longitude': -80.39036092533418}, 'locationCapable': True,
        'locationEnabled': True, 'isLocating': True, 'remoteLock': None,
        'activationLocked': True, 'lockedTimestamp': None,
        'lostModeCapable': True, 'lostModeEnabled': False,
        'locFoundEnabled': False, 'lostDevice': None,
        'lostTimestamp': '', 'remoteWipe': None,
        'wipeInProgress': False, 'wipedTimestamp': None, 'isMac': False}
        """

        log_msg = ("►ICLOUD DATA, DEVICE ID={}, ▶deviceDisplayName={}").format(
            status,
            status['deviceDisplayName'])
        self.log_debug_msg('*', log_msg)

        location = status['location']

        log_msg = ("►ICLOUD DEVICE STATUS/LOCATION, ●deviceDisplayName={}, "
            "●deviceStatus={}, ●name={}, ●deviceClass={}, "
            "●batteryLevel={}, ●batteryStatus={}, "
            "●isOld={}, ●positionType={}, ●latitude={}, ●longitude={}, "
            "●horizontalAccuracy={}, ●timeStamp={}({})").format(
            status['deviceDisplayName'],
            status[ATTR_ICLOUD_DEVICE_STATUS],
            status[CONF_NAME],
            status['deviceClass'],
            status[ATTR_ICLOUD_BATTERY_LEVEL],
            status[ATTR_ICLOUD_BATTERY_STATUS],
            location[ATTR_ISOLD],
            location['positionType'],
            location[ATTR_LATITUDE],
            location[ATTR_LONGITUDE],
            location[ATTR_ICLOUD_HORIZONTAL_ACCURACY],
            location[ATTR_ICLOUD_LOC_TIMESTAMP],
            self._timestamp_to_time_utcsecs(location[ATTR_ICLOUD_LOC_TIMESTAMP]))
        self.log_debug_msg('*', log_msg)
        return True

#--------------------------------------------------------------------
    def _log_start_finish_update_banner(self, start_finish_symbol, devicename,
                method, update_reason):
        '''
        Display a banner in the log file at the start and finish of a
        device update cycle
        '''

        log_msg = ( "^ {} ^ {}-{}-{} ^^ State={} ^^ {} ^").format(
                method,
                devicename,
                self.group,
                self.base_zone,
                self.state_this_poll.get(devicename),
                update_reason)

        log_msg2 = log_msg.replace('^', start_finish_symbol, 99).replace(" ",".").upper()
        self.log_debug_msg(devicename, log_msg2)

#########################################################
#
#   EVENT LOG ROUTINES
#
#########################################################
    def _setup_event_log_base_attrs(self):
        '''
        Set up the name, picture and devicename attributes in the Event Log
        sensor. Read the sensor attributes first to see if it was set up by
        another instance of iCloud3 for a different iCloud acount.
        '''
        name_attrs       = {}
        try:
            attrs = self.hass.states.get(SENSOR_EVENT_LOG_ENTITY).attributes

            if attrs and 'names' in attrs:
                name_attrs = attrs.get("names")

            #_LOGGER.error("Get attrs(name)>>%s",attrs.get("names"))
            #_LOGGER.error("Get name_attrs>>%s",name_attrs)
            #_LOGGER.error("Get name_attrs(name)>>%s",name_attrs.get("names"))

        except (KeyError, AttributeError):
            pass
        except Exception as err:
            _LOGGER.exception(err)

        if self.tracked_devices:
            for devicename in self.tracked_devices:
                name_attrs[devicename] = self.friendly_name.get(devicename)
        else:
            name_attrs = {'iCloud3 Startup Events': 'Error Messages'}

        base_attrs          = {}
        base_attrs["names"] = name_attrs
        base_attrs["logs"]  = ""

        self.hass.states.set(SENSOR_EVENT_LOG_ENTITY, "Initialized", base_attrs)
        self.event_log_base_attrs = base_attrs
        if len(self.tracked_devices) > 0:
            self.log_table_length  = 999 * len(self.tracked_devices)

        return

#------------------------------------------------------
    def _save_event(self, devicename, event_text):

        try:
            if (instr(event_text, "▼") or instr(event_text, "▲") or
                    instr(event_text, "event_log")):
                return
                
            devicename_zone = self._format_devicename_zone(devicename, HOME)
            this_update_time = dt_util.now().strftime('%H:%M:%S')

            if devicename == '' or devicename == 'Initializing':
                friendly_name = '*'
            else:
                state       = self.state_this_poll.get(devicename)
                zone_names  = self._get_zone_names(self.zone_current.get(devicename))
                zone        = zone_names[1]
                interval    = self.interval_str.get(devicename_zone)
                travel_time = self.last_tavel_time.get(devicename_zone)
                distance    = self.last_distance_str.get(devicename_zone)

            if devicename == '*' or state       is None: state = ''
            if devicename == '*' or zone        is None: zone = ''
            if devicename == '*' or distance    is None: distance = ''
            if devicename == '*' or travel_time is None or travel_time == 0: travel_time = ''
            if devicename == '*' or interval    is None: interval = ''
            if devicename == '*' or devicename  is None: devicename = '*'
            
            if instr(state, STATIONARY): state = STATIONARY
            if instr(zone, STATIONARY):  zone  = STATIONARY
            
            if event_text.startswith('__'): event_text = event_text[2:]
            event_text = event_text.replace('"', '`', 99)
            event_text = event_text.replace("'", "`", 99)
            event_text = event_text.replace('~','--', 99)
            event_text = event_text.replace('@','@ ', 99)
            event_text = event_text.replace('Background','Bkgnd', 99)
            event_text = event_text.replace('Geographic','Geo', 99)
            #event_text = event_text.replace(STATIONARY,'stat', 99)
            event_text = event_text.replace('Significant','Sig', 99)
            if len(event_text) == 0:
                event_text = 'Info Message'
             
            #Break the event_text string into chunks of 250 characters each and
            #create an event_log recd for each chunk
            et_pos_end = len(event_text)
            et_pos_start = int(et_pos_end/250) * 250
            while et_pos_start >= 0:
                event_text_chunk = event_text[et_pos_start:et_pos_end]
                et_pos_end = et_pos_start
                et_pos_start -= 250
                if len(event_text) > 250: event_text_chunk += ' .....'
                if et_pos_start < 0:
                    event_recd = [devicename, this_update_time,
                                  state, zone, interval, travel_time,
                                  distance, event_text_chunk]
                else:
                    event_recd = [devicename, '',
                                  '', '', '', '',
                                  '', event_text_chunk]
                   
                if self.event_log_table is None:
                    self.event_log_table = []

                if devicename != '*':
                   while len(self.event_log_table) > self.log_table_length:
                        self.event_log_table.pop(0)

                #self.event_log_table.append(event_recd)
                self.event_log_table.insert(0, event_recd)

        except Exception as err:
            _LOGGER.exception(err)

#------------------------------------------------------
    def _update_event_log_sensor_line_items(self, devicename):
        """Display the event log"""

        try:
            if self.event_log_base_attrs:
                log_attrs = self.event_log_base_attrs.copy()

            attr_recd  = {}
            attr_event = {}
            log_attrs["log_level_debug"] = "On" if self.log_level_eventlog_flag else "Off"

            if devicename is None:
                return
            elif devicename == 'clear_log_items':
                log_attrs["filtername"] = "ClearLogItems"
            elif devicename == "*" :
                log_attrs["filtername"] = "Initialize"
            else:
                log_attrs["filtername"] = self.friendly_name.get(devicename)
                self.event_cnt[devicename] += 1

            #log_msg = ("Updating Event Log for {}").format(devicename)
            #self.log_debug_msg(devicename, log_msg)
 
            
            if devicename == 'clear_log_items':
                max_recds  = EVENT_LOG_CLEAR_CNT
                self.event_log_chear_secs = 9999999999
                devicename = self.event_log_last_devicename
            else:
                max_recds = 99999
                self.event_log_chear_secs = self.this_update_secs + EVENT_LOG_CLEAR_SECS
                self.event_log_last_devicename = devicename
            
            #The state must change for the recds to be refreshed on the
            #Lovelace card. If the state does not change, the new information
            #is not displayed. Add the update time to make it unique.

            log_update_time = ("{}, {}").format(
                    dt_util.now().strftime("%a, %m/%d"),
                    dt_util.now().strftime(self.um_time_strfmt))
            log_attrs["update_time"] = log_update_time
            self.event_log_sensor_state = ("{}:{}").format(devicename, log_update_time)
            
            attr_recd = self._setup_event_log_event_recds(devicename, max_recds)
            log_attrs["logs"] = attr_recd

            self.hass.states.set(SENSOR_EVENT_LOG_ENTITY, self.event_log_sensor_state, log_attrs)

        except Exception as err:
            _LOGGER.exception(err)
#------------------------------------------------------
    def _setup_event_log_event_recds(self, devicename, max_recds=99999):
        '''
        Build the event items attribute for the event log sensor. Each item record
        is [devicename, time, state, zone, interval, travTime, dist, textMsg]
        Select the items for the devicename or '*' and return the string of
        the resulting list to be passed to the Event Log
        '''

        el_devicename_check=['*', devicename]

        attr_recd = [el_recd[1:8] for el_recd in self.event_log_table \
                if el_recd[0] in el_devicename_check]

        if max_recds == EVENT_LOG_CLEAR_CNT:
            recd_cnt = len(attr_recd)
            attr_recd = attr_recd[0:max_recds]
            control_recd = ['',' ',' ',' ',' ',' ',f'^^^ Click `Refresh` to display \
                                all records ({max_recds} of {recd_cnt} displayed) ^^^']
            attr_recd.insert(0, control_recd)

        control_recd = ['00:00:00','','','','','','Last Record']
        attr_recd.append(control_recd)

        return str(attr_recd)
#########################################################
#
#   WAZE ROUTINES
#
#########################################################
    def _get_waze_data(self, devicename,
                            this_lat, this_long, last_lat,
                            last_long, current_zone, last_dist_from_zone_km):

        try:
            if not self.distance_method_waze_flag:
                return ( WAZE_NOT_USED, 0, 0, 0)
            elif current_zone == self.base_zone:        #HOME:
                return (WAZE_USED, 0, 0, 0)
            elif self.waze_status == WAZE_PAUSED:
                return (WAZE_PAUSED, 0, 0, 0)

            try:
                waze_from_zone = self._get_waze_distance(devicename,
                        this_lat, this_long,
                        self.base_zone_lat, self.base_zone_long)

                waze_status = waze_from_zone[0]
                if waze_status != WAZE_ERROR:
                    waze_from_last_poll = self._get_waze_distance(devicename,
                            last_lat, last_long, this_lat, this_long)
                else:
                    waze_from_last_poll = [WAZE_ERROR, 0, 0]

            except Exception as err:
                if err == "Name 'WazeRouteCalculator' is not defined":
                    self.distance_method_waze_flag = False
                    return (WAZE_NOT_USED, 0, 0, 0)

                return (WAZE_ERROR, 0, 0, 0)

            try:
                waze_dist_from_zone_km = self._round_to_zero(waze_from_zone[1])
                waze_time_from_zone = self._round_to_zero(waze_from_zone[2])
                waze_dist_last_poll = self._round_to_zero(waze_from_last_poll[1])

                if waze_dist_from_zone_km == 0:
                    waze_time_from_zone = 0
                else:
                    waze_time_from_zone = self._round_to_zero(waze_from_zone[2])

                if ((waze_dist_from_zone_km > self.waze_max_distance) or
                     (waze_dist_from_zone_km < self.waze_min_distance)):
                    waze_status = WAZE_OUT_OF_RANGE

            except Exception as err:
                log_msg = ("►►INTERNAL ERROR (ProcWazeData)-{})".format(err))
                self.log_error_msg(log_msg)

            log_msg = ("►WAZE DISTANCES CALCULATED>, "
                "Status={}, DistFromHome={}, TimeFromHome={}, "
                " DistLastPoll={}, "
                "WazeFromHome={}, WazeFromLastPoll={}").format(
                waze_status,
                waze_dist_from_zone_km,
                waze_time_from_zone,
                waze_dist_last_poll,
                waze_from_zone,
                waze_from_last_poll)
            self.log_debug_interval_msg(devicename, log_msg)

            return (waze_status, waze_dist_from_zone_km, waze_time_from_zone,
                    waze_dist_last_poll)

        except Exception as err:
            log_msg = ("►►INTERNAL ERROR (GetWazeData-{})".format(err))
            self.log_info_msg(log_msg)

            return (WAZE_ERROR, 0, 0, 0)

#--------------------------------------------------------------------
    def _get_waze_distance(self, devicename, from_lat, from_long, to_lat,
                        to_long):
        """
        Example output:
            Time 72.42 minutes, distance 121.33 km.
            (72.41666666666667, 121.325)

        See https://github.com/home-assistant/home-assistant/blob
        /master/homeassistant/components/sensor/waze_travel_time.py
        See https://github.com/kovacsbalu/WazeRouteCalculator
        """

        if not self.distance_method_waze_flag:
            return (WAZE_NOT_USED, 0, 0)

        try:
            from_loc = '{},{}'.format(from_lat, from_long)
            to_loc   = '{},{}'.format(to_lat, to_long)

            retry_cnt = 0
            while retry_cnt < 3:
                try:
                    route = WazeRouteCalculator.WazeRouteCalculator(
                            from_loc, to_loc, self.waze_region)

                    route_time, route_distance = \
                        route.calc_route_info(self.waze_realtime)

                    route_time     = round(route_time, 0)
                    route_distance = round(route_distance, 2)

                    return (WAZE_USED, route_distance, route_time)

                except WazeRouteCalculator.WRCError as err:
                    retry_cnt += 1
                    log_msg = ("Waze Server Error={}, Retrying (#{})").format(
                    err, retry_cnt)
                    self.log_info_msg(log_msg)

            return (WAZE_ERROR, 0, 0)

        except Exception as err:
            log_msg = ("►►INTERNAL ERROR (GetWazeDist-{})".format(err))
            self.log_info_msg(log_msg)

            return (WAZE_ERROR, 0, 0)
#--------------------------------------------------------------------
    def _get_waze_from_data_history(self, devicename,
                        curr_dist_from_zone_km, this_lat, this_long):
        '''
        Before getting Waze data, look at all other devices to see
        if there are any really close. If so, don't call waze but use their
        distance & time instead if the data it passes distance and age
        tests.

        The other device's distance from home and distance from last
        poll might not be the same as this devices current location
        but it should be close enough.

        last_waze_data is a list in the following format:
           [timestamp, latitudeWhenCalculated, longitudeWhenCalculated,
                [distance, time, distMoved]]
        '''
        #return None
        if not self.distance_method_waze_flag:
            return None
        elif self.waze_status == WAZE_PAUSED:
            return None
        elif self.base_zone != HOME:
            return None
        elif self._isnot_inzone(devicename):
            pass
        elif self.state_this_poll.get(devicename) != self.zone_current.get(devicename):
            return None

        #Calculate how far the old data can be from the new data before the
        #data will be refreshed.
        test_distance = curr_dist_from_zone_km * .05
        if test_distance > 5:
            test_distance = 5

        try:
            for near_devicename_zone in self.waze_distance_history:
                devicename_zone = self._format_devicename_zone(devicename)

                self.waze_history_data_used_flag[devicename_zone] = False
                waze_data_other_device = self.waze_distance_history.get(near_devicename_zone)
                #Skip if this device doesn't have any Waze data saved or it's for
                #another base_zone.
                if len(waze_data_other_device) == 0:
                    continue
                elif len(waze_data_other_device[3]) == 0:
                    continue
                elif near_devicename_zone.endswith(':'+self.base_zone) == False:
                    continue

                waze_data_timestamp = waze_data_other_device[0]
                waze_data_latitude  = waze_data_other_device[1]
                waze_data_longitude = waze_data_other_device[2]

                dist_from_other_waze_data = self._calc_distance_km(
                            this_lat, this_long,
                            waze_data_latitude, waze_data_longitude)

                #Get distance from current location and Waze data
                #If close enough, use it regardless of whose it is
                if dist_from_other_waze_data < test_distance:
                    event_msg = ("Waze history data used from {} ({}m away), "
                        "Dist from `{}` zone-{}km, Travel time-{}min").format(
                        near_devicename_zone,
                        dist_from_other_waze_data,
                        self.base_zone,
                        waze_data_other_device[3][1],
                        waze_data_other_device[3][2])
                    self._save_event_halog_info(devicename, event_msg)

                    self.waze_data_copied_from[devicename_zone] = near_devicename_zone

                    #Return Waze data (Status, distance, time, dist_moved)
                    self.waze_history_data_used_flag[near_devicename_zone] = True
                    return waze_data_other_device[3]

        except Exception as err:
            _LOGGER.exception(err)
        return None

#--------------------------------------------------------------------
    def _format_waze_time_msg(self, devicename, waze_time_from_zone,
                                waze_dist_from_zone):
        '''
        Return the message displayed in the waze time field ►►
        '''

        #Display time to the nearest minute if more than 3 min away
        if self.waze_status == WAZE_USED:
            t = waze_time_from_zone * 60
            r = 0
            if t > 180:
                t, r = divmod(t, 60)
                t = t + 1 if r > 30 else t
                t = t * 60

            waze_time_msg = self._secs_to_time_str(t)

        else:
            waze_time_msg = ''

        return waze_time_msg
#--------------------------------------------------------------------
    def _verify_waze_installation(self):
        '''
        Report on Waze Route alculator service availability
        '''

        self.log_info_msg("Verifying Waze Route Service component")

        if (WAZE_IMPORT_SUCCESSFUL == 'YES' and
                    self.distance_method_waze_flag):
            self.waze_status = WAZE_USED
        else:
            self.waze_status = WAZE_NOT_USED
            self.distance_method_waze_flag = False
            self.log_info_msg("Waze Route Service not available")

#########################################################
#
#   MULTIPLE PLATFORM/GROUP ROUTINES
#
#########################################################
    def _check_devicename_in_another_thread(self, devicename):
        '''
        Cycle through all instances of the ICLOUD3_TRACKED_DEVICES and check
        to see if  this devicename is also in another the tracked_devices
        for group/instance/thread/platform.
        If so, return True to reject this devicename and generate an error msg.

        ICLOUD3_TRACKED_DEVICES = {
            'work': ['gary_iphone > gcobb321@gmail.com, gary.png'],
            'group2': ['gary_iphone > gcobb321@gmail.com, gary.png, whse',
                       'lillian_iphone > lilliancobb321@gmail.com, lillian.png']}
        '''
        try:
            for group in ICLOUD3_GROUPS:
                if group != self.group and ICLOUD3_GROUPS.index(group) > 0:
                    tracked_devices = ICLOUD3_TRACKED_DEVICES.get(group)
                    for tracked_device in tracked_devices:
                        tracked_devicename = tracked_device.split('>')[0].strip()
                        if devicename == tracked_devicename:
                            log_msg = ("Error: A device can only be tracked in "
                                "one platform/group {}. '{}' was defined multiple "
                                "groups and will not be tracked in '{}'.").format(
                                    ICLOUD3_GROUPS,
                                    devicename,
                                    self.group)
                            self._save_event_halog_error('*', log_msg)
                            return True

        except Exception as err:
            _LOGGER.exception(err)

        return False


#########################################################
#
#   log_, trace_ MESSAGE ROUTINES
#
#########################################################
    def log_info_msg(self, log_msg):
        if self.log_level_eventlog_flag: 
            if log_msg.startswith("►") == False: log_msg = f"►{log_msg}"
            self._save_event("*", log_msg)
        _LOGGER.info(log_msg)

    def _save_event_halog_info(self, devicename, log_msg):
        self._save_event(devicename, log_msg)
        log_msg = ("{} {}").format(self._format_fname_devtype(devicename), log_msg)
        self.log_info_msg(log_msg)
        
    @staticmethod
    def log_warning_msg(log_msg):
        _LOGGER.warning(log_msg)

#--------------------------------------
    @staticmethod
    def log_error_msg(log_msg):
        _LOGGER.error(log_msg)
        
    def _save_event_halog_error(self, devicename, log_msg):
        self._save_event(devicename, log_msg)
        log_msg = ("{} {}").format(self._format_fname_devtype(devicename), log_msg)
        self.log_error_msg(log_msg)

#--------------------------------------
    def log_debug_msg(self, devicename, log_msg, also_to_eventlog = False):
        if self.log_level_eventlog_flag: 
            if log_msg.startswith("►") == False: log_msg = f"►{log_msg}"
            self._save_event(devicename, log_msg)
            
        if self.log_level_debug_flag:  #self.log_debug_msgs_trace_flag:
            _LOGGER.info("◆%s◆ %s", devicename, log_msg)
        else:
            _LOGGER.debug("◆%s◆ %s", devicename, log_msg)
             
#--------------------------------------          
    def log_debug_interval_msg(self, devicename, log_msg):
        if self.log_level_intervalcalc_flag:
            _LOGGER.debug("◆%s◆ %s", devicename, log_msg)
            
            if self.log_level_eventlog_flag:
                if log_msg.startswith("►") == False: log_msg = f"►{log_msg}"
                self._save_event(devicename, log_msg)

    def log_level_debug_rawdata(self, title, data):
        display_title = title.replace(" ",".").upper()
        if self.log_level_debug_rawdata_flag:
            log_msg = (f"▼-▼-▼-▼-▼-▼..{display_title}..▼-▼-▼-▼-▼-▼")
            self.log_debug_msg("*", log_msg)
            log_msg = (f"{data}")
            self.log_debug_msg("*", log_msg)
            log_msg = (f"▲-▲-▲-▲-▲-▲..{display_title}..▲-▲-▲-▲-▲-▲")
            self.log_debug_msg("*", log_msg)
#--------------------------------------
    def log_debug_msg2(self, log_msg):
            _LOGGER.debug(log_msg)

    def trace2(self, devicename, variable_name, variable1 = '%', variable2 = '%',
            variable3 = '%', variable4 = '%'):
        '''
        Display a message or variable in the HA log file
        '''
        if variable_name != '':
            value_str = f"{variable_name} = "
            if variable1 != '%': value_str += f" ({variable1})"
            if variable2 != '%': value_str += f" ({variable2})"
            if variable3 != '%': value_str += f" ({variable3})"
            if variable4 != '%': value_str += f" ({variable4})"

            self._save_event(devicename, value_str)
            _LOGGER.info(value_str)

    @staticmethod
    def _internal_error_msg(function_name, err_text: str='',
                section_name: str=''):
        log_msg = ("►►INTERNAL ERROR-RETRYING ({}:{}-{})".format(
            function_name,
            section_name,
            err_text))
        _LOGGER.error(log_msg)

        attrs = {}
        attrs[ATTR_INTERVAL]           = '0 sec'
        attrs[ATTR_NEXT_UPDATE_TIME]   = ZERO_HHMMSS
        attrs[ATTR_INFO]               = log_msg

        return attrs

#########################################################
#
#   TIME & DISTANCE UTILITY ROUTINES
#
#########################################################
    @staticmethod
    def _time_now_secs():
        ''' Return the epoch seconds in utc time '''

        return int(time.time())
#--------------------------------------------------------------------
    def _secs_to_time(self, e_seconds, time_24h = False):
        """ Convert seconds to hh:mm:ss """

        if e_seconds == 0:
            return ZERO_HHMMSS
        else:
            t_struct = time.localtime(e_seconds + self.e_seconds_local_offset_secs)
            if time_24h:
                return  time.strftime("%H:%M:%S", t_struct).lstrip('0')
            else:
                return  time.strftime(self.um_time_strfmt, t_struct).lstrip('0')

#--------------------------------------------------------------------
    @staticmethod
    def _secs_to_time_str(time_sec):
        """ Create the time string from seconds """

        if time_sec < 60:
            time_str = str(round(time_sec, 0)) + " sec"
        elif time_sec < 3600:
            time_str = str(round(time_sec/60, 1)) + " min"
        elif time_sec == 3600:
            time_str = "1 hr"
        else:
            time_str = str(round(time_sec/3600, 1)) + " hrs"

        # xx.0 min/hr --> xx min/hr
        time_str = time_str.replace('.0 ', ' ')
        return time_str
#--------------------------------------------------------------------
    @staticmethod
    def _secs_to_minsec_str(time_sec):
        """ Create the time string from seconds """

        t_sec = int(time_sec)
        if t_sec < 60 and t_sec > 60:
            time_str = "{}s".format(t_sec)
        else:
            time_str = "{}m{}s".format(int(t_sec/60), (t_sec % 60))

        return time_str
#--------------------------------------------------------------------
    def _secs_since(self, e_seconds):
        return self.this_update_secs - e_seconds
#--------------------------------------------------------------------
    def _secs_to(self, e_seconds):
        return e_seconds - self.this_update_secs
#--------------------------------------------------------------------
    @staticmethod
    def _time_to_secs(hhmmss):
        """ Convert hh:mm:ss into seconds """
        if hhmmss:
            s = hhmmss.split(":")
            tts_seconds = int(s[0]) * 3600 + int(s[1]) * 60 + int(s[2])
        else:
            tts_seconds = 0

        return tts_seconds

#--------------------------------------------------------------------
    def _time_to_12hrtime(self, hhmmss, time_24h = False):
        if hhmmss == ZERO_HHMMSS:
            return

        if self.unit_of_measurement == 'mi' and time_24h is False:
            hhmmss_hms = hhmmss.split(':')
            hhmmss_hh  = int(hhmmss_hms[0])

            if hhmmss_hh > 12:
                hhmmss_hh -= 12
            elif hhmmss_hh == 0:
                hhmmss_hh = 12
            hhmmss = "{}:{}:{}".format(
                    hhmmss_hh, hhmmss_hms[1], hhmmss_hms[2])
        return hhmmss
#--------------------------------------------------------------------
    @staticmethod
    def _time_str_to_secs(time_str='30 min'):
        """
        Calculate the seconds in the time string.
        The time attribute is in the form of '15 sec' ',
        '2 min', '60 min', etc
        """

        s1 = str(time_str).replace('_', ' ') + " min"
        time_part = float((s1.split(" ")[0]))
        text_part = s1.split(" ")[1]

        if text_part == 'sec':
            time_sec = time_part
        elif text_part == 'min':
            time_sec = time_part * 60
        elif text_part == 'hrs':
            time_sec = time_part * 3600
        elif text_part in ('hr', 'hrs'):
            time_sec = time_part * 3600
        else:
            time_sec = 1200      #default to 20 minutes

        return time_sec

#--------------------------------------------------------------------
    def _timestamp_to_time_utcsecs(self, utc_timestamp):
        """
        Convert iCloud timeStamp into the local time zone and
        return hh:mm:ss
        """

        ts_local = int(float(utc_timestamp)/1000) + self.time_zone_offset_seconds

        ts_str = dt_util.utc_from_timestamp(
                ts_local).strftime(self.um_time_strfmt)
        if ts_str[0] == "0":
            ts_str = ts_str[1:]

        return ts_str

#--------------------------------------------------------------------
    def x_timestamp_age_secs(self, timestamp):
        """
        Return the age of the device timestamp attribute (sec)
        Format is --'timestamp': '2019-02-02T12:12:38.358-0500'
        """

        time_now_secs  = self.this_update_secs
        timestamp_secs = self._timestamp_to_secs(timestamp)
        if timestamp_secs == 0:
            return 0

        return (time_now_secs - timestamp_secs)
#--------------------------------------------------------------------
    def _timestamp_to_time(self, timestamp, time_24h = False):
        """
        Extract the time from the device timeStamp attribute
        updated by the IOS app.
        Format is --'timestamp': '2019-02-02T12:12:38.358-0500'
        Return as a 24hour time if time_24h = True
        """

        try:
            if timestamp == ISO_TIMESTAMP_ZERO:
                return ZERO_HHMMSS

            dev_time_yyyymmddhhmmss = '{}.'.format(timestamp.split('T')[1])
            dev_time_hhmmss = dev_time_yyyymmddhhmmss.split('.')[0]

            #if self.unit_of_measurement == 'mi' and time_24h is False:
            #    dev_time_hh = int(dev_time_hhmmss[0:2])
            #    if dev_time_hh > 12:
            #        dev_time_hh -= 12
            #    dev_time_hhmmss = "{}{}".format(
            #            dev_time_hh, dev_time_hhmmss[2:])

            return dev_time_hhmmss
        except:
            return ZERO_HHMMSS
#--------------------------------------------------------------------
    def _timestamp_to_secs_utc(self, utc_timestamp):
        """
        Convert timeStamp seconds (1567604461006) into the local time zone and
        return time in seconds.
        """

        ts_local = int(float(utc_timestamp)/1000) + self.time_zone_offset_seconds

        ts_str = dt_util.utc_from_timestamp(ts_local).strftime('%X')
        if ts_str[0] == "0":
            ts_str = ts_str[1:]

        t_sec = self._time_to_secs(ts_str)

        return t_sec

#--------------------------------------------------------------------
    def _timestamp_to_secs(self, timestamp, utc_local = LOCAL_TIME):
        """
        Convert the timestamp from the device timestamp attribute
        updated by the IOS app.
        Format is --'timestamp': '2019-02-02T12:12:38.358-0500'
        Return epoch seconds
        """
        try:
            if timestamp is None:
                return 0
            elif timestamp == '' or timestamp[0:19] == '0000-00-00T00:00:00':
                return 0

            tm = time.mktime(time.strptime(timestamp[0:19], "%Y-%m-%dT%H:%M:%S"))
            if utc_local is UTC_TIME:
                tm = tm + self.time_zone_offset_seconds

        except Exception as err:
            _LOGGER.error("Invalid timestamp format, timestamp = '%s'",
                timestamp)
            _LOGGER.exception(err)
            tm = 0

        return tm
#--------------------------------------------------------------------
    def _calculate_time_zone_offset(self):
        """
        Calculate time zone offset seconds
        """
        try:
            local_zone_offset = dt_util.now().strftime('%z')
            local_zone_offset_secs = int(local_zone_offset[1:3])*3600 + \
                        int(local_zone_offset[3:])*60
            if local_zone_offset[:1] == "-":
                local_zone_offset_secs = -1*local_zone_offset_secs

            e = int(time.time())
            l = time.localtime(e)
            ls= time.strftime('%H%M%S', l)
            g  =time.gmtime(e)
            gs=time.strftime('%H%M%S', g)
            t =dt_util.now().strftime('%H%M%S')

            if (ls == gs):
                self.e_seconds_local_offset_secs = local_zone_offset_secs

            log_msg = ("Time Zone Offset, Local Zone-{} hrs, {} secs").format(
                local_zone_offset,
                local_zone_offset_secs)
            self.log_debug_msg('*', log_msg)

        except Exception as err:
            _LOGGER.exception(err)
            x = self._internal_error_msg(fct_name, err, 'CalcTZOffset')
            local_zone_offset_secs = 0

        return local_zone_offset_secs

#--------------------------------------------------------------------
    def _km_to_mi(self, arg_distance):
        arg_distance = arg_distance * self.um_km_mi_factor

        if arg_distance == 0:
            return 0
        elif arg_distance <= 20:
            return round(arg_distance, 2)
        elif arg_distance <= 100:
            return round(arg_distance, 1)
        else:
            return round(arg_distance)

    def _mi_to_km(self, arg_distance):
       return round(float(arg_distance) / self.um_km_mi_factor, 2)

#--------------------------------------------------------------------
    @staticmethod
    def _calc_distance_km(from_lat, from_long, to_lat, to_long):
        if from_lat == None or from_long == None or to_lat == None or to_long == None:
            return 0

        d = distance(from_lat, from_long, to_lat, to_long) / 1000
        if d < .05:
            d = 0
        return round(d, 2)

    @staticmethod
    def _calc_distance_m(from_lat, from_long, to_lat, to_long):
        if from_lat == None or from_long == None or to_lat == None or to_long == None:
            return 0

        d = distance(from_lat, from_long, to_lat, to_long)

        return round(d, 2)

#--------------------------------------------------------------------
    @staticmethod
    def _round_to_zero(arg_distance):
        if abs(arg_distance) < .05:
            arg_distance = 0
        return round(arg_distance, 2)

#--------------------------------------------------------------------
    def _add_comma_to_str(self, text):
        """ Add a comma to info if it is not an empty string """
        if text:
            return '{}, '.format(text)
        return ''

#--------------------------------------------------------------------
    @staticmethod
    def _isnumber(string):

        try:
            test_number = float(string)

            return True
        except:
            return False

#--------------------------------------------------------------------
    @staticmethod
    def _inlist(string, list_items):

        for item in list_items:
            if string.find(item) >= 0:
                return True

        return False

    @staticmethod
    def _instr(string, find_string):
        return string.find(find_string) >= 0

#--------------------------------------------------------------------

    def _extract_name_device_type(self, devicename):
        '''Extract the name and device type from the devicename'''

        try:
            fname    = devicename.title()
            dev_type = ''

            for dev_type in APPLE_DEVICE_TYPES:
                if instr(devicename, dev_type):
                    fnamew = devicename.replace(dev_type, "", 99)
                    fname  = fnamew.replace("_", "", 99)
                    fname  = fname.replace("-", "", 99).title()
                    device_type  = dev_type
                    break

        except Exception as err:
            _LOGGER.exception(err)

        return (fname, dev_type)

#########################################################
#
#   These functions handle notification and entry of the
#   iCloud Account trusted device verification code.
#
#########################################################
    def icloud_need_trusted_device(self):
        """We need a trusted device."""
        configurator = self.hass.components.configurator
        if self.group in ICLOUD_ACCT_DEVICE_CONFIG:
            return

        devicesstring = ''
        if self.valid_trusted_device_ids == 'Invalid Entry':
            devicesstring = '\n\n'\
                '----------------------------------------------\n'\
                '●●● Previous Trusted Device Id Entry is Invalid ●●●\n\n\n' \
                '----------------------------------------------\n\n\n'
            self.valid_trusted_device_ids = None

        devices = self.api.trusted_devices
        device_list = "ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Phone Number\n" \
                      "––&nbsp;&nbsp;&nbsp;&nbsp;––––––––––––\n"
        for i, device in enumerate(devices):
            device_list += ("{}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                        "&nbsp;&nbsp;{}\n").format(
                        i, device.get('phoneNumber'))

            self.valid_trusted_device_ids = "{},{}".format(i,
                        self.valid_trusted_device_ids)

        description_msg = ("Enter the ID for the Trusted Device to receive "
            "the verification code via a text message.\n\n\n{}").format(
            device_list)

        ICLOUD_ACCT_DEVICE_CONFIG[self.group] = configurator.request_config(
            'iCloud Account Verification Required for {}-{}'.\
            format(self.username, self.group),
            self.icloud_trusted_device_callback,
            description    = (description_msg),
            entity_picture = "/static/images/config_icloud.png",
            submit_caption = 'Confirm',
            fields         = [{'id': 'trusted_device', \
                               CONF_NAME: 'Trusted Device ID'}]
        )

#--------------------------------------------------------------------
    def icloud_trusted_device_callback(self, callback_data):
        """
        Take the device number enterd above, get the api.device info and
        have pyiCloud validate the device.

        callbackData={'trusted_device': '1'}
        apiDevices=[{'deviceType': 'SMS', 'areaCode': '', 'phoneNumber':
                    '********65', 'deviceId': '1'},
                    {'deviceType': 'SMS', 'areaCode': '', 'phoneNumber':
                    '********66', 'deviceId': '2'}]
        """
        self.trusted_device_id = int(callback_data.get('trusted_device'))
        self.trusted_device    = \
                    self.api.trusted_devices[self.trusted_device_id]

        if self.group in ICLOUD_ACCT_DEVICE_CONFIG:
            request_id   = ICLOUD_ACCT_DEVICE_CONFIG.pop(self.group)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

        if str(self.trusted_device_id) not in self.valid_trusted_device_ids:
            event_msg = ("iCloud3 Error: Invalid Trusted Device ID. "
              "Entered={}, Valid IDs={}").format(
              self.trusted_device_id,
              self.valid_trusted_device_ids)
            self._save_event_halog_error(event_msg)

            self.trusted_device = None
            self.valid_trusted_device_ids = 'Invalid Entry'
            self.icloud_need_trusted_device()

        elif not self.api.send_verification_code(self.trusted_device):
            event_msg = ("iCloud3 Error: Failed to send verification code")
            self._save_event_halog_error(event_msg)

            self.trusted_device = None
            self.valid_trusted_device_ids = None

        else:
            # Get the verification code, Trigger the next step immediately

            self.icloud_need_verification_code()

#------------------------------------------------------
    def icloud_need_verification_code(self):
        """Return the verification code."""
        configurator = self.hass.components.configurator
        if self.group in ICLOUD_ACCT_DEVICE_CONFIG:
            return

        ICLOUD_ACCT_DEVICE_CONFIG[self.group] = configurator.request_config(
            'iCloud Account Verification Code for {}'.format(self.group),
            self.icloud_verification_callback,
            description    = ('Enter the Verification Code'),
            entity_picture = "/static/images/config_icloud.png",
            submit_caption = 'Confirm',
            fields         = [{'id': 'code', \
                               CONF_NAME: 'Verification Code'}]
        )

#--------------------------------------------------------------------
    def icloud_verification_callback(self, callback_data):
        """Handle the chosen trusted device."""
        from .pyicloud_ic3 import PyiCloudException
        self.verification_code = callback_data.get('code')

        try:
            if not self.api.validate_verification_code(
                    self.trusted_device, self.verification_code):
                raise PyiCloudException('Unknown failure')
        except PyiCloudException as error:
            # Reset to the initial 2FA state to allow the user to retry
            log_msg = ("iCloud3 Error: Failed to verify verification "
                "code: {}").format(error)
            self.log_error_msg(log_msg)

            self.trusted_device = None
            self.verification_code = None

            # Trigger the next step immediately
            self.icloud_need_trusted_device()

        if self.group in ICLOUD_ACCT_DEVICE_CONFIG:
            request_id   = ICLOUD_ACCT_DEVICE_CONFIG.pop(self.group)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

#--------------------------------------------------------------------
    def icloud_reauthorizing_account(self, restarting_flag = False):
        '''
        Make sure iCloud is still available and doesn't need to be reauthorized
        in 15-second polling loop

        Returns True  if Authentication is needed.
        Returns False if Authentication succeeded
        '''

        if self.CURRENT_TRK_METHOD_IOSAPP:
            return False
        elif self._start_icloud3_group_inprocess_flag:
            return False

        fct_name = "icloud_reauthorizing_account"

        from .pyicloud_ic3 import PyiCloudService
        from .pyicloud_ic3 import (
            PyiCloudFailedLoginException, PyiCloudNoDevicesException)

        try:
            if restarting_flag is False:
                if self.api is None:
                    event_msg = ("iCloud/FmF API Error, No device API information "
                                    "for devices. Resetting iCloud")
                    self._save_event_halog_error(event_msg)

                    self._start_icloud3()

                elif self._start_icloud3_group_request_flag:    #via service call
                    event_msg = ("iCloud Restarting, Reset command issued")
                    self._save_event_halog_error(event_msg)
                    self._start_icloud3()

                if self.api is None:
                    event_msg = ("iCloud reset failed, no device API information "
                                    "after reset")
                    self._save_event_halog_error(event_msg)

                    return True

            if self.api.requires_2sa:
                from .pyicloud_ic3 import PyiCloudException
                try:
                    if self.trusted_device is None:
                        self.icloud_need_trusted_device()
                        return True  #Authentication needed

                    if self.verification_code is None:
                        self.icloud_need_verification_code()

                        devicename = list(self.tracked_devices.keys())[0]
                        self._display_info_status_msg(devicename, '')
                        return True  #Authentication needed

                    self.api.authenticate()
                    self.authenticated_time = dt_util.now().strftime(self.um_date_time_strfmt)

                    event_msg = ("iCloud/FmF Authentication, Devices={}").format(
                        self.api.devices)
                    self._save_event_halog_info("*", event_msg)

                    if self.api.requires_2sa:
                        raise Exception('Unknown failure')

                    self.trusted_device    = None
                    self.verification_code = None

                except PyiCloudException as error:
                    event_msg = ("iCloud3 Error: Setting up 2FA: {}").format(error)
                    self._save_event_halog_error(event_msg)

                    return True  #Authentication needed, Authentication Failed

            return False         #Authentication not needed, (Authenticationed OK)

        except Exception as err:
            _LOGGER.exception(err)
            x = self._internal_error_msg(fct_name, err, 'AuthiCloud')
            return True

#########################################################
#
#   ICLOUD ROUTINES
#
#########################################################
    def service_handler_lost_iphone(self, group, arg_devicename):
        """Call the lost iPhone function if the device is found."""

        if self.CURRENT_TRK_METHOD_FAMSHR is False:
            log_msg = ("Lost Phone Alert Error: Alerts can only be sent "
                       "when using tracking_method FamShr")
            self.log_warning_msg(log_msg)
            self.info_notification = log_msg
            self._display_status_info_msg(arg_devicename, log_msg)
            return

        valid_devicename = self._service_multi_acct_devicename_check(
                "Lost iPhone Service", group, arg_devicename)
        if valid_devicename is False:
            return

        device = self.tracked_devices.get(arg_devicename)
        device.play_sound()

        log_msg = ("iCloud Lost iPhone Alert, Device {}").format(
                    arg_devicename)
        self.log_info_msg(log_msg)
        self._display_status_info_msg(arg_devicename, "Lost Phone Alert sent")

#--------------------------------------------------------------------
    def service_handler_icloud_update(self, group, arg_devicename=None,
                    arg_command=None):
        """
        Authenticate against iCloud and scan for devices.


        Commands:
        - waze reset range = reset the min-max rnge to defaults (1-1000)
        - waze toggle      = toggle waze on or off
        - pause            = stop polling for the devicename or all devices
        - resume           = resume polling devicename or all devices, reset
                             the interval override to normal interval
                             calculations
        - pause-resume     = same as above but toggles between pause and resume
        - zone xxxx        = updates the devie state to xxxx and updates all
                             of the iloud3 attributes. This does the see
                             service call and then an update.
        - reset            = reset everything and rescans all of the devices
        - debug interval   = displays the interval formula being used
        - debug gps        = simulates bad gps accuracy
        - debug old        = simulates that the location informaiton is old
        - info xxx         = the same as 'debug'
        - location         = request location update from ios app
        """

        #If several iCloud groups are used, this will be called for each
        #one. Exit if this instance of iCloud is not the one handling this
        #device. But if devicename = 'reset', it is an event_log service cmd.
        log_msg = ("iCloud3 Command Entered, Device: {}, ({}), "
            "Command: {}").format(
            arg_devicename,
            group,
            arg_command)
        self.log_debug_msg("*", log_msg)
        #self._save_event("*", log_msg)

        if arg_devicename:
            if (arg_devicename != 'restart'):
                valid_devicename = self._service_multi_acct_devicename_check(
                    "Update iCloud Service", group, arg_devicename)
                if valid_devicename is False:
                    return

        if instr(arg_command, 'event_log') == False:
            self._save_event(arg_devicename, "Service Call Command "
                "received ({})".format(arg_command))

        arg_command         = ("{} .").format(arg_command)
        arg_command_cmd     = arg_command.split(' ')[0].lower()
        arg_command_parm    = arg_command.split(' ')[1]       #original value
        arg_command_parmlow = arg_command_parm.lower()
        log_level_msg       = ""

        log_msg = ("iCloud3 Command Processed, Device: {} ({}), "
            "Command: {}").format(
            arg_devicename,
            group,
            arg_command)

        #System level commands
        if arg_command_cmd == 'restart':
            if self._start_icloud3_group_inprocess_flag is False:
                self._start_icloud3_group_request_flag = True
            self._save_event_halog_info("*", log_msg)
            return

        elif arg_command_cmd == 'refresh_event_log':
            self._update_event_log_sensor_line_items(arg_devicename)
            return
            '''
            Test code to send msg to the phone
            devicename = 'gary_iphone'
            if self.iosapp_version[devicename] == 1:
                entity_id = f"ios_{devicename}"
            else:
                entity_id = f"mobile_app_{devicename}"
            service_data = {
                "title": "iCloud3/iOSApp Zone Action Needed", 
                "message": "The iCloud3 Stationary Zone may not be loaded "\
                    "in the iOSApp. Force close the iOSApp from the iOS App "\
                    "Switcher. Then restart the iOSApp to reload the HA zones.",
                "data": {"subtitle": "Stationary Zone Exit Trigger was not received"}}
            self.hass.services.call("notify", entity_id, service_data)
            '''
            return
            
        elif arg_command_cmd == 'event_log':
            error_msg = ("Error > Then refresh the Event Log page in your browser. v2.1 "
                         "has [Refresh] [Debug] [Restart-ic3] at the top. "
                         "Also, swipe down in the iOS App to refresh it on your devices.")
            self._save_event("*", error_msg)
            error_msg = ("Error > Event Log v1.0 is being used. Clear your browser "
                         "cache or add `?v=2.1` to the ui-lovelace.yaml so it reads "
                         "`- url: .../icloud3-event-log-card.js?v=2.1`. ")
            self._save_event("*", error_msg)
            
            self._update_event_log_sensor_line_items(arg_devicename)
            return

        #command preprocessor, reformat specific commands
        elif instr(arg_command_cmd, 'log_level'):
            if instr(arg_command_parm, 'debug'):
                self.log_level_debug_flag = (not self.log_level_debug_flag)
                
            if instr(arg_command_parm, 'rawdata'):
                self.log_level_debug_rawdata_flag = (not self.log_level_debug_rawdata_flag)
                if self.log_level_debug_rawdata_flag: self.log_level_debug_flag = True
                            
            log_level_debug = "On" if self.log_level_debug_flag else "Off"
            log_msg += f"(Debug Log-{log_level_debug})"
            self._save_event_halog_info("*", log_msg)
            
            if instr(arg_command_parm, 'intervalcalc'):
                self.log_level_intervalcalc_flag = (not self.log_level_intervalcalc_flag)
                
            if instr(arg_command_parm, 'eventlog'):
                self.log_level_eventlog_flag = (not self.log_level_eventlog_flag)
                
                #log_level_debug = "On" if self.log_level_eventlog_flag else "Off"
                #log_msg += f"(iC3 Event Log/Debug Items-{log_level_debug})"
                #self._save_event_halog_info("*", log_msg)
            
            return 
            
        self._save_event_halog_info("*", log_msg)

        #Location level commands
        if arg_command_cmd == 'waze':
            if self.waze_status == WAZE_NOT_USED:
                arg_command_cmd = ''
                return
            elif arg_command_parmlow == 'reset_range':
                self.waze_min_distance = 0
                self.waze_max_distance = 99999
                self.waze_manual_pause_flag = False
                self.waze_status = WAZE_USED
            elif arg_command_parmlow == 'toggle':
                if self.waze_status == WAZE_PAUSED:
                    self.waze_manual_pause_flag = False
                    self.waze_status = WAZE_USED
                else:
                    self.waze_manual_pause_flag = True
                    self.waze_status = WAZE_PAUSED
            elif arg_command_parmlow == 'pause':
                self.waze_manual_pause_flag = False
                self.waze_status = WAZE_USED
            elif arg_command_parmlow != 'pause':
                self.waze_manual_pause_flag = True
                self.waze_status = WAZE_PAUSED

        elif arg_command_cmd == 'zone':     #parmeter is the new zone
            #if HOME in arg_command_parmlow:    #home/not_home is lower case
            if self.base_zone in arg_command_parmlow:    #home/not_home is lower case
                arg_command_parm = arg_command_parmlow

            kwargs = {}
            attrs  = {}

            self._wait_if_update_in_process(arg_devicename)
            self.overrideinterval_seconds[arg_devicename] = 0
            self.update_in_process_flag = False
            self._initialize_next_update_time(arg_devicename)

            self._update_device_icloud('Command', arg_devicename)

            return

        #Device level commands
        device_time_adj = 0
        for devicename in self.tracked_devices:
            if arg_devicename and devicename != arg_devicename:
                continue

            device_time_adj += 3
            devicename_zone = self._format_devicename_zone(devicename, HOME)

            now_secs_str = dt_util.now().strftime('%X')
            now_seconds  = self._time_to_secs(now_secs_str)
            x, update_in_secs = divmod(now_seconds, 15)
            update_in_secs = 15 - update_in_secs + device_time_adj

            attrs = {}

            #command processor, execute the entered command
            info_msg = None
            if arg_command_cmd == 'pause':
                cmd_type = CMD_PAUSE
                self.next_update_secs[devicename_zone] = 9999999999
                self.next_update_time[devicename_zone] = PAUSED
                self._display_info_status_msg(devicename, '● PAUSED ●')

            elif arg_command_cmd == 'resume':
                cmd_type = CMD_RESUME
                self.next_update_time[devicename_zone]    = ZERO_HHMMSS
                self.next_update_secs[devicename_zone]    = 0
                #self._initialize_next_update_time(devicename)
                self.overrideinterval_seconds[devicename] = 0
                self._display_info_status_msg(devicename, '● RESUMING ●')
                self._update_device_icloud('Resuming', devicename)

            elif arg_command_cmd == 'waze':
                cmd_type = CMD_WAZE
                if self.waze_status == WAZE_USED:
                    self.next_update_time[devicename_zone] = ZERO_HHMMSS
                    self.next_update_secs[devicename_zone] = 0
                    #self._initialize_next_update_time(devicename)
                    attrs[ATTR_NEXT_UPDATE_TIME]           = ZERO_HHMMSS
                    attrs[ATTR_WAZE_DISTANCE]              = 'Resuming'
                    self.overrideinterval_seconds[devicename] = 0
                    self._update_device_sensors(devicename, attrs)
                    attrs = {}

                    self._update_device_icloud('Resuming', devicename)
                else:
                    attrs[ATTR_WAZE_DISTANCE] = PAUSED
                    attrs[ATTR_WAZE_TIME]     = ''

            elif arg_command_cmd == 'location':
                self._request_iosapp_location_update(devicename)

            else:
                cmd_type = CMD_ERROR
                info_msg = '● INVALID COMMAND ({}) ●'.format(
                            arg_command_cmd)
                self._display_info_status_msg(devicename, info_msg)

            if attrs:
                self._update_device_sensors(devicename, attrs)

        #end for devicename in devs loop

#--------------------------------------------------------------------
    def service_handler_icloud_setinterval(self, group, arg_interval=None,
                    arg_devicename=None):

        """
        Set the interval or process the action command of the given devices.
            'interval' has the following options:
                - 15               = 15 minutes
                - 15 min           = 15 minutes
                - 15 sec           = 15 seconds
                - 5 hrs            = 5 hours
                - Pause            = Pause polling for all devices
                                     (or specific device if devicename
                                      is specified)
                - Resume            = Resume polling for all devices
                                     (or specific device if devicename
                                      is specified)
                - Waze              = Toggle Waze on/off
        """
        #If several iCloud groups are used, this will be called for each
        #one. Exit if this instance of iCloud is not the one handling this
        #device.

        if arg_devicename and self.CURRENT_TRK_METHOD_IOSAPP:
            if self.count_request_iosapp_update.get(arg_devicename) > self.max_iosapp_locate_cnt:
                event_msg = ("Can not Set Interval, location request cnt "
                    "exceeded ({} of {})").format(
                    self.count_request_iosapp_update.get(arg_devicename),
                    self.max_iosapp_locate_cnt)
                self._save_event(arg_devicename, event_msg)
                return

        elif arg_devicename:
            valid_devicename = self._service_multi_acct_devicename_check(
                "Update Interval Service", group, arg_devicename)
            if valid_devicename is False:
                return

        if arg_interval is None:
            if arg_devicename is not None:
                self._save_event(arg_devicename, "Set Interval Command Error, "
                        "no new interval specified")
            return

        cmd_type = CMD_INTERVAL
        new_interval = arg_interval.lower().replace('_', ' ')

#       loop through all devices being tracked and
#       update the attributes. Set various flags if pausing or resuming
#       that will be processed by the next poll in '_polling_loop_15_sec_icloud'
        device_time_adj = 0
        for devicename in self.tracked_devices:
            if arg_devicename and devicename != arg_devicename:
                continue

            device_time_adj += 3
            devicename_zone = self._format_devicename_zone(devicename, HOME)

            self._wait_if_update_in_process()

            log_msg = ("►SET INTERVAL COMMAND Start {}, "
                "ArgDevname={}, ArgInterval={}, "
                "New Interval: {}").format(
                devicename,
                arg_devicename,
                arg_interval,
                new_interval)
            self.log_debug_msg(devicename, log_msg)
            self._save_event(devicename, ("Set Interval Command handled, "
                "New interval {}").format(arg_interval))

            self.next_update_time[devicename_zone] = ZERO_HHMMSS
            self.next_update_secs[devicename_zone] = 0
            #self._initialize_next_update_time(devicename)
            self.interval_str[devicename_zone]        = new_interval
            self.overrideinterval_seconds[devicename] = self._time_str_to_secs(new_interval)

            now_seconds = self._time_to_secs(dt_util.now().strftime('%X'))
            x, update_in_secs = divmod(now_seconds, 15)
            time_suffix = 15 - update_in_secs + device_time_adj

            info_msg = '● Updating ●'
            self._display_info_status_msg(devicename, info_msg)

            log_msg = ("►SET INTERVAL COMMAND END {}").format(devicename)
            self.log_debug_msg(devicename, log_msg)
#--------------------------------------------------------------------
    def _service_multi_acct_devicename_check(self, svc_call_name,
            group, arg_devicename):

        if arg_devicename is None:
            log_msg = ("{} Error, no devicename specified").format(svc_call_name)
            self.log_error_msg(log_msg)
            return False

        info_msg = ("Checking {} for {}").format(svc_call_name, group)

        if (arg_devicename not in self.track_devicename_list):
            event_msg = ("{}, {} not in this group").format(info_msg, arg_devicename)
            #self._save_event(arg_devicename, event_msg)
            self.log_info_msg(event_msg)
            return False

        event_msg = ("{}-{} Processed").format(
            info_msg,
            arg_devicename)
        #self._save_event(arg_devicename, event_msg)
        self.log_info_msg(event_msg)
        return True
#--------------------------------------------------------------------
