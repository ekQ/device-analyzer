import re
from dateutil import parser
import datetime as dt
import time
import gzip
import sys
import random
import os
'''
Example usage: python analyze_single_device.py device_directory working_directory

Arguments:
    device_directory    A directory containing all files of a single device.
    working_directory   Where the output file will be saved.
'''

def analyze_single(data_directory, working_directory, debug=True):
    '''
    Go through the provided input files (twice) collecting installed apps and stats
    about their usage and write these to a randomly named file in the provided
    working directory.
    '''
    files = os.listdir(data_directory)
    # Sort the files numerically
    files = sorted(files, key=lambda item: int(item.partition('-')[0]))
    
    installed_apps = {} # Map app names to App objects
    t0 = 0
    t_first = None
    for file_name in files:
        f = gzip.open(data_directory+'/'+file_name,'r')
        # Read the file line by line
        for line in f:
            mo = re.match(r'^"\d+";"(\d+)";"(.+)";"([^"]*)";"1"',line)
            if mo:
                t_boot = int(mo.group(1))
                t = t0 + t_boot
                key = mo.group(2)
                value = mo.group(3)

                if key == 'time|bootup' and len(value) >= 23: # New boot time entry
                    # This ignores the timezone since handling it 
                    # correctly in python 2.X seems to be non-trivial
                    boot_date = parser.parse(value[:23]) 
                    t0 = time.mktime(boot_date.timetuple())*1000
                    if t_first is None:
                        # Store the first (presumably the smallest) boot time in the file
                        t_first = t0
                        if debug:
                            print "Set t_first to:", boot_date

                elif key == 'app|installed': # Extract app install times
                    apps_str = ',' + value
                    # Get the names and the install times of the installed apps
                    apps = re.findall(r',([^@]+)@\d+:[^:]+:(\d+):', apps_str)
                    for a in apps:
                        t_install = float(a[1])
                        t_install_str =  dt.datetime.utcfromtimestamp(t_install/1000.0)
                        if t_install > t_first and a[0] not in installed_apps:
                            new_app = App(a[0],t_install)
                            installed_apps[a[0]] = new_app
                            if debug:
                                print "Installed %s at"%a[0], t_install_str
            else:
                if debug:
                    print "Poorly formatted line:"
                    print line
        f.close()

    # Make a second pass collecting the app|pid|importance entries for the
    # recently installed apps
    prev_key = ''
    prev_value = ''
    t0 = t_first
    for file_name in files:
        f = gzip.open(data_directory+'/'+file_name,'r')
        # Read the file line by line
        for line in f:
            mo = re.match(r'^"\d+";"(\d+)";"(.+)";"([^"]*)";"1"',line)
            if mo:
                t_boot = int(mo.group(1))
                t = t0 + t_boot
                key = mo.group(2)
                value = mo.group(3)

                mo2 = re.match(r'app\|(\d+)\|name',key)

                if key == 'time|bootup' and len(value) >= 23: # New boot time entry
                    # This ignores the timezone
                    boot_date = parser.parse(value[:23]) 
                    t0 = time.mktime(boot_date.timetuple())*1000

                elif mo2 and value in installed_apps and re.match(r'app\|\d+\|importance',prev_key):
                    # Find the importance of the running process (it's usually
                    # on the previous line)
                    app_name = value
                    importance = prev_value
                    pid = mo2.group(1)
                    installed_apps[app_name].detected(t, importance, pid)
                prev_key = key
                prev_value = value
        f.close()

    # Create the output file with random name
    if not os.path.exists(working_directory):
        os.mkdir(working_directory)
    fout = open(working_directory+'/'+str(random.randint(0,sys.maxint))+'.txt','w')

    if debug:
        print "\nInstalled apps:"
    for app in installed_apps.itervalues():
        if debug:
            print "%d\t%d\t%d\t%d\t%d\t%s\t%s\t%f" % (app.n_foreground, app.n_background, app.n_uniq_ids, app.n_sessions, app.early_use, app.name, str(dt.datetime.fromtimestamp(app.t_install/1000.0)), app.get_first_use_lag())
        if not app.early_use:
            # Write the app usage stats to the output file
            print >>fout, "%s\t%d\t%d\t%d\t%d" % (app.name, app.n_foreground, app.n_background, app.n_uniq_ids, app.n_sessions)
    fout.close()

class App:
    '''
    App objects contain app usage information per single person.
    '''
    def __init__(self, name, t_install, t_max_days=7):
        self.name = name
        self.t_install = t_install
        self.t_max = t_max_days*24*60*60*1000
        self.n_foreground = 0
        self.n_background = 0
        self.uniq_ids = set()
        self.n_uniq_ids = 0
        self.n_sessions = 0
        self.prev_importance = ''
        self.t_first_use = 1e30
        self.early_use = False # Whether the app has been used before the reported install time
        # We set early_use to True only if the difference is above t_slack since 
        # there could be some discrepancy because of the timezone
        self.t_slack = 12*60*60*1000 # = 12 hours 

    def detected(self, t, importance, pid):
        if importance == 'foreground':
            self.fg_detected(t, pid)
        elif importance == 'background':
            self.bg_detected(t, pid)
        self.prev_importance = importance
        if t < self.t_first_use:
            self.t_first_use = t

    def fg_detected(self, t, pid):
        if t >= self.t_install - self.t_slack and t - self.t_install < self.t_max:
            self.n_foreground += 1
            if pid not in self.uniq_ids:
                self.n_uniq_ids += 1
                self.uniq_ids.add(pid)
            if self.prev_importance != 'foreground':
                self.n_sessions += 1
        elif t < self.t_install - self.t_slack:
            if self.early_use == False:
                print "App %s used %f hours before installation!" % (self.name, (self.t_install-t)/1000.0/60/60)
            self.early_use = True

    def bg_detected(self, t, pid):
        if t >= self.t_install - self.t_slack and t - self.t_install < self.t_max:
            self.n_background += 1
            if pid not in self.uniq_ids:
                self.n_uniq_ids += 1
                self.uniq_ids.add(pid)
        elif t < self.t_install - self.t_slack:
            if self.early_use == False:
                print "App %s used %f hours before installation!" % (self.name, (self.t_install-t)/1000.0/60/60)
            self.early_use = True

    def get_first_use_lag(self): # In minutes
        return (self.t_first_use - self.t_install) / 1000.0 / 60


def main():
    if len(sys.argv) == 3:
        analyze_single(sys.argv[1],sys.argv[2])
    else:
        print "Error: You must provide two arguments, the name of the directory containing the device data, and the name of a working directory. For example:"
        print "python analyze_single_device.py device_directory working_directory"

if __name__ == '__main__':
    main()
