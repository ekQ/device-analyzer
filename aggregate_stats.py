import os
import numpy as np
import sys
'''
Example usage: python aggregate_stats.py working_directory output.txt
'''

def aggregate_stats(working_directory, output_file):
    '''
    Aggregate app features from all the files in the provided working directory
    and write them to the provided output file.
    '''
    files = os.listdir(working_directory)
    n = len(files)
    apps = {}
    for fname in files:
        f = open(working_directory+'/'+fname,'r')
        for line in f:
            vals = line.split('\t')
            if len(vals) != 5:
                n -= 1
                continue
            name = vals[0]
            if name in apps:
                app = apps[name]
            else:
                app = AppStats(name)
                apps[name] = app
            app.fg.append(vals[1])
            app.bg.append(vals[2])
            app.uniq.append(vals[3])
            app.session.append(vals[4])
        f.close()
    fout_name = working_directory + '/' + output_file
    fout = open(fout_name,'w')
    for stat in apps.itervalues():
        print >>fout, stat.aggregate()
    fout.close()
    print "Successfully wrote output to file:", fout_name

class AppStats:
    '''
    AppStats objects contain app usage information for all users.
    '''
    def __init__(self,name):
        self.name = name # App name
        self.fg = []
        self.bg = []
        self.uniq = []
        self.session = []

    def aggregate(self):
        '''
        Create an output line consisting of 15 tab-separated values for
        a single app.
        '''
        fg = np.array(self.fg,dtype=float)
        bg = np.array(self.bg,dtype=int)
        uniq = np.array(self.uniq,dtype=int)
        ses = np.array(self.session,dtype=int)

        n = len(self.fg)
        ret = "%s\t%d\t" % (self.name,n)
        ret += str(np.mean(fg))+'\t'
        ret += str(np.median(fg))+'\t'
        ret += str(np.sum(fg>1))+'\t'

        ret += str(np.mean(bg))+'\t'
        ret += str(np.median(bg))+'\t'
        ret += str(np.sum(bg>1))+'\t'

        ret += str(np.mean(uniq))+'\t'
        ret += str(np.median(uniq))+'\t'
        ret += str(np.sum(uniq>1))+'\t'

        ret += str(np.mean(ses))+'\t'
        ret += str(np.median(ses))+'\t'
        ret += str(np.sum(ses>1))+'\t'

        bg_nz = bg
        bg_nz[bg==0] = 1
        ret += str(np.mean(1.0*fg/bg_nz))+'\t'

        return ret

def main():
    if len(sys.argv) == 3:
        aggregate_stats(sys.argv[1],sys.argv[2])
    else:
        print "Error: You must provide two arguments, the working directory and the name of the output file. For example:"
        print "python aggregate_stats.py working_directory output.txt"

if __name__ == '__main__':
    main()
