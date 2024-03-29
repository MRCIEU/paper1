# this script generates sequence similarity kernel matrices
# based on varying lengths of window sizes (w), and k-mer sizes (k)

from Bio import SeqIO
import os
import pandas as pd
from strkernel.mismatch_kernel import MismatchKernel
from strkernel.mismatch_kernel import preprocess
from Bio import SeqIO
from Bio.Seq import Seq
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score
from sklearn.metrics import classification_report # classfication summary
import matplotlib.pyplot as plt
import numpy as np
from numpy import random

# Reads in the human GRCh38 genome in fasta format
os.chdir("/Users/uw20204/Desktop/20221110")
record_dict = SeqIO.to_dict(SeqIO.parse("hg38.fa", "fasta"))

# Reading in the variant file
variants = pd.read_csv("filteredRGreater5Variants.txt", sep = "\t", names = ['chrom', 'pos', 'reference_allele', 'alternate_allele', 'reccurance', 'driver_status'])

# Removes sex chromosomes
variants = variants[(variants['chrom'] != "chrX") & (variants['chrom'] != "chrY")]
variants = variants.reset_index(drop = True)

# unput is the variant dataset and window size either side of the variants (e.g. w of 100 = 200 bp in total)
def getSequences(dataset, window_size):
    kmerDf = pd.DataFrame()
    similarityArray = []

    def getSeqFun(i):

        # generates wild type sequence
        # by refering to the reference sequence, it gets the sequences flanking 100bp either side of the variant position
        wildType = str(record_dict[dataset.loc[i, "chrom"]].seq[int(dataset.loc[i, "pos"]-1-window_size):int(dataset.loc[i, "pos"]-1+window_size)]).upper()

        # mutant sequence
        # repeats the same as above but replaces WT variant with the mutant variant
        mutant = str(record_dict[dataset.loc[i, "chrom"]].seq[int(dataset.loc[i, "pos"]-1-window_size):int(dataset.loc[i, "pos"]-1)]) + dataset.loc[i, "alternate_allele"] + str(record_dict[dataset.loc[i, "chrom"]].seq[int(dataset.loc[i, "pos"]):int(dataset.loc[i, "pos"]-1+window_size)]).upper()

        kmerDf.loc[i, "wildType"] = wildType.upper()
        kmerDf.loc[i, "mutant"] = mutant.upper()
        seq = [wildType.upper()] + [mutant.upper()]
        int_seq = preprocess(seq)

        # Generates mismatch kernel
        mismatch_kernel1 = MismatchKernel(l=4, k=2, m=1).get_kernel(int_seq)
        similarity_mat1 = mismatch_kernel1.kernel
        similarityArray.append(similarity_mat1[0][1])

    # Carries out function for each variant in the dataset
    [getSeqFun(i) for i in range(0, len(variants))]
    return similarityArray, kmerDf

from itertools import islice
 
# generator function
def over_slice(test_str, K):
    itr = iter(test_str)
    res = tuple(islice(itr, K))
    if len(res) == K:
        yield res   
    for ele in itr:
        res = res[1:] + (ele,)
        yield res

def getSpectrumFeatures(seq1, seq2, k): 
    # initializing string
    test_str = seq1 + seq2

    # initializing K
    K = k
    
    # calling generator function
    res = ["".join(ele) for ele in over_slice(test_str, K)]
    dfMappingFunction = pd.DataFrame(columns = ["seq"] + res)
    dfMappingFunction.loc[0, "seq"] = seq1
    dfMappingFunction.loc[1, "seq"] = seq2

    # generate mapping function
    def getMappingFunction(res, seq):
        if res in seq:
            dfMappingFunction.loc[dfMappingFunction["seq"] == seq, res] = dfMappingFunction.loc[dfMappingFunction["seq"] == seq, "seq"].reset_index(drop=True)[0].count(res) 
        else:
            dfMappingFunction.loc[dfMappingFunction["seq"] == seq, res] = 0

    for seq in [seq1, seq2]:
        [getMappingFunction(x, seq) for x in res]

    # generate p-spectra
    pSpectrumKernel = pd.DataFrame(columns=[seq1, seq2])
    pSpectrumKernel.insert(0, "seq", [seq1, seq2])

    # to derive p-spectra, take product of every row and sum together
    products_WT_mut = [np.prod(dfMappingFunction.iloc[:, i]) for i in range(1, len(dfMappingFunction.columns))]
    sum_WT_mut  = np.sum(products_WT_mut)
    pSpectrumKernel.iloc[0, 2] = sum_WT_mut
    pSpectrumKernel.iloc[1, 1] = sum_WT_mut
    squares_WT = [np.square(dfMappingFunction.iloc[0, i]) for i in range(1, len(dfMappingFunction.columns))]
    squares_mutant = [np.square(dfMappingFunction.iloc[1, i]) for i in range(1, len(dfMappingFunction.columns))]
    pSpectrumKernel.iloc[0, 1] = np.sum(squares_WT)
    pSpectrumKernel.iloc[1, 2] = np.sum(squares_mutant)
    return pSpectrumKernel.drop("seq", axis = 1)

def getFinalSpectrumDf(windowSize, kmerSize):
    # kmer of window size 5 and kmer size 3
    # get sequences given a set of variants and specified sequence lengths
    variantsSequences = getSequences(variants, windowSize)
    spectrumFeatureList = [getSpectrumFeatures(list(variantsSequences[1].loc[i, :])[0], list(variantsSequences[1].loc[i, :])[1], kmerSize) for i in range(0, len(variantsSequences[1]))]
    y = variants["driver_status"]
    spectrumList = [list(spectrumFeatureList[x].loc[0, :]) + list(spectrumFeatureList[x].loc[1, :]) for x in range(0, len(spectrumFeatureList))]
    spectrumdf = pd.DataFrame(spectrumList)
    spectrumdf = pd.concat([variants, spectrumdf], axis = 1)
    spectrumdf["chrom"] = spectrumdf["chrom"].str.replace("chr", "").astype(str)
    spectrumdf["pos"] = spectrumdf["pos"].astype(int)

    # save each result to CSV file
    spectrumdf.to_csv(str(windowSize) + "_" + str(kmerSize) + "_kernel.txt")

# get p-spectra for window sizes 1-5 ranging from k-mers of 1-4
[getFinalSpectrumDf(5, i) for i in range(1, 4)]
[getFinalSpectrumDf(4, i) for i in range(1, 4)]
[getFinalSpectrumDf(3, i) for i in range(1, 4)]
[getFinalSpectrumDf(2, i) for i in range(1, 3)]
[getFinalSpectrumDf(1, i) for i in range(1, 2)]
