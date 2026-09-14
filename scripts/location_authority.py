"""Autorità Geografica e Semantica delle Località (FLIGHT Module).

Distingue in modo strutturale:
- AIRPORT: aeroporti fisici con voli commerciali di linea regolari (scheduled_service).
- CITY: entità città.
- METROPOLITAN_AREA: codice aggregatore di area metropolitana servita da più aeroporti.
- NON_COMMERCIAL: aeroporti di aviazione generale, militari o chiusi al traffico commerciale.

Fornisce:
- Risoluzione univoca di alias e aeroporti GA verso l'aeroporto commerciale principale.
- Mappatura codice aeroporto -> città canonica per la deduplicazione intelligente.
- Preservazione rigorosa degli scali commerciali distinti negli hub multi-aeroporto (es. LHR vs LGW).
- Nomi puliti e riconoscibili per città e aeroporti.
"""
from __future__ import annotations
from typing import Optional

# ── 1. CODICI CITTÀ / METROPOLITAN AREA ────────────────────────────────────────
# Questi codici NON sono aeroporti fisici da cui partono voli di linea.
CITY_OR_METRO_CODES = {
    'CHI',  # Chicago (ORD, MDW)
    'LON',  # London (LHR, LGW, STN, LTN, LCY, SEN)
    'NYC',  # New York (JFK, LGA, EWR)
    'PAR',  # Paris (CDG, ORY, BVA)
    'ROM',  # Rome (FCO, CIA)
    'MIL',  # Milan (MXP, LIN, BGY)
    'MOW',  # Moscow (SVO, DME, VKO, ZIA)
    'BJS',  # Beijing (PEK, PKX)
    'SHA',  # Shanghai (PVG, SHA)
    'TYO',  # Tokyo (HND, NRT)
    'WAS',  # Washington (IAD, DCA, BWI)
    'RIO',  # Rio de Janeiro (GIG, SDU)
    'SAO',  # Sao Paulo (GRU, CGH, VCP)
    'BUE',  # Buenos Aires (EZE, AEP)
    'STO',  # Stockholm (ARN, BMA, NYO)
    'SEL',  # Seoul (ICN, GMP)
    'YTO',  # Toronto (YYZ, YTZ)
    'YMQ',  # Montreal (YUL, YHU)
    'OSA',  # Osaka (KIX, ITM)
    'SPK',  # Sapporo (CTS, OKD)
    'REK',  # Reykjavik (KEF, RKV)
    'BHZ',  # Belo Horizonte (CNF, PLU)
    'CAS',  # Casablanca (CMN)
    'MMA',  # Malmo (MMX)
    'YEA',  # Edmonton (YEG)
}

# ── 2. GA / NON-COMMERCIAL / ALIAS -> AEROPORTO COMMERCIALE PRINCIPALE ────────
# Aeroporti non di linea (GA, militari, chiusi) o codici obsoleti con corrispondenza univoca.
GA_AND_CLOSED_ALIASES: dict[str, str] = {
    'ORL': 'MCO',  # Orlando Executive (GA) -> Orlando International
    'FMY': 'RSW',  # Page Field (GA) -> Southwest Florida International
    'SIA': 'XIY',  # Xi'an Xiguan (chiuso) -> Xi'an Xianyang International
    'ANK': 'ESB',  # Etimesgut (GA/militare) -> Ankara Esenboga
    'DKR': 'DSS',  # Leopold Sedar Senghor (commerciale chiuso 2017) -> Blaise Diagne
    'NHA': 'CXR',  # Nha Trang Air Base (militare) -> Cam Ranh
    'RTW': 'GSV',  # Saratov Tsentralny (chiuso 2019) -> Saratov Gagarin
    'MES': 'KNO',  # Polonia (commerciale chiuso 2013) -> Kualanamu
    'ALY': 'HBE',  # El Nouzha (chiuso al commerciale) -> Borg El Arab
    'MKC': 'MCI',  # Charles B. Wheeler Downtown (GA) -> Kansas City International
    'SAC': 'SMF',  # Sacramento Executive (GA) -> Sacramento International
    'WSI': 'SYD',  # Western Sydney (non ancora operativo) -> Sydney Kingsford Smith
    'MLW': 'ROB',  # Spriggs Payne (GA) -> Roberts International
    'SRZ': 'VVI',  # El Trompillo (GA) -> Viru Viru International
    'NLP': 'MQP',  # Nelspruit (chiuso al commerciale) -> Kruger Mpumalanga
    'JDF': 'IZA',  # Francisco de Assis (GA) -> Presidente Itamar Franco
    'ESK': 'AOE',  # Eskisehir (GA/militare) -> Hasan Polatkan
    'AGB': 'MUC',  # Augsburg (GA) -> Munich
    'YAO': 'NSI',  # Yaounde Ville (GA/militare) -> Yaounde Nsimalen
    'ULY': 'ULV',  # Baratayevka -> Ulyanovsk Vostochny
    'ADA': 'COV',  # Adana Sakirpasa (chiuso) -> Cukurova International
    'FYV': 'XNA',  # Drake Field (GA) -> Northwest Arkansas National
    'MTS': 'SHO',  # Matsapha (GA) -> King Mswati III
    'WCA': 'MHC',  # Castro Gamboa (GA) -> Mocopulli
}

# ── 3. MAPPA CITTÀ / AREA METROPOLITANA -> AEROPORTI COMMERCIALI REALI ────────
# Tutti gli aeroporti elencati qui sono aeroporti commerciali reali e distinti.
# NON devono essere collassati l'uno nell'altro!
CITY_TO_COMMERCIAL_AIRPORTS: dict[str, list[str]] = {
    'CHI': ['ORD', 'MDW'],
    'LON': ['LHR', 'LGW', 'STN', 'LTN', 'LCY', 'SEN'],
    'NYC': ['JFK', 'LGA', 'EWR'],
    'PAR': ['CDG', 'ORY', 'BVA'],
    'ROM': ['FCO', 'CIA'],
    'MIL': ['MXP', 'LIN', 'BGY'],
    'MOW': ['SVO', 'DME', 'VKO', 'ZIA'],
    'BJS': ['PEK', 'PKX'],
    'SHA': ['PVG', 'SHA'],
    'TYO': ['HND', 'NRT'],
    'WAS': ['IAD', 'DCA', 'BWI'],
    'RIO': ['GIG', 'SDU'],
    'SAO': ['GRU', 'CGH', 'VCP'],
    'BUE': ['EZE', 'AEP'],
    'STO': ['ARN', 'BMA', 'NYO'],
    'SEL': ['ICN', 'GMP'],
    'YTO': ['YYZ', 'YTZ'],
    'YMQ': ['YUL', 'YHU'],
    'OSA': ['KIX', 'ITM'],
    'SPK': ['CTS', 'OKD'],
    'ORL': ['MCO', 'SFB'],
    'FMY': ['RSW'],
    'SIA': ['XIY'],
    'ANK': ['ESB'],
    'DKR': ['DSS'],
    'IST': ['IST', 'SAW'],
    'BER': ['BER'],
    'MAD': ['MAD'],
    'BCN': ['BCN'],
    'VCE': ['VCE', 'TSF'],
    'FLR': ['FLR', 'PSA'],
    'NAP': ['NAP', 'QSR'],
    'BLQ': ['BLQ', 'FRL'],
    'TRN': ['TRN', 'CUF'],
    'VRN': ['VRN'],
    'BRI': ['BRI', 'BDS'],
    'CTA': ['CTA', 'CIY'],
    'PMO': ['PMO', 'TPS'],
    'VIE': ['VIE'],
    'ZRH': ['ZRH'],
    'GVA': ['GVA'],
    'BSL': ['BSL'],
    'AMS': ['AMS', 'EIN', 'RTM'],
    'BRU': ['BRU', 'CRL'],
    'DUB': ['DUB'],
    'CPH': ['CPH'],
    'OSL': ['OSL', 'TRF'],
    'HEL': ['HEL'],
    'WAW': ['WAW', 'WMI'],
    'PRG': ['PRG'],
    'BUD': ['BUD'],
    'ATH': ['ATH'],
    'LIS': ['LIS'],
    'OPO': ['OPO'],
    'DXB': ['DXB', 'DWC'],
    'DOH': ['DOH'],
    'AUH': ['AUH'],
    'SIN': ['SIN'],
    'BKK': ['BKK', 'DMK'],
    'KUL': ['KUL', 'SZB'],
    'HKG': ['HKG'],
    'SYD': ['SYD'],
    'MEL': ['MEL', 'AVV'],
    'LAX': ['LAX', 'BUR', 'LGB', 'SNA', 'ONT'],
    'SFO': ['SFO', 'OAK', 'SJC'],
    'MIA': ['MIA', 'FLL', 'PBI'],
    'DFW': ['DFW', 'DAL'],
    'IAH': ['IAH', 'HOU'],
    'SEA': ['SEA'],
    'BOS': ['BOS'],
    'ATL': ['ATL'],
    'DEN': ['DEN'],
    'PHX': ['PHX', 'AZA'],
    'LAS': ['LAS'],
}

# Inverso: aeroporto commerciale -> codice città di appartenenza
AIRPORT_TO_CITY_CODE: dict[str, str] = {}
for city_code, airports in CITY_TO_COMMERCIAL_AIRPORTS.items():
    for ap in airports:
        AIRPORT_TO_CITY_CODE[ap] = city_code

# Includi anche gli alias per risoluzione rapida
for alias, primary in GA_AND_CLOSED_ALIASES.items():
    if primary in AIRPORT_TO_CITY_CODE:
        AIRPORT_TO_CITY_CODE[alias] = AIRPORT_TO_CITY_CODE[primary]

# ── 4. NOMI PULITI E RICONOSCIBILI ────────────────────────────────────────────
CLEAN_CITY_NAMES: dict[str, str] = {
    'CHI': 'Chicago',
    'ORD': 'Chicago',
    'MDW': 'Chicago',
    'SIA': "Xi'an",
    'XIY': "Xi'an",
    'ORL': 'Orlando',
    'MCO': 'Orlando',
    'SFB': 'Orlando',
    'FMY': 'Fort Myers',
    'RSW': 'Fort Myers',
    'IST': 'Istanbul',
    'SAW': 'Istanbul',
    'ISL': 'Istanbul',
    'MEX': 'Città del Messico',
    'NLU': 'Città del Messico',
    'SPK': 'Sapporo',
    'CTS': 'Sapporo',
    'OKD': 'Sapporo',
    'TYO': 'Tokyo',
    'HND': 'Tokyo',
    'NRT': 'Tokyo',
    'PAR': 'Parigi',
    'CDG': 'Parigi',
    'ORY': 'Parigi',
    'BVA': 'Parigi',
    'LON': 'Londra',
    'LHR': 'Londra',
    'LGW': 'Londra',
    'STN': 'Londra',
    'LTN': 'Londra',
    'LCY': 'Londra',
    'SEN': 'Londra',
    'NYC': 'New York',
    'JFK': 'New York',
    'LGA': 'New York',
    'EWR': 'New York',
    'ROM': 'Roma',
    'FCO': 'Roma',
    'CIA': 'Roma',
    'MIL': 'Milano',
    'MXP': 'Milano',
    'LIN': 'Milano',
    'BGY': 'Milano',
    'BJS': 'Pechino',
    'PEK': 'Pechino',
    'PKX': 'Pechino',
    'SHA': 'Shanghai',
    'PVG': 'Shanghai',
    'MOW': 'Mosca',
    'SVO': 'Mosca',
    'DME': 'Mosca',
    'VKO': 'Mosca',
    'ZIA': 'Mosca',
    'ANK': 'Ankara',
    'ESB': 'Ankara',
    'DKR': 'Dakar',
    'DSS': 'Dakar',
    'NHA': 'Nha Trang',
    'CXR': 'Cam Ranh',
    'RTW': 'Saratov',
    'GSV': 'Saratov',
    'MES': 'Medan',
    'KNO': 'Medan',
    'ALY': 'Alessandria',
    'HBE': 'Alessandria',
    'MKC': 'Kansas City',
    'MCI': 'Kansas City',
    'SAC': 'Sacramento',
    'SMF': 'Sacramento',
}

CLEAN_AIRPORT_NAMES: dict[str, str] = {
    'ORD': "O'Hare",
    'MDW': 'Midway',
    'MCO': 'Orlando International',
    'SFB': 'Orlando Sanford',
    'RSW': 'Southwest Florida',
    'XIY': 'Xianyang',
    'ESB': 'Esenboga',
    'DSS': 'Blaise Diagne',
    'LHR': 'Heathrow',
    'LGW': 'Gatwick',
    'STN': 'Stansted',
    'LTN': 'Luton',
    'LCY': 'London City',
    'SEN': 'Southend',
    'CDG': 'Charles de Gaulle',
    'ORY': 'Orly',
    'BVA': 'Beauvais',
    'JFK': 'John F. Kennedy',
    'LGA': 'LaGuardia',
    'EWR': 'Newark Liberty',
    'FCO': 'Fiumicino',
    'CIA': 'Ciampino',
    'MXP': 'Malpensa',
    'LIN': 'Linate',
    'BGY': 'Orio al Serio',
    'IST': 'Istanbul',
    'SAW': 'Sabiha Gokcen',
    'HND': 'Haneda',
    'NRT': 'Narita',
    'CXR': 'Cam Ranh',
    'GSV': 'Gagarin',
    'KNO': 'Kualanamu',
    'HBE': 'Borg El Arab',
    'MCI': 'Kansas City Intl',
    'SMF': 'Sacramento Intl',
}


# ── 5. FUNZIONI DI CONVALIDA E AUTORITÀ ────────────────────────────────────────

def is_city_or_metro(iata: str) -> bool:
    """Verifica se il codice IATA rappresenta una città o area metropolitana e non un aeroporto."""
    if not isinstance(iata, str):
        return False
    code = iata.strip().upper()
    return code in CITY_OR_METRO_CODES


def is_ga_or_non_commercial(iata: str) -> bool:
    """Verifica se il codice rappresenta un aeroporto non commerciale (GA, militare, chiuso)."""
    if not isinstance(iata, str):
        return False
    return iata.strip().upper() in GA_AND_CLOSED_ALIASES


def is_commercial_airport(iata: str) -> bool:
    """Verifica se il codice IATA rappresenta un vero aeroporto commerciale di linea.
    
    Rifiuta:
    - Codici città / metropolitan area (es. CHI, LON, NYC).
    - Aeroporti non commerciali / GA / chiusi (es. ORL, FMY, SIA, ANK).
    """
    if not isinstance(iata, str) or len(iata) != 3:
        return False
    code = iata.strip().upper()
    if code in CITY_OR_METRO_CODES or code in GA_AND_CLOSED_ALIASES:
        return False
    return True


def canonical_city_code(iata: str) -> str:
    """Restituisce il codice città canonico associato all'aeroporto per il raggruppamento."""
    code = (iata or '').strip().upper()
    # Se è un aeroporto registrato in una città conosciuta, restituisci il codice città
    if code in AIRPORT_TO_CITY_CODE:
        return AIRPORT_TO_CITY_CODE[code]
    return code


def resolve_commercial_airport(iata: str) -> Optional[str]:
    """Risolve un codice IATA verso il suo aeroporto commerciale effettivo.
    
    - Se è già un aeroporto commerciale, restituisce se stesso.
    - Se è un alias / GA univoco (es. ORL -> MCO, SIA -> XIY), restituisce l'aeroporto commerciale.
    - Se è un codice città multi-aeroporto ambiguo (es. CHI, LON), restituisce None.
    """
    if not isinstance(iata, str):
        return None
    code = iata.strip().upper()
    if code in GA_AND_CLOSED_ALIASES:
        return GA_AND_CLOSED_ALIASES[code]
    if code in CITY_TO_COMMERCIAL_AIRPORTS:
        airports = CITY_TO_COMMERCIAL_AIRPORTS[code]
        if len(airports) == 1:
            return airports[0]
        # Multi-airport hub: ambiguo
        return None
    if code in CITY_OR_METRO_CODES:
        return None
    return code


def get_clean_city_name(iata: str, default: str = '') -> str:
    """Restituisce il nome pulito e riconoscibile della città."""
    code = (iata or '').strip().upper()
    if code in CLEAN_CITY_NAMES:
        return CLEAN_CITY_NAMES[code]
    city_code = canonical_city_code(code)
    if city_code in CLEAN_CITY_NAMES:
        return CLEAN_CITY_NAMES[city_code]
    return default or code


def get_clean_airport_name(iata: str, default: str = '') -> str:
    """Restituisce il nome pulito dell'aeroporto."""
    code = (iata or '').strip().upper()
    if code in CLEAN_AIRPORT_NAMES:
        return CLEAN_AIRPORT_NAMES[code]
    return default or code
