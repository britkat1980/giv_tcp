"""Load Energy uses the DC-hybrid formula on hybrids again (the v2 library builds added PV twice). The hold that
stops Load going down lets it drop once to the corrected value, the first time the new formula runs"""
import os

import read

def marker():
    return os.path.join(read.GiV_Settings.cache_location, ".load_formula_" + str(read.GiV_Settings.givtcp_instance))

def test_changed_once(monkeypatch):
    if os.path.exists(marker()):
        os.remove(marker())
    assert read.loadFormulaChanged() is True       # first run with this version: let it drop
    assert read.loadFormulaChanged() is False      # then hold as before
    monkeypatch.setattr(read, "LOAD_FORMULA_VERSION", "99")
    assert read.loadFormulaChanged() is True       # a later formula change lets it drop again

def test_dc_hybrids():
    from givenergy_modbus.model.inverter import Model
    assert Model.HYBRID_GEN1 in read.DC_HYBRID_MODELS and Model.HYBRID_HV_GEN3 in read.DC_HYBRID_MODELS
    assert Model.AC not in read.DC_HYBRID_MODELS and Model.ALL_IN_ONE not in read.DC_HYBRID_MODELS
