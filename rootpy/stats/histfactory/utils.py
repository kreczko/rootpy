# Copyright 2012 the rootpy developers
# distributed under the terms of the GNU General Public License
from __future__ import absolute_import

import os
import re
import shutil
from glob import glob

import ROOT

from . import log; log = log[__name__]
from ...memory.keepalive import keepalive
from ...utils.silence import silence_sout_serr
from ...context import do_nothing, working_directory
from ...io import root_open
from ... import asrootpy
from . import Channel, Measurement, HistoSys, OverallSys

__all__ = [
    'make_channel',
    'make_measurement',
    'make_models',
    'make_model',
    'make_workspace',
    'measurements_from_xml',
    'write_measurement',
    'patch_xml',
    'split_norm_shape',
]


def make_channel(name, samples, data=None):
    """
    Create a Channel from a list of Samples
    """
    llog = log['make_channel']
    llog.info("creating channel {0}".format(name))
    # avoid segfault if name begins with a digit by using "channel_" prefix
    chan = Channel('channel_{0}'.format(name))
    chan.SetStatErrorConfig(0.05, "Poisson")

    if data is not None:
        llog.info("setting data")
        chan.SetData(data)

    for sample in samples:
        llog.info("adding sample {0}".format(sample.GetName()))
        chan.AddSample(sample)

    return chan


def make_measurement(name,
                     channels,
                     lumi=1.0, lumi_rel_error=0.,
                     output_prefix='./histfactory',
                     POI=None,
                     const_params=None):
    """
    Create a Measurement from a list of Channels
    """
    llog = log['make_measurement']
    # Create the measurement
    llog.info("creating measurement {0}".format(name))

    if not isinstance(channels, (list, tuple)):
        channels = [channels]

    meas = Measurement('measurement_{0}'.format(name), '')
    meas.SetOutputFilePrefix(output_prefix)
    if POI is not None:
        if isinstance(POI, basestring):
            llog.info("setting POI {0}".format(POI))
            meas.SetPOI(POI)
        else:
            llog.info("adding POIs {0}".format(', '.join(POI)))
            for p in POI:
                meas.AddPOI(p)

    llog.info("setting lumi={0:f} +/- {1:f}".format(lumi, lumi_rel_error))
    meas.lumi = lumi
    meas.lumi_rel_error = lumi_rel_error

    for channel in channels:
        llog.info("adding channel {0}".format(channel.GetName()))
        meas.AddChannel(channel)

    if const_params is not None:
        llog.info("adding constant parameters {0}".format(
            ', '.join(const_params)))
        for param in const_params:
            meas.AddConstantParam(param)

    return meas


def make_models(measurement, silence=False):
    """
    Create a workspace containing all models for a Measurement

    If `silence` is True, then silence HistFactory's output on
    stdout and stderr.
    """
    context = silence_sout_serr if silence else do_nothing
    with context():
        workspace = ROOT.RooStats.HistFactory.MakeModelAndMeasurementFast(
            measurement)
    return asrootpy(workspace)


def make_model(measurement, channel=None, silence=False):
    """
    Create a workspace containing the model for a measurement

    If `channel` is None then include all channels in the model

    If `silence` is True, then silence HistFactory's output on
    stdout and stderr.
    """
    context = silence_sout_serr if silence else do_nothing
    with context():
        hist2workspace = ROOT.RooStats.HistFactory.HistoToWorkspaceFactoryFast(
            measurement)
        if channel is not None:
            workspace = hist2workspace.MakeSingleChannelModel(
                measurement, channel)
        else:
            workspace = hist2workspace.MakeCombinedModel(measurement)
    workspace = asrootpy(workspace)
    keepalive(workspace, measurement)
    return workspace


def make_workspace(name, channels,
                   lumi=1.0, lumi_rel_error=0.,
                   output_prefix='./histfactory',
                   POI=None,
                   const_params=None,
                   silence=False):
    """
    Create a workspace from a list of channels
    """
    if not isinstance(channels, (list, tuple)):
        channels = [channels]
    measurement = make_measurement(
        name, channels,
        lumi=lumi,
        lumi_rel_error=lumi_rel_error,
        output_prefix=output_prefix,
        POI=POI,
        const_params=const_params)
    workspace = make_model(measurement, silence=silence)
    workspace.SetName('workspace_{0}'.format(name))
    return workspace, measurement


def measurements_from_xml(filename,
                          collect_histograms=True,
                          cd_parent=False,
                          silence=False):
    """
    Read in a list of Measurements from XML; The equivalent of what
    hist2workspace does before calling MakeModelAndMeasurementFast
    (see make_models()).
    """
    if not os.path.isfile(filename):
        raise OSError("the file {0} does not exist".format(filename))
    silence_context = silence_sout_serr if silence else do_nothing

    filename = os.path.abspath(os.path.normpath(filename))

    if cd_parent:
        xml_directory = os.path.dirname(filename)
        parent = os.path.abspath(os.path.join(xml_directory, os.pardir))
        cd_context = working_directory
    else:
        parent = None
        cd_context = do_nothing

    log.info("parsing XML in {0} ...".format(filename))
    with cd_context(parent):
        parser = ROOT.RooStats.HistFactory.ConfigParser()
        with silence_context():
            measurements_vect = parser.GetMeasurementsFromXML(filename)
        # prevent measurements_vect from being garbage collected
        ROOT.SetOwnership(measurements_vect, False)
        measurements = []
        for m in measurements_vect:
            if collect_histograms:
                with silence_context():
                    m.CollectHistograms()
            measurements.append(asrootpy(m))
    return measurements


def write_measurement(m, output_suffix=None, silence=False):
    """
    Write a measurement and RooWorkspaces for all contained channels
    into a ROOT file and write the XML into a directory with the same name as
    the measurement.
    """
    context = silence_sout_serr if silence else do_nothing
    output_name = m.name
    if output_suffix is not None:
        output_name += '_{0}'.format(output_suffix)
    output_name = output_name.replace(' ', '_')
    root_output = 'ws_{0}.root'.format(output_name)
    xml_output = 'xml_{0}'.format(output_name)
    with root_open(root_output, 'recreate') as out:
        log.info("writing histograms and measurement in {0} ...".format(root_output))
        with context():
            m.writeToFile(out)
        # get modified measurement
        out_m = out[m.name]
        with context():
            out_m.PrintXML(xml_output)
        log.info("writing combined model in {0} ...".format(root_output))
        workspace = make_model(m, silence=silence)
        workspace.Write()
        for channel in m.channels:
            log.info("writing model for channel `{0}` in {1} ...".format(channel.name, root_output))
            workspace = make_model(m, channel=channel, silence=silence)
            workspace.Write()
        log.info("writing XML in {0} ...".format(xml_output))
        with context():
            out_m.PrintXML(xml_output)
    patch_xml(glob(os.path.join(xml_output, '*.xml')), root_file=root_output)


def patch_xml(files, root_file=None, float_precision=3):
    """
    Apply patches to HistFactory XML output from PrintXML
    """
    if float_precision < 0:
        raise ValueError("precision must be greater than 0")
    for xmlfilename in files:
        xmlfilename = os.path.abspath(os.path.normpath(xmlfilename))
        patched_xmlfilename = '{0}.tmp'.format(xmlfilename)
        log.info("patching {0} ...".format(xmlfilename))
        fin = open(xmlfilename, 'r')
        fout = open(patched_xmlfilename, 'w')
        for line in fin:
            if root_file is not None:
                line = line.replace('InputFile=""', 'InputFile="{0}"'.format(root_file))
            line = line.replace(
                '<StatError Activate="True"  InputFile=""  HistoName=""  HistoPath=""  />',
                '<StatError Activate="True" />')
            line = re.sub(
                '<Combination OutputFilePrefix="(\S*)" >',
                '<Combination OutputFilePrefix="hist2workspace" >', line)
            line = re.sub('\w+=""', '', line)
            line = re.sub('\s+/>', ' />', line)
            line = re.sub('(\S)\s+</', r'\1</', line)
            # HistFactory bug:
            line = re.sub('InputFileHigh="\S+"', '', line)
            line = re.sub('InputFileLow="\S+"', '', line)
            line = line.replace('<Input>./workspaces/', '<Input>./')
            # HistFactory bug:
            line = line.replace('<ParamSetting Const="True"></ParamSetting>', '')
            # chop off floats to desired precision
            line = re.sub(r'"(\d*\.\d{{{0:d},}})"'.format(float_precision + 1),
                          lambda x: '"{0}"'.format(str(round(float(x.group(1)), float_precision))),
                          line)
            line = re.sub('"\s\s+(\S)', r'" \1', line)
            fout.write(line)
        fin.close()
        fout.close()
        shutil.move(patched_xmlfilename, xmlfilename)
        if not os.path.isfile(os.path.join(
                              os.path.dirname(xmlfilename),
                              'HistFactorySchema.dtd')):
            rootsys = os.getenv('ROOTSYS', None)
            if rootsys is not None:
                dtdfile = os.path.join(rootsys, 'etc/HistFactorySchema.dtd')
                target = os.path.dirname(xmlfilename)
                if os.path.isfile(dtdfile):
                    log.info("copying {0} to {1} ...".format(dtdfile, target))
                    shutil.copy(dtdfile, target)
                else:
                    log.warning("{0} does not exist".format(dtdfile))
            else:
                log.warning("$ROOTSYS is not set so cannot find HistFactorySchema.dtd")


def split_norm_shape(histosys, nominal_hist):
    """
    Split a HistoSys into normalization (OverallSys) and shape (HistoSys)
    components.

    It is recommended to use OverallSys as much as possible, which tries to
    enforce continuity up to the second derivative during
    interpolation/extrapolation. So, if there is indeed a shape variation, then
    factorize it into shape and normalization components.
    """
    up = histosys.GetHistoHigh()
    dn = histosys.GetHistoLow()
    up = up.Clone(name=up.name + '_shape')
    dn = dn.Clone(name=dn.name + '_shape')
    n_nominal = nominal_hist.Integral(0, nominal_hist.GetNbinsX() + 1)
    n_up = up.Integral(0, up.GetNbinsX() + 1)
    n_dn = dn.Integral(0, dn.GetNbinsX() + 1)
    up.Scale(n_nominal / n_up)
    dn.Scale(n_nominal / n_dn)
    shape = HistoSys(histosys.GetName(), low=dn, high=up)
    norm = OverallSys(histosys.GetName(),
                      low=n_dn / n_nominal,
                      high=n_up / n_nominal)
    return norm, shape
