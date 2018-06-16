
import argparse
import os
from subprocess import call
import numpy as np

from MUSHACreconstruction import MUSHACreconstruction

#%% run Benoit's denoising algo
def runDenoising( inputData, outputName ):

    if not os.path.exists( outputName ): 
        functionDenoising = '/home/ch137122/Software/mrtrix/mrtrix3/release/bin/dwidenoise'
        functionMRconvert = '/home/ch137122/Software/mrtrix/mrtrix3/release/bin/mrconvert'

        tmpdir = '/tmp/tmp%d'  %(np.random.randint(1e6))
        os.makedirs(tmpdir)

        print 'Convert to FSL'
        out = call([ 'crlDWIConvertNHDRForFSL', '-i', inputData, '--data', tmpdir + '/data.nii' ,\
                            '--bvals',  tmpdir + '/bvals', '--bvecs', tmpdir + '/bvecs'])
        print 'Convert to MIF'
        out = call([ functionMRconvert, '-fslgrad', tmpdir + '/bvecs', tmpdir + '/bvals', tmpdir + '/data.nii',  tmpdir + '/data.mif' ])

        print 'run denoise'
        out = call([ functionDenoising, tmpdir + '/data.mif',  tmpdir + '/data-denoised.nii' ])

        print 'convert back to NHDR'
        out = call([ 'crlDWIConvertFSLToNHDR', '-i', tmpdir + '/data-denoised.nii', '-o', outputName ])

        os.rmdir(tmpdir)
    else:
        print '%s already exists. NOt computing denoising algorithm.' %(outputName)

#%% run DIAMOND on benchmark data
def runDIAMOND( dataNHDR, inputFolder, mask, outputName, saveRef='', numThreads=50):

    # define which DIAMOND code to call
    functionName = 'crlDCIEstimate'
    if np.any( os.uname()[1] == [ 'galahad','lancelot','percival' ] ):
        functionName = '/home/ch199899/bins/crlDCIEstimate_March2018_XeonPhi'

    # run DIAMOND
    print outputName[:-5] + '_t0.nrrd'
    if not os.path.exists( outputName[:-5] + '_t0.nrrd' ):
        try:
            out = call([functionName, '-i',  inputFolder + dataNHDR, '-m', mask,  '--residuals' ,'-o', outputName, '-n 3', '-p ' + str(numThreads) , '--automose aicu', '--fascicle diamondcyl'] )
        except :
            print 'Could not run DIAMOND on ' + dataNHDR
    else:
        print outputName  + ' already computed'


def readInBvecsAndBvals( inputFolder, bvecsFile='dwi.bvec', bvalsFile='dwi.bval' ):

    # b values
    fbvals = open( inputFolder + bvalsFile )
    lines = fbvals.readlines()
    fbvals.close()
    splitLine = lines[0].split(' ')
    val = [ float(vv) for vv in splitLine if not vv=='' ]
    bvals = np.array( val )

    # b vectors
    fbvals = open( inputFolder + bvecsFile )
    lines = fbvals.readlines()
    fbvals.close()
    bvecs = []
    for ll in lines:
        splitLine = ll.split(' ')
        vecs = [ float(vv) for vv in splitLine if (not vv=='')&(not vv=='\n') ]

        bvecs.append( np.array( vecs ) )

    # return bvecs, bvals
    return bvals, np.array(bvecs).T

def resample2HighRes( headerFile, inputPath, outputPath, maskPath, resolution ,nThreads=50):


    # update header file
    fo = open( inputPath + headerFile )
    lines = fo.readlines()
    fo.close()

    # retrieve files reated to the given header
    dwiFiles = []
    readFiles = False
    for ll in lines:
        if 'data file: LIST' in lines[ll]:
            readFiles = True
        if readFiles:
            dwiFiles.append( ll )

    # resample files
    newDWIfiles = []
    for ff in dwiFiles:

        # update resolution of individual nrrds
        resolutionSTR = '%0.2f,%0.2f,%0.2f' %(resolution, resolution, resolution)
        outName = ff[:-9] + 'isores%dmm_' %(resolution*10) + ff[-9:]  

        if not os.path.exists( outputPath +  outName ):
            out = call(['crlResampler2', '--voxelsize', resolutionSTR, '-i', inputPath + ff, '-o' , outputPath +  outName, '--interp linear', '-p', str(nThreads)])

        newDWIfiles.append( outName )

    # extract new size from an example file
    fr = open( outputPath + dwiFiles[0])
    rlines = fr.readlines()
    fr.close()
    refSize = [ ll for ll in rlines if 'sizes:' in ll ][0][:-1]
    refSpD = [ ll for ll in rlines if 'space directions' in ll ][0][:-1]
    refOrg = [ ll for ll in rlines if 'space origin:' in ll ][0][:-1]

    # write 
    for ll in range(len(lines)):
        if 'sizes' in lines[ll]:
            numBval = lines[ll].split(' ')[-1]
            lines[ll] = refSize + ' ' + numBval 
        if 'space directions' in lines[ll]:
            lines[ll] = refSpD + ' none\n'
        if 'space origin:' in  lines[ll]:
            lines[ll] = refOrg + '\n'

        if 'data file: LIST' in lines[ll]:
            for l2 in range(ll+1, len(lines)):
                lines[l2] = newDWIfiles.pop(0) + '\n'
            break

    outName = headerFile[:-5] + '_isores%dmm.nhdr' %(resolution*10)
    fo = open( outputPath + outName , 'w+')
    fo.writelines( lines )
    fo.close()
    

    # resample mask
    outMask = maskPath[:-5] + '_isores%dmm.nrrd' %(resolution*10)
    if not os.path.exists( outMask ):
        out = call(['crlResampler2', '--voxelsize', resolutionSTR, '-i', maskPath, '-o' , outMask, '--interp nearest', '-p', str(nThreads)])

    return outName, outMask

# ------------------ MAIN ----------------------- #

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Benchmark code for DWI data')
    parser.add_argument('-d', '--dir', required=True,
                        help='path to subject folders')
    parser.add_argument('-s', '--subj', default='all',
                        help='subject ID')
    parser.add_argument('-seq', '--seq', default='all',
                        help='sequence ID')
    parser.add_argument('-seq_ref', '--seq_ref', default='prisma',
                        help='sequence for refrence ID')
    parser.add_argument('-res_ref', '--res_ref', default='st',
                        help='resolution for refrence ID')
    parser.add_argument('-p', '--threads', default='50',
                        help='number of threads')
    args = parser.parse_args()

    if args.subj == 'all': 
        subjects = ['A','B','C','D','E','F','G','I','J','K']
    else:
        subjects = [args.subj]

    if args.seq == 'all':
        sequences = ['prisma','connectom']
    else:
        sequences = [args.seq]

    
    # for all subjects
    for subj in subjects:

        dataNHDR = subj + '_' + args.seq_ref + '_' + args.res_ref + '_dwi.nhdr'
        dataDenoisedNHDR = subj + '_' + args.seq_ref + '_' + args.res_ref + '_denoised_dwi.nhdr'
        # set reference paths
        refInputFolder = args.dir + subj + '/' + args.seq_ref + '/' + args.res_ref + '/' 
        refOutputFolder = refInputFolder + 'DIAMOND/' + dataNHDR[:-9] + '_DIAMOND3T.nrrd'
        if not os.path.exists( refOutputFolder ):
            os.makedirs( refOutputFolder )
        mask = refInputFolder + 'mask.nrrd'

        # run DIAMOND on the reference sequence
        print 'Running DIAMOND on reference data'
        runDIAMOND( dataNHDR, refInputFolder + 'dwi/', mask, refOutputFolder,  numThreads=args.threads )

        # ------------------ DENOISED DATA ----------------------- #
        print 'Running denoising on reference data'
        runDenoising( refInputFolder + 'dwi/' + dataNHDR, refInputFolder + 'dwi/' + dataDenoisedNHDR )
        refOutputFolder = refInputFolder + 'DIAMOND/' +  dataDenoisedNHDR[:-9]  + '_DIAMOND3T.nrrd'
        print 'Running DIAMOND on denoised reference data'
        runDIAMOND( dataDenoisedNHDR, refInputFolder + 'dwi/', mask, refOutputFolder, numThreads=args.threads )


        # ------------------ UPSAMPLE  ----------------------- # 
        # upsample dwi data to 1.5 and run DIAMOND
        print 'Resampling data to 1.5mm'
        ref15ResolutionFolder = refInputFolder + 'dwi_iso15mm/'
        if not os.path.exists( ref15ResolutionFolder ):
            os.makedirs( ref15ResolutionFolder )
        dataNHDR15mm, mask15mm = resample2HighRes( dataNHDR, refInputFolder + 'dwi/', ref15ResolutionFolder, mask, 1.5 ,nThreads=int(args.threads))
        
        print 'Running DIAMOND on data at resolution 1.5mm'
        outputFolder = refInputFolder + 'DIAMOND_iso15mm/' + subj + '_' + args.seq_ref + '_' + args.res_ref + '_iso12mm_DIAMOND3T.nrrd'
        if not os.path.exists( refInputFolder + 'DIAMOND_iso15mm/' ):
            os.makedirs( refInputFolder + 'DIAMOND_iso15mm/' )
        runDIAMOND( dataNHDR15mm, ref15ResolutionFolder, mask15mm, outputFolder,  args.threads )

        # upsample dwi data to 1.5 and run DIAMOND
        print 'Resampling data to 1.2mm'
        ref12ResolutionFolder = refInputFolder + 'dwi_iso12mm/'
        if not os.path.exists( ref12ResolutionFolder ):
            os.makedirs( ref12ResolutionFolder )
        dataNHDR12mm, mask12mm = resample2HighRes( dataNHDR, refInputFolder + 'dwi/', ref12ResolutionFolder, mask, 1.2 ,nThreads=int(args.threads))

        print 'Running DIAMOND on data at resolution 1.2mm'
        outputFolder = refInputFolder + 'DIAMOND_iso12mm/' + subj + '_' + args.seq_ref + '_' + args.res_ref + '_iso12mm_DIAMOND3T.nrrd'
        if not os.path.exists( refInputFolder + 'DIAMOND_iso12mm/' ):
            os.makedirs( refInputFolder + 'DIAMOND_iso12mm/' )
        runDIAMOND( dataNHDR12mm, ref12ResolutionFolder, mask12mm, outputFolder,  args.threads )




        # prepare diamond model for extrapolation
        print 'Preparing DIAMOND model for extrapolation'
        diamondModel = MUSHACreconstruction( refInputFolder,'DIAMOND/','dwi/',maskPath='mask.nrrd')




        # ------------------ COMPARISON ----------------------- #

        for seq in sequences:
            
            for res in ['sa','st']:

                # set paths
                inputFolder = args.dir + subj + '/' + seq + '/' + res + '/' 
                outputFolder = inputFolder + 'DIAMOND/' + subj + '_' + seq + '_' + res + '_DIAMOND3T.nrrd'
                if not os.path.exists( inputFolder + 'DIAMOND/' ):
                    os.makedirs( inputFolder + 'DIAMOND/' )
                mask = inputFolder + 'mask.nrrd'

                # run DIAMOND on target data
                runDIAMOND( dataNHDR, inputFolder + 'dwi/', mask, outputFolder,  args.threads )

                # reconstruct data with DIAMOND
                bvals, bvecs = readInBvecsAndBvals( inputFolder )
                diamondReconstruction = diamondModel.generateDWIdata( bvecs, bvals)

                # compare results against DIAMOND residuals