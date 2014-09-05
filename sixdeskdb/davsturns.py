# DA vs turns module
import os as os
import sys as sys
import numpy as np
import matplotlib.pyplot as pl
import glob as glob
from SixdeskDB import SixDeskDB,tune_dir

# basic functions
def ang_to_i(ang,angmax):
  """converts angle [degrees] to index (sixtrack)"""
  return int(ang/(90./(angmax+1))-1)

# functions necessary for the analysis
def get_min_turn_ang(s,t,a,it):
  """returns array with (angle,minimum sigma,sturn) of particles with lost turn number < it.

  check if there is a particle with angle ang with lost turn number <it
  if true: lost turn number and amplitude of the last stable particle is saved = particle "before" the particle with the smallest amplitude with nturns<it
  if false: the smallest lost turn number and the largest amplitude is saved 
  """
  angmax=len(a[:,0])#number of angles
  ftype=[('angle',float),('sigma',float),('sturn',float)]
  mta=np.ndarray(angmax,dtype=ftype)
  #initialize to 0
  for i in range(len(mta)):
    mta[i]=(0,0,0)
  for ang in set(a[:,0]):
  #save in mta
    tang=t[a==ang]
    sang=s[a==ang]
    if(any(tang[tang<it])):
      sangit=np.amin(sang[tang<it])
      argminit=np.amin(np.where(sang==sangit)[0])#get index of smallest amplitude with sturn<it - amplitudes are ordered ascending
#      print(argminit)
      mta[ang_to_i(ang,angmax)]=(ang,sang[argminit-1],tang[argminit-1])#last stable amplitude -> index argminit-1
    else: 
      mta[ang_to_i(ang,angmax)]=(ang,np.amax(sang),np.amin(tang))
  return mta
def get_da_vs_turns(seed,tune,data,turnstep):
  """returns DAout with DAwtrap,DAstrap,DAwsimp,DAssimp,DAstraperr,DAstraperrang,DAstraperramp,nturn,tlossmin.
  DAs:       simple average over radius 
             DAs = 2/pi*int_0^(2pi)[r(theta)]dtheta=<r(theta)>
                 = 2/pi*dtheta*sum(r(theta_i))
  DAw:       weighted average
             DAw = (int_0^(2pi)[(r(theta))^4*sin(2*theta)]dtheta)^1/4
                 = (dtheta*sum(r(theta_i)^4*sin(2*theta_i)))^1/4
  trapezoidal and simpson rule: numerical recipes open formulas 4.1.15 and 4.1.18        
  """
  mtime=0.0
  (tunex,tuney)=tune
  s,a,t=data['sigma'],data['angle'],data['sturn']
  tmax=np.max(t[s>0])#maximum number of turns
#  print tmax
  #set the 0 in t to tmax*100 in order to check if turnnumber<it (any(tang[tang<it])<it in get_min_turn_ang)
  t[s==0]=tmax*100
  angmax=len(a[:,0])#number of angles
  angstep=np.pi/(2*(angmax+1))#step in angle in rad
  ampstep=np.abs((s[s>0][1])-(s[s>0][0]))
  ftype=[('seed',int),('tunex',float),('tuney',float),('DAwtrap',float),('DAstrap',float),('DAwsimp',float),('DAssimp',float),('DAstraperr',float),('DAstraperrang',float),('DAstraperramp',float),('nturn',float),('tlossmin',float),('mtime',float)]
  DAout=np.ndarray(len(np.arange(turnstep,tmax,turnstep)),dtype=ftype)
  for nm in DAout.dtype.names:
    DAout[nm]=np.zeros(len(DAout[nm]))
  dacount=0
  currentDAwtrap=0
  currenttlossmin=0
  for it in np.arange(turnstep,tmax,turnstep):
    mta=get_min_turn_ang(s,t,a,it)
    mta['angle']=mta['angle']*np.pi/180#convert to rad
    if(len(mta['angle'])>2):
      ajtrap=(np.append(np.append(np.array([3/2.]),np.ones(len(mta['angle'])-2)),np.array([3/2.])))#define coefficients for simpson rule
    else:
      print('Error in get_da_vs_turns: You need at least 3 angles to calculate the DA vs turns!')
      sys.exit(0)
    if(len(mta['angle'])>6):
      ajsimp=(np.append(np.append(np.array([55/24.,-1/6.,11/8.]),np.ones(len(mta['angle'])-6)),np.array([11/8.,-1/6.,55/24.])))#define coefficients for simpson rule
      calcsimp=True
    else:
      print('Error in get_da_vs_turns: You need at least 7 angles to calculate the DA vs turns with the simpson rule! DA*simp* will be set to 0.') 
      calcsimp=False
    # integral trapezoidal rule
    #MF: should add factor 3/2 for first and last angle
    DAwtrap=(np.sum(mta['sigma']**4*np.sin(2*mta['angle']))*angstep)**(1/4.)
    DAstrap=(2./np.pi)*np.sum(mta['sigma'])*angstep
    # error trapezoidal rule
    DAstraperrang=np.sum(np.abs(np.diff(mta['sigma'])))/(2*angmax)
    DAstraperramp=ampstep/2
    DAstraperr=np.sqrt(DAstraperrang**2+DAstraperramp**2)
    if(calcsimp):
      # integral simpson rule
      DAwsimpint = np.sum(ajsimp*((mta['sigma']**4)*np.sin(2*mta['angle'])))*angstep
      DAssimpint = np.sum(ajsimp*mta['sigma'])*angstep
      DAwsimp    = (DAwsimpint)**(1/4.)
      DAssimp    = (2./np.pi)*DAssimpint
      # error simpson rule
    else:
      (DAwsimp,DAssimp)=np.zeros(2)
    tlossmin=np.min(mta['sturn'])
    if(DAwtrap!=currentDAwtrap and it-turnstep > 0 and tlossmin!=currenttlossmin):
      DAout[dacount]=(seed,tunex,tuney,DAwtrap,DAstrap,DAwsimp,DAssimp,DAstraperr,DAstraperrang,DAstraperramp,it-turnstep,tlossmin,mtime)
      dacount=dacount+1
    currentDAwtrap     =DAwtrap
    currenttlossmin=tlossmin
  return DAout[DAout['DAwtrap']>0]#delete 0 from errors

# functions to reload and create DA.out files for previous scripts
def save_daout(data,path):
  DAoutold=data[['DAwtrap','DAstrap','DAstraperr','DAstraperrang','DAstraperramp','nturn','tlossmin']]
  np.savetxt(path+'/DA.out',DAoutold,fmt='%.6f %.6f %.6f %.6f %.6f %d %d')
def reload_daout(path):
  ftype=[('DAwtrap',float),('DAstrap',float),('DAstraperr',float),('DAstraperrang',float),('DAstraperramp',float),('nturn',float),('tlossmin',float)]
  return np.loadtxt(glob.glob(path+'/DA.out*')[0],dtype=ftype,delimiter=' ')
def save_dasurv(data,path):
  np.savetxt(path+'/DAsurv.out',np.reshape(data,-1),fmt='%.8f %.8f %d')
def reload_dasurv(path):
  ftype=[('angle', '<f8'), ('sigma', '<f8'), ('sturn', '<f8')]
  data=np.loadtxt(glob.glob(path+'/DAsurv.out*')[0],dtype=ftype,delimiter=' ')
  angles=len(set(data['angle']))
  return data.reshape(angles,-1)

def plot_da_vs_turns(data,seed,ampmin=2,ampmax=14,tmax=1.e6,slog=False):
  """dynamic aperture vs number of turns, blue=simple average, red=weighted average"""
  pl.close('all')
  pl.figure(figsize=(6,6))
  pl.errorbar(data['DAstrap'],data['tlossmin'],xerr=data['DAstraperr'],fmt='bo',markersize=2,label='simple average')
  pl.plot(data['DAwtrap'],data['tlossmin'],'ro',markersize=3,label='weighted average')
  pl.title('seed '+seed)
  pl.xlim([ampmin,ampmax])
  pl.xlabel(r'Dynamic aperture [$\sigma$]',labelpad=10,fontsize=12)
  pl.ylabel(r'Number of turns',labelpad=15,fontsize=12)
  plleg=pl.gca().legend(loc='best')
  for label in plleg.get_texts():
      label.set_fontsize(12)
  if(slog):
    pl.ylim([5.e3,tmax])
    pl.yscale('log')
  else:
    pl.ylim([0,tmax])
    pl.gca().ticklabel_format(style='sci', axis='y', scilimits=(0,0))
def plot_da_vs_turns_comp(data,lbldata,datacomp,lbldatacomp,seed,ampmin=2,ampmax=14,tmax=1.e6,slog=False):
  """dynamic aperture vs number of turns, blue/green=simple average, red/orange=weighted average"""
  pl.close('all')
  pl.figure(figsize=(6,6))
  pl.errorbar(data['DAstrap'],data['tlossmin'],xerr=data['DAstraperr'],fmt='bo',markersize=2,label='simple average '+lbldata)
  pl.plot(data['DAwtrap'],data['tlossmin'],'ro',markersize=3,label='weighted average '+lbldata)
  pl.errorbar(datacomp['DAstrap'],datacomp['tlossmin'],xerr=datacomp['DAstraperr'],fmt='go',markersize=2,label='simple average '+lbldatacomp)
  pl.plot(datacomp['DAwtrap'],datacomp['tlossmin'],'o',color='orange',markersize=3,label='weighted average '+lbldatacomp)
  pl.title('seed '+seed)
  pl.xlim([ampmin,ampmax])
  pl.xlabel(r'Dynamic aperture [$\sigma$]',labelpad=10,fontsize=12)
  pl.ylabel(r'Number of turns',labelpad=15,fontsize=12)
  plleg=pl.gca().legend(loc='best')
  for label in plleg.get_texts():
    label.set_fontsize(12)
  if(slog):
    pl.ylim([5.e3,tmax])
    pl.yscale('log')
  else:
    pl.ylim([0,tmax])
    pl.gca().ticklabel_format(style='sci',axis='y',scilimits=(0,0))

# main analysis - putting the pieces together
def RunDaVsTurns(db,force,outfile,turnstep,tmax,ampmaxsurv,ampmindavst,ampmaxdavst,plotlog):
  '''Da vs turns analysis for study dbname'''
# create directory structure and delete old files if force=true
  count=0
  for seed in db.get_db_seeds():
    for tune in db.get_tunes():
      if(force):
        # create directory
        pp=db.mk_analysis_dir(seed,tune)
    #delete old plots and files
        for filename in 'DA.out','DAsurv.out','DA.png','DAsurv.png','DAsurv_log.png','DAsurv_comp.png','DAsurv_comp_log.png':
          ppf=os.path.join(pp,filename)
          if(os.path.exists(ppf)):
            os.remove(ppf)
            if(count==0):
              print('remove old DA.out, DAsurv.out ... files in '+db.LHCDescrip)
              count=count+1
# start analysis
  if(not db.check_seeds()):
    print('!!! Seeds are missing in database !!!')
  for seed in db.get_db_seeds():
    seed=int(seed)
    print('analyzing seed {0} ...').format(str(seed))
    for tune in db.get_tunes():
      print('analyzing tune {0} ...').format(str(tune))
      dirname=db.mk_analysis_dir(seed,tune)
      print('... get survival plot data')
      DAsurv=db.get_surv(seed,tune)
      # case: create data
      if(force):
        #load and save the data
        print('... calculate da vs turns')
        DAout=get_da_vs_turns(seed,tune,DAsurv,turnstep)
        print('.... save data in database')
        db.st_da_vst(DAout)
      # case: reload data
      else:
        print('... get da vs turns data')
        DAout = reload_daout(dirname)
      if(outfile):# create DAsurv.out and DA.out files
        print('... save outputfiles DA.out (da vs turns) and DAsurv.out (survival plots)')
        save_dasurv(DAsurv,dirname)
        save_daout(DAout,dirname)
      print('- create the plots')
      pl.close('all')
      db.plot_surv_2d(seed,tune,ampmaxsurv)
      pl.savefig(dirname+'/DAsurv.png')
      print('... creating plot DAsurv.png')
      plot_da_vs_turns(DAout,str(seed),ampmindavst,ampmaxdavst,tmax,plotlog)
      if(plotlog==True):
        pl.savefig(dirname+'/DA_log.png')
        print('... creating plot DA_log.png')
      else:
        pl.savefig(dirname+'/DAsurv.png')
        print('... creating plot DAsurv.png')

def RunDaVsTurnsComp(db,dbcomp,ampmaxsurv,ampmindavst,ampmaxdavst,plotlog,lblname,complblname):
  '''Da vs turns analysis for study dbname'''
# create directory structure and delete old files if force=true
  count=0
  for seed in db.get_db_seeds():
    for tune in db.get_tunes():
      if(force):
        pp=db.mk_analysis_dir(seed,tune)
        for filename in 'DA.out','DAsurv.out','DA.png','DAsurv.png','DAsurv_log.png','DAsurv_comp.png','DAsurv_comp_log.png':
          ppf=os.path.join(pp,filename)
          if(os.path.exists(ppf)):
            os.remove(ppf)
            if(count==0):
              print('remove old DA.out, DAsurv.out ... files in '+db.LHCDescrip)
              count=count+1
# start analysis
  if(not db.check_seeds()):
    print('Seeds are missing in database!')
  for seed in db.get_db_seeds():
    for tune in db.get_tunes():
      seed=int(seed)
      print('analyzing seed {0} ...').format(str(seed))
      dirname=db.mk_analysis_dir(seed,tune)
      # case: create DA.out and DAsurv.out file
      if(force):
        #load and save the data
        print('- load and save the data')
        print('... creating file DAsurv.out')
        DAsurv=db.get_surv(seed)
        # create DAsurv.out file used for survival plots in old scripts
        save_dasurv(DAsurv,dirname)
        print('... creating file DA.out')
        DAout=get_da_vs_turns(DAsurv,turnstep)
        # create DA.out file used for DA vs turns plots in old scripts
        save_daout(DAout,dirname)
      # case: reload DA.out files
      else:
        try:
          DAout = reload_daout(dirname)
        except IndexError:
          print('Error in RunDaVsTurns - DA.out file not found for seed {0}!').format(str(seed))
          sys.exit(0)
        try:
          DAsurv= reload_dasurv(dirname)
        except IndexError:
          print('Error in RunDaVsTurns - DAsurv.out file not found for seed {0}!').format(str(seed))
          sys.exit(0)
        print('- reload the data')
      print('- create the plots')
      pl.close('all')
      db.plot_surv_2d(DAsurv,str(seed),ampmaxsurv)
      pl.savefig(dirname+'/DA.png')
      print('... creating plot DA.png')
      plot_da_vs_turns(DAout,str(seed),ampmindavst,ampmaxdavst,tmax,plotlog)
      if(plotlog==True):
        pl.savefig(dirname+'/DAsurv_log.png')
        print('... creating plot DAsurv_log.png')
      else:
        pl.savefig(dirname+'/DAsurv.png')
        print('... creating plot DAsurv.png')
      if(comp==True):
        compdirnameseed=os.path.join(compdirname,str(seed),tune_dir(tune))
        try:
            DAoutcomp=reload_daout(compdirnameseed)
        except IndexError:
            print('Error in RunDaVsTurns - file {} does not exist!').format(compdirnameseed)
            sys.exit(0)
        plot_da_vs_turns_comp(DAout,lblname,DAoutcomp,complblname,str(seed),ampmindavst,ampmaxdavst,tmax,plotlog)
        if(plotlog==True):
          figname=os.path.join(dirname,"DAsurv_comp_log.png")
        else:
          figname=os.path.join(dirname,"DAsurv_comp.png")
        pl.savefig(dirname+'/DAsurv_comp.png')
        print('... creating plot DAsurv_comp.png')

#      # case: reload data
#      else:
#        try:
#          DAout = reload_daout(dirname)
#        except IndexError:
#          print('Error in RunDaVsTurns - DA.out file not found for seed {0}!').format(str(seed))
#          sys.exit(0)
#        try:
#          DAsurv= reload_dasurv(dirname)
#        except IndexError:
#          print('Error in RunDaVsTurns - DAsurv.out file not found for seed {0}!').format(str(seed))
#          sys.exit(0)
