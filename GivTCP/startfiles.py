"""The files in the cache folder that startup keeps. It deletes the rest, as they belong to the previous run"""

KEEP_PREFIXES=("rateData","writecount","safewritecount",".dayRate",".nightRate","allsettings","v2env",".v3upgrade",
               ".load_formula",
               "pendingReverts_")       # timed reverts still due, which the read loop runs or reschedules once it starts

def keptOnStart(filename):
    # Logs, the settings and rate data, and each inverter's capabilities, so detect only runs once per inverter
    return "log" in filename or filename.startswith(KEEP_PREFIXES) or filename.endswith("_caps.pkl")
