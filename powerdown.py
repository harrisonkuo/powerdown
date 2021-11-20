#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import subprocess

INTEL_POWERCAP = '/sys/class/powercap/'
INTEL_RAPL = 'intel-rapl'
INTEL_RAPL_ZONE_PREFIX = f'{INTEL_RAPL}:'
INTEL_RAPL_PATH = os.path.join(INTEL_POWERCAP, INTEL_RAPL)
POWERCAP_SET = 'powercap-set'

PL1_NAME = 'long_term'
PL2_NAME = 'short_term'
PL4_NAME = 'peak_power'
NAME = 'name'
POWER_LIMIT_UW = 'power_limit_uw'
TIME_WINDOW_US = 'time_window_us'
MAX_POWER_UW = 'max_power_uw'

ENABLED = 'enabled'
CONSTRAINT = 'constraint'

MICRO = 1000000


class Utils(object):
    """
    Utilty functions
    """

    def get_value(path):
        """
        Gets a value of arbitrary type depending on the path given.
        :param path: a string representing a path to a single line file
        :return: a value of arbitrary type
        """
        if os.path.exists(path):
            with open(path) as f:
                value = f.readline().strip()
                f.close()
                return value

    def set_rapl_value(zone_id, enabled=None, constraint_id=None, power_limit_uw=None, time_window_us=None, 
                       reset_energy=None):
        """
        Sets Intel RAPL values using powercap-set from powercap-utils
        :param zone_id: a string of an id representing a zone (examples include 0, 0:0, 0:1)
        :param enabled: a boolean representing if the zone is enabled
        :param constraint_id: a string representing the constraint_id
        :param power_limit_uw: a number representing the power limit for the zone in microwatts
        :param time_window_uw: a number representing the time window for the zone in microseconds
        :param reset_energy: a boolean representing if the energy counter for the zone is to be reset
        """
        cmd = [POWERCAP_SET, '-p', INTEL_RAPL, '-z', zone_id]

        if constraint_id:
            cmd.extend(['-c', constraint_id])
            if power_limit_uw:
                cmd.extend(['-l', str(int(power_limit_uw))])
            if time_window_us:
                cmd.extend(['-s', str(int(time_window_us))])

        if enabled:
            cmd.extend(['-e', str(int(enabled))])

        if reset_energy:
            cmd.append('-j')

        subprocess.run(cmd)
        

class RAPLController(object):
    """
    Intel RAPL non-MMIO controller
    """
    
    def __init__(self):
        """
        Initializes the RAPL controller by enumerating zones available to Intel-RAPL
        """
        self.zones = [RAPLZone(zone_name.strip(INTEL_RAPL_ZONE_PREFIX)) for zone_name in os.listdir(INTEL_RAPL_PATH) 
                      if INTEL_RAPL_ZONE_PREFIX in zone_name]

    @property
    def enabled(self):
        """
        Checks if Intel RAPL is enabled
        :return: a boolean if Intel RAPL is enabled
        """
        enabled_str = Utils.get_value(os.path.join(self.path, ENABLED))
        if enabled_str:
            return bool(int(enabled_str))


class RAPLZone(object):
    """
    Intel RAPL zone
    """

    def __init__(self, zone_id, parent_zone=None):
        """
        Initializes the RAPL zone by enumerating subzones and constraints available
        :param zone_id: a string representing the zone id
        :param parent_zone: a RAPLZone that is the parent of this zone, defaults to None
        """
        self.zone_id = zone_id
        self.parent_zone = parent_zone
        self.subzones = [RAPLZone(zone_name.strip(INTEL_RAPL_ZONE_PREFIX), parent_zone=self) for zone_name 
                         in os.listdir(self.path) if INTEL_RAPL_ZONE_PREFIX in zone_name]
        constraint_ids = list(set([constraint_attribute.split('_')[1] for
                                   constraint_attribute in os.listdir(self.path) 
                                   if CONSTRAINT in constraint_attribute]))
        self._constraints = {}

        for constraint_id in constraint_ids:
            constraint = RAPLConstraint(constraint_id, self)
            self._constraints[constraint.name] = constraint

    def __str__(self):
        return self.name

    @property
    def path(self):
        """
        Returns the full absolute path of the zone
        :return: a string representing the absolute path of the zone
        """
        parent_zone_path = ''
        if self.parent_zone:
            parent_zone_path = self.parent_zone.path
        return os.path.join(INTEL_RAPL_PATH, parent_zone_path, f'{INTEL_RAPL_ZONE_PREFIX}{self.zone_id}')

    @property
    def name(self):
        """
        Gets the name of the zone
        :return: a string representing the name of the zone
        """
        return Utils.get_value(os.path.join(self.path, NAME))

    @property
    def enabled(self):
        """
        Gets if the zone is enabled
        :return: a boolean representing if the zone is enabled or not
        """
        enabled_str = Utils.get_value(os.path.join(self.path, ENABLED))
        if enabled_str:
            return bool(int(enabled_str))

    @enabled.setter
    def enabled(self, enabled):
        """
        Sets the name of the zone
        :param enabled: a boolean representing if the zone will be enabled or not
        """
        Utils.set_rapl_value(self.zone_id, enabled=enabled)

    @property
    def constraints(self):
        """
        Gets a sorted list of constraints by constraint ids
        :param enabled: a sorted list of constraints by constraint ids
        """
        return sorted(self._constraints.values(), key=lambda constraint: constraint.constraint_id)

    @property
    def PL1(self):
        """
        Gets the PL1 constraint, long term nominal power
        :return: RAPLConstraint representing PL1
        """
        if PL1_NAME in self._constraints:
            return self._constraints[PL1_NAME]

    @property
    def PL2(self):
        """
        Gets the PL2 constraint, short term "burst" power
        :return: RAPLConstraint representing PL2
        """
        if PL2_NAME in self._constraints:
            return self._constraints[PL2_NAME]

    @property
    def PL4(self):
        """
        Gets the PL4 constraint, instantaneous "peak" power
        :return: RAPLConstraint representing PL4
        """
        if PL4_NAME in self._constraints:
            return self._constraints[PL4_NAME]


class RAPLConstraint(object):

    def __init__(self, constraint_id, zone):
        """
        Intel RAPL constraint of a zone
        """
        self.zone = zone
        self.constraint_id = constraint_id

    def constraint_attribute_path(self, attribute_name):
        """
        Gets the path to the constraint of a provided attribute
        :param attribute_name: the string representing the attribute name
        :return: a string representing the absolute path to the attribute name
        """
        return os.path.join(self.zone.path, f'constraint_{self.constraint_id}_{attribute_name}')

    def __str__(self):
        return self.name

    @property
    def name(self):
        """
        Gets the name of the constraint
        :return: a string representing the name of the constraint
        """
        return Utils.get_value(os.path.join(self.constraint_attribute_path(NAME)))

    @property
    def power_limit_uw(self):
        """
        Gets the power limit in microwatts of the constraint
        :return: an integer representing the power limit in microwatts
        """
        return int(Utils.get_value(os.path.join(self.constraint_attribute_path(POWER_LIMIT_UW))))

    @power_limit_uw.setter
    def power_limit_uw(self, power_uw):
        """
        Sets the power limit in microwatts of the constraint
        :param power_uw: a number representing the power limit in microwatts
        """
        Utils.set_rapl_value(self.zone.zone_id, constraint_id=self.constraint_id, 
                             power_limit_uw=int(power_uw))

    @property
    def time_window_us(self):
        """
        Gets the time window in microseconds of the constraint
        :return: an integer representing the power limit in microseconds
        """
        return int(Utils.get_value(os.path.join(self.constraint_attribute_path(TIME_WINDOW_US))))

    @time_window_us.setter
    def time_window_us(self, time_window_us):
        """
        Sets the time window in microseconds of the constraint
        :param time_window_us: a number representing the time window in microseconds
        """
        Utils.set_rapl_value(self.zone_id, constraint_id=self.constraint_id, 
                             time_window_us=int(time_window_us))

    @property
    def max_power_uw(self):
        """
        Gets the max power in microwatts of the constraint
        :return: an integer representing the max power in microwatts
        """
        return int(Utils.get_value(os.path.join(self.constraint_attribute_path(MAX_POWER_UW))))

    @property
    def max_power(self):
        """
        Gets the max power in watts of the constraint
        :return: a number representing the max power in watts
        """
        return self.max_power_uw / MICRO

    @property
    def power_limit(self):
        """
        Gets the power limit in watts of the constraint
        :return: a number representing the power limit in watts
        """
        return self.power_limit_uw / MICRO

    @power_limit.setter
    def power_limit(self, power_w):
        """
        Sets the power limit in watts of the constraint
        :param power_w: a number representing the power limit in watts
        """
        self.power_limit_uw = power_w * MICRO

    @property
    def time_window(self):
        """
        Gets the time window in seconds of the constraint
        :return: a number representing the time window in seconds
        """
        return self.time_window_us / MICRO

    @time_window.setter
    def time_window(self, time_window_s):
        """
        Sets the time window in seconds of the constraint
        :param time_window_s: a number representing the time window in seconds
        """
        self.time_window_us = time_window_s * MICRO

