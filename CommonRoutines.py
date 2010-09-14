import string
import ROOT
import array
import math
import random
from Graph import Graph
from Cut import Cut
from Histogram import Histogram
from Styles import *
from ROOT import gROOT, gStyle, gPad, TGraph
import os
import sys
import uuid
from pprint import pprint

currentStyle = None

def readline(file,cont=None):

    line = file.readline()
    if cont != None:
        while line.strip().endswith(cont):
            line = " ".join([line.strip()[:-1*len(cont)],file.readline()])
    return line

def readlines(file,cont=None):
    
    lines = []
    line = readline(file,cont)
    while line != '':
        lines.append(line)
        line = readline(file,cont=None)
    return lines

def getTrees(inputFile):

    return getTObjects(inputFile, "TTree")

def getTreeNames(inputFile):

    return getTObjectNames(inputFile, "TTree")

def getGraphs(inputFile):
    
    return getTObjects(inputFile, "TGraph")
    
def getHistos(inputFile):

    return getTObjects(inputFile, "TH1D")

def getTObjects(inputFile, className):
    
    keys = inputFile.GetListOfKeys()
    objects = []
    for key in keys:
        if key.GetClassName() == className:
            objects.append(inputFile.Get(key.GetName()))
    return objects

def getTObjectNames(inputFile, className):
    
    keys = inputFile.GetListOfKeys()
    names = []
    for key in keys:
        if key.GetClassName() == className:
            names.append(key.GetName())
    return names

def getNumEntries(trees,cuts=None,weighted=True,verbose=False):
   
    if type(trees) is not list:
        trees = [trees]
    if weighted:
        if verbose: print "Retrieving the weighted number of entries in:"
    else:
        if verbose: print "Retrieving the unweighted number of entries in:"
    wentries = 0.
    if cuts != None:
        if not cuts.empty():
            if verbose: print "Using cuts: %s"%str(cuts)
            for tree in trees:
                weight = tree.GetWeight()
                entries = tree.GetEntries(str(cuts))
                if verbose: print "%s\t%e\t%i"%(tree.GetName(),weight,entries)
                if weighted:
                    wentries += weight*entries
                else:
                    wentries += entries
            return wentries
    for tree in trees:
        weight = tree.GetWeight()
        entries = tree.GetEntries()
        if verbose: print "%s\t%e\t%i"%(tree.GetName(),weight,entries)
        if weighted:
            wentries += weight*entries
        else:
            wentries += entries
    return wentries

def makeLabel(x,y,text,textsize=-1):

    label = ROOT.TLatex(x,y,text)
    label.SetNDC()
    if textsize > 0:
        label.SetTextSize(textsize)
    return label

def drawObject(pad,object,options=""):

    pad.cd()
    object.Draw(options)
    pad.Modified()
    pad.Update()
    hold_pointers_to_implicit_members(pad)

def getTreeMaximum(trees,branchName):

    if type(trees) is not list:
        trees = [trees]
    max = -1E300
    for tree in trees:
        treeMax = tree.GetMaximum(branchName)
        if treeMax > max:
            max = treeMax
    return max 

def getTreeMinimum(trees,branchName):
    
    if type(trees) is not list:
        trees = [trees]
    min = -1E300
    for tree in trees:
        treeMin = tree.GetMinimum(branchName)
        if treeMin > min:
            min = treeMin
    return min

def drawTrees(trees,hist,expression,cuts=None,weighted=True,verbose=False):
   
    if type(trees) is not list:
        trees = [trees]
    temp_weight = 1. 
    if verbose:
        print ""
        print "Drawing the following trees onto %s:"%hist.GetName()
        print "Initial integral: %f"%hist.Integral()
    if cuts != None:
        if not cuts.empty():
            if verbose: print "cuts applied: %s"%str(cuts)
            for tree in trees:
                if verbose: print tree.GetName()
                if not weighted:
                    temp_weight = tree.GetWeight()
                    tree.SetWeight(1.)
                tree.Draw("%s>>+%s"%(expression,hist.GetName()),str(cuts))
                if not weighted:
                    tree.SetWeight(temp_weight)
            if verbose:
                print "Final integral: %f"%hist.Integral()
            return
    for tree in trees:
        if verbose: print tree.GetName()
        if not weighted:
            temp_weight = tree.GetWeight()
            tree.SetWeight(1.)
        tree.Draw("%s>>+%s"%(expression,hist.GetName()))
        if not weighted:
            tree.SetWeight(temp_weight)
    if verbose:
        print "Final integral: %f"%hist.Integral()

def closest(target, collection):

    return collection.index((min((abs(target - i), i) for i in collection)[1]))

def round_to_n(x, n):

    if n < 1:
        raise ValueError("number of significant digits must be >= 1")
    return "%.*g" % (n, x)

def drawLogGraphs(pad,graphs,title,xtitle,ytitle,label=None,format="png"):
    
    pad.cd()
    pad.SetLogy()
    #if format not in ("pdf","eps"):
    #pad.SetGrid()
    legend,legendheight = getLegend(len(graphs),pad)
    legend.SetEntrySeparation(0.01)
    
    xmax = -1E20
    xmin = 1E20
    ymax = -1E20
    ymin = 1E20
    for graph in graphs:
        txmax = graph.xMax()
        txmin = graph.xMin()
        tymax = graph.yMax()
        tymin = graph.yMin()
        if txmax > xmax:
            xmax = txmax
        if txmin < xmin:
            xmin = txmin
        if tymax > ymax:
            ymax = tymax
        if tymin < ymin:
            ymin = tymin
        
    stack = ROOT.TMultiGraph(title,title)
    for index,graph in enumerate(graphs):
        legend.AddEntry(graph,graph.GetTitle(),"P")
        graph.SetMarkerSize(1.5)
        stack.Add(graph,"P")
    stack.Draw("A")
    
    stack.GetXaxis().SetLimits(xmin,xmax)
    stack.GetXaxis().SetRangeUser(xmin,xmax)
    stack.GetXaxis().SetTitle(xtitle)
    
    stack.GetYaxis().SetLimits(ymin,ymax)
    stack.GetYaxis().SetRangeUser(ymin,ymax)
    stack.GetYaxis().SetTitle(ytitle)
    
    stack.SetTitle(title)
    legend.Draw()
    if label:
        label.Draw()
    stack.UseCurrentStyle()
    pad.Modified()
    pad.Update()
    for item in pad.GetListOfPrimitives():
        if isinstance(item,ROOT.TPaveText):
            text = item.GetLine(0)
            text.SetTextFont(63)
            text.SetTextSizePixels(20)
    hold_pointers_to_implicit_members(pad)

## Come back here and implement 3d histograms!
def drawHistos(
        pad,
        histos,
        title,
        axisTitles,
        legend=None,
        legendheight=1.,
        label=None,
        ylabel="",
        normalized="NONE",
        showLegend=True,
        h1dOption="HIST",
        h2dOption="LEGO20",
        h3dOption="SCAT",
        yscale="linear",
        myMin=None,
        myMax=None
    ):
   
    if type(histos) is not list:
        histos = [histos]

    histos = [hist.Clone() for hist in histos] # make copies to not alter originals

    if type(axisTitles) is not list:
        axisTitles = [axisTitles]
    
    if yscale not in ["linear","log"]:
        print "Unknown scale type for y-axis"
        return
    
    pad.cd()
    if yscale == "log":
        pad.SetLogy()
    
    pad.SetTopMargin(ROOT.gStyle.GetPadTopMargin())
    pad.SetRightMargin(ROOT.gStyle.GetPadRightMargin())
    pad.SetBottomMargin(ROOT.gStyle.GetPadBottomMargin())
    pad.SetLeftMargin(ROOT.gStyle.GetPadLeftMargin())

    if title != "":
        pad.SetTopMargin(0.1)

    for hist in histos:
        if "colz" in hist.format.lower():
            if title == "":
                pad.SetTopMargin(0.06)
            pad.SetRightMargin(0.13)
            break
    
    if not legend:
        legend,legendheight = getLegend(len(histos),pad)

    if type(axisTitles) is not list:
        axisTitles = [axisTitles]
    
    for hist in histos:
        if normalized.upper() == "MAX":
            if hist.GetMaximum()>0:
                hist.Scale(1./hist.GetMaximum())
        elif normalized.upper() == "UNIT":
            if hist.Integral()>0:
                hist.Scale(1./float(hist.Integral()))
    
    max = -1E270
    min = 1E270
    for hist in histos:
        if hist.GetMaximum() > max:
            max = hist.GetMaximum()
        if hist.GetMinimum() < min:
            min = hist.GetMinimum()

    if myMax != None:
        if myMax > max:
            max = myMax
    if myMin != None:
        if myMin < min:
            min = myMin
    
    axesDrawn = False
    if showLegend and legend:
        plotheight = 1 - pad.GetTopMargin() - pad.GetBottomMargin()
        padding = 0.05
        if yscale == "linear":
            max = (max - (min * (legendheight+padding) / plotheight)) / (1. - (legendheight+padding) / plotheight)
        else: # log
            max = 10.**((math.log10(max) - (math.log10(min) * (legendheight+padding) / plotheight)) / (1. - (legendheight+padding) / plotheight))

    for index,hist in enumerate(histos):
       
        if legend and showLegend and hist.inlegend:
            legend.AddEntry(hist,hist.GetTitle().replace("_"," "),hist.legend) 
        if len(axisTitles)>1 and normalized.upper() != "NONE":
            hist.SetTitle(hist.GetTitle()+" Normalized")
        drawOptions = []
        if index == 0 or not axesDrawn:
            hist.SetTitle(title)
            hist.GetXaxis().SetTitle(axisTitles[0])
            hist.GetYaxis().SetTitle(ylabel)
            if max > min and len(axisTitles)==1:
                hist.GetYaxis().SetLimits(min,max)
                hist.GetYaxis().SetRangeUser(min,max)
            if hist.intMode:
                hist.GetXaxis().SetNdivisions(hist.GetXaxis().GetNbins(),True)
            if len(axisTitles) in [2,3]:
                hist.GetYaxis().SetTitle(axisTitles[1])
                """
                if (len(axisTitles)==2 and ("LEGO" in h2dOption.upper())) or len(axisTitles)==3:
                    #hist.GetYaxis().SetTitleOffset(1.8)
                    #hist.GetXaxis().SetTitleOffset(1.8)
                """
                if len(axisTitles) == 3:
                    hist.GetZaxis().SetTitle(axisTitles[2])
                    hist.GetZaxis().SetTitleOffset(1.8)
        else:
            hist.SetTitle("")
            drawOptions.append("same")
        """
        if len(axisTitles) == 1 and h1dOption != "":
            drawOptions.append(h1dOption)
        elif len(axisTitles) == 2 and h2dOption != "":
            drawOptions.append(h2dOption)
        elif len(axisTitles) == 3 and h3dOption != "":
            drawOptions.append(h3dOption)
        """
        if hist.visible:
            axesDrawn = True
        hist.Draw(drawOptions)
    
    if legend and showLegend:
        legend.Draw()

    if label:
        label.Draw()

    pad.Modified()
    pad.Update()
    for item in pad.GetListOfPrimitives():
        if isinstance(item,ROOT.TPaveText):
            text = item.GetLine(0)
            text.SetTextFont(63)
            text.SetTextSizePixels(20)
    hold_pointers_to_implicit_members(pad)

def savePad(pad,filename=None,format="png",dir=None):
    
    if not filename:
        filename = pad.GetName() #To Fix
    for c in string.punctuation:
        filename = filename.replace(c,'-')
    filename = filename.strip().replace(' ','-')
    
    if dir:
        filename = dir.strip("/")+"/"+filename
    
    formats = format.split('+')
    for imageformat in formats:
        pad.Print(".".join([filename,imageformat]))

def hold_pointers_to_implicit_members( obj ):
    
    if not hasattr(obj, '_implicit_members'):
        obj._implicit_members = []
    if hasattr(obj, 'GetListOfPrimitives'):
        for prim in obj.GetListOfPrimitives():
            if prim not in obj._implicit_members:
                obj._implicit_members.append(prim)
            
def getLegend(numEntries,pad,leftmargin = 0.,textfont=None,textsize=0.04,fudge=1.):
   
    buffer = 0.03
    height = fudge*0.04*numEntries + buffer
    legend = ROOT.TLegend(pad.GetLeftMargin()+buffer+leftmargin,(1.-pad.GetTopMargin()) - height,1.-pad.GetRightMargin(),((1.-pad.GetTopMargin())-buffer))
    legend.UseCurrentStyle()
    legend.SetEntrySeparation(0.2)
    legend.SetMargin(0.15)
    legend.SetFillStyle(0)
    legend.SetFillColor(0)
    if textfont:
        legend.SetTextFont(textfont)
    legend.SetTextSize(textsize)
    legend.SetBorderSize(0)
    return legend,height

def ROOTlogon(batch=False,noGlobal=False,style="MINE"):

    global currentStyle
    if noGlobal:
        ROOT.TH1.AddDirectory(False) # Stupid global variables in ROOT... doing this will screw up TTree.Draw()
    if batch:
        ROOT.gROOT.SetBatch()
    ROOT.TH1.SetDefaultSumw2(True)
    #ROOT.gROOT.SetStyle("Plain")
    ROOT.TGaxis.SetMaxDigits(3)
    tstyle = getStyle(style)
    currentStyle = tstyle
    if tstyle:
        print "Using ROOT style %s"%tstyle.GetName()
        ROOT.gROOT.SetStyle(tstyle.GetName())
        ROOT.gROOT.ForceStyle()
        ROOT.gStyle.SetPalette(1)
    else:
        print "Style %s is not defined"%style
