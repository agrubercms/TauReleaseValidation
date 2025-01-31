import re
import os
import subprocess

import eostools

globaldebug = False

#FIXME: This needs some fixing for phase 2 samples with 14 TeV in their name
from sample_mapping import runtype_to_sample


def addArguments(parser, produce=True, compare=False):
    parser.add_argument('--runtype', choices=['Data', 'DataTau', 'DataMu', 'DataEl', 'DYToLL', 'ZTT', 'ZEE', 'ZMM', 'ZpMM', 'QCD', 'TTbar', 'TTbarTau', 'ZpTT', 'TenTaus'], help='choose sample type')
    parser.add_argument('-i', '--inputfiles', default=[], nargs='*', help="List of files locations [Default: %(default)s]")

    # useful for debugging
    parser.add_argument('-n', '--maxEvents', default=-1, type=int, help='Number of events that will be analyzed (-1 = all events) [Default: %(default)s]')
    parser.add_argument('--debug', default=False, help="Debug option [Default: %(default)s]", action="store_true")
    parser.add_argument('--dryRun', default=False, action="store_true",  help='Dry run - no plots [Default: %(default)s]')
    parser.add_argument('--skip', default=False, action="store_true",  help='skip production of root files and make plots directly')
    parser.add_argument('--manual_query', default="",  help='enter manual DAS file query, only allowed together with --s das')

    if produce:
        parser.add_argument('--release', default="CMSSW_9_4_0_pre1", help='Release')
        parser.add_argument('--globalTag', default='', help='Global tag [Default: %(default)s]') # e.g. 93X_mc2017_realistic_v3-v1
        parser.add_argument('-o', '--outputFileName', default='', help="Output file name [Default: %(default)s]")
        parser.add_argument('-s', '--storageSite', default='eos', choices=['eos', 'das', 'loc'], help="Choose between samples store on eos or DAS or in private local folder [Default: %(default)s]")
        parser.add_argument('-l', '--localdir', default='/eos/user/o/ohlushch/relValMVA/', help="Local dir where the samples are looked up [Default: %(default)s]")#
        parser.add_argument('-m', '--mvaid', default=[], nargs='*',
            help="Select mvaids that should be obtained via rerunning TAUId sequence: [2017v1, 2017v2, newDM2017v2, dR0p32017v2, 2016v1, newDM2016v1]. [Default: %(default)s]")
        parser.add_argument('-t', '--tauCollection', default='slimmedTaus', help="Tau collection to be used. Possible: NewTauIDsEmbedded; [Default: %(default)s].")
        parser.add_argument('-u', '--useRecoJets', default=False, action="store_true", help='Use RecoJets [Default: %(default)s]')
        parser.add_argument('--noAntiLepton', default=False, action='store_true', help='Do not access anti-lepton discriminators, e.g. if you use the tau reconstruction on top of MiniAOD that does not calculate them')
        parser.add_argument('--exact', default='', help='Provide exact DAS query (of the form "/Sample.../GT.../MINIAODSIM")')

    if compare:
        parser.add_argument('-p', '--part', default=0, type=int, help='Make WP plots(1), fraction of histogram plots(2..totalparts), \
            , or everything at once(0) (This part needs to be split up to avoid a crash that happens for some reason)')
        parser.add_argument('--totalparts', default=7, type=int, help='How many parts the compare step should be split into. \
            Increase this value if root crashes occur.')
        parser.add_argument('-b', '--onebin', default=False, action="store_true", help='Plot inclusive efficiencies by only using one bin')
        parser.add_argument('--releases', default=[], nargs='*', help='List of releases') # e.g. ["CMSSW_9_4_0_pre1", "CMSSW_9_4_0_pre2"]
        parser.add_argument('--globalTags', default=[], nargs='*', help='List of global tags [Default: %(default)s]') # e.g. ['93X_mc2017_realistic_v3-v1', 'PU25ns_94X_mc2017_realistic_v1-v1']

        parser.add_argument('-v', '--variables', default=[], nargs='*', help='Variables to place on a single plot (if only one release+GT)')
        parser.add_argument('-c', '--colors', default=[1, 4], nargs='*', help='Colors of variables to place on a single plot (if only one release+GT)')
        parser.add_argument('--varyLooseId', default=False, action="store_true", help='If the loose Id should be varied')
        parser.add_argument('--setLooseId', default='tau_byLooseIsolationMVArun2v1DBoldDMwLT', help='LooseId to be considered')


def dprint(*text):
    if globaldebug and text is not None:
        for t in text:
            print (t,)
        print
        # print " ".join(map(str, text))


def dpprint(*text):
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    if globaldebug and text is not None:
        for t in text:
            pp.pprint(t)
        # pp.pprint(" \n".join(map(str, text)))


def getFilesFromEOS(path, cmseospath=True):
    '''Give path in form /store/relval/CMSSW_9_4_0_pre2/...'''
    if path[-1] == "/":
        path = path[:-1]
    dirs = eostools.listFiles(cmseospath * '/eos/cms' + path)
    print ("getFilesFromEOS::path:", path)
    print ("getFilesFromEOS::dirs: ", dirs)

    files = []
    for sub_path in dirs:
        print ("\tsub_path:", sub_path)
        files += [cmseospath * 'root://eoscms.cern.ch/' + x for x in eostools.listFiles(sub_path) if re.match('.*root', x)]

    print ("files:", files)
    return files


def getFilesFromDAS(release, runtype, globalTag, miniaod, manual_query="", exact=""):
    '''Get proxy with "voms-proxy-init -voms cms" to use this option.'''
    if manual_query:
        query=manual_query
    else:
        query = "file dataset=/{0}/{1}-{2}/{3}".format(runtype, release, globalTag, miniaod)
    if exact != "": query = "file dataset={0}".format(exact)
    # Examples/Hardcoding:
    #query = "file dataset=/TauGun_Pt-15to500_14TeV-pythia8/Run3Summer19MiniAOD-2023Scenario_106X_mcRun3_2023_realistic_v3-v2/MINIAODSIM"
    #query = "file dataset=/TTToSemiLeptonic_TuneCP5_14TeV-powheg-pythia8/Run3Summer19MiniAOD-2023Scenario_106X_mcRun3_2023_realistic_v3-v2/MINIAODSIM"
    print ("Getting files from DAS. query:", query)
    result = subprocess.check_output("dasgoclient --query='" + query + "'", shell=True).decode("utf-8")
    if not result:
        query = "file dataset=/*{0}*/*{1}-{2}*/{3}".format(runtype, release, globalTag, miniaod) # TODO: Doesn't work! Finds dataset, but not files for all datasets
        print ("First attempt unsuccessful. Generalizing query. May take a while.... query:", query)
        result = subprocess.check_output("dasgoclient --query='" + query + "'", shell=True).decode("utf-8")

    files = ["root://cms-xrd-global.cern.ch/" + s.strip() for s in result.splitlines()]
    #files = ["root://cms-xrd-global.cern.ch/" + s.strip() for s in result.splitlines()]

    print ("files:", files)
    return files

def getNeventsFromDAS(release, runtype, globalTag, miniaod, exact=""):
    '''Get proxy with "voms-proxy-init -voms cms" to use this option.'''
    query = "dataset=/{0}/{1}-{2}/{3}".format(runtype, release, globalTag, miniaod)
    if exact != "": query = "dataset={0}".format(exact)
    result = subprocess.check_output("dasgoclient --query='" + query + "' -json", shell=True).decode("utf-8")
    if '[\n]' in result:
        query = "dataset=/*{0}*/*{1}-{2}*/{3}".format(runtype, release, globalTag, miniaod)
        result = subprocess.check_output("dasgoclient --query='" + query + "' -json", shell=True).decode("utf-8")
    try:
      nevents=int(result[result.find("nevent")+9:result.find("nfiles")-2])
      return nevents
    except ValueError:
      return -1


def get_cmssw_version():
    """returns 'CMSSW_X_Y_Z'"""
    return os.environ["CMSSW_RELEASE_BASE"].split('/')[-1]


def get_cmssw_version_number():
    """returns 'X_Y_Z' (without 'CMSSW_')"""
    return map(int, get_cmssw_version().split("CMSSW_")[1].split("_")[0:3])


def versionToInt(release=9, subversion=4, patch=0):
    return release * 10000 + subversion * 100 + patch


def is_above_cmssw_version(release=9, subversion=4, patch=0):
    split_cmssw_version = list(get_cmssw_version_number())
    if versionToInt(release, subversion, patch) > versionToInt(split_cmssw_version[0], split_cmssw_version[1], split_cmssw_version[2]):
        return False
    return True
