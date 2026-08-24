BOROUGHS=("Manhattan","Brooklyn","Queens","Bronx","Staten Island")

QUEENS_TERMS=("queens","flushing","glendale","richmond hill","kew gardens","far rockaway","long island city","astoria","woodside","sunnyside","jackson heights","elmhurst","rego park","forest hills","jamaica","bayside","fresh meadows","college point","whitestone","corona","maspeth","middle village","ridgewood","ozone park","howard beach","woodhaven","cambria heights","laurelton","rosedale","springfield gardens","south ozone park","briarwood","little neck","douglaston")

def infer_nyc_borough(address):
    text=" ".join((address or "").lower().replace(".","").split())
    if not text: return None
    if any(term in text for term in QUEENS_TERMS): return "Queens"
    if "brooklyn" in text: return "Brooklyn"
    if "bronx" in text: return "Bronx"
    if "staten island" in text: return "Staten Island"
    if "manhattan" in text or "new york, ny" in text or "new york ny" in text: return "Manhattan"
    return None
