"""Shared constants for smoke tests (destinations.csv row 2 — Paris)."""

PARIS_LAT = 48.857
PARIS_LNG = 2.352

FLIGHT_FROM = "Manchester"
FLIGHT_TO = "Barcelona"
FLIGHT_DATE = "20/07/2026"

LLM_PROMPT = "I want a warm beach holiday with good nightlife and seafood."

WIKIVOYAGE_PAGE = "Paris"
WIKIVOYAGE_SECTION = "See"
# Landmark we expect to appear in the Paris "See" section HTML — grounds the
# assertion that real Wikivoyage content came back rather than the placeholder.
WIKIVOYAGE_NEEDLE = "Eiffel"

SUMMARISE_TAB_TYPE = "see"

KRAKOW_SEE_RAW = """\
    Individual listings can be found in Kraków's district articles

    1 Wawel Wawel Castle on Wikipedia at the south tip of Old Town is a citadel perched on a crag. Within are the cathedral, and the Royal Castle which has several museum galleries and collections.
    2 Main Market Square (Rynek Główny) is the grand centre of Old Town, with St Mary's Basilica and the Cloth Hall. The town walls have gone except for the bastions on its north flank.
    3 Kazimierz was the Jewish quarter. The best of it is around Szeroka, with the Remuh synagogue and atmospheric old cemetery.
    Museums are run by either the National or the City museum.

    - The 4 National Museum main building is at the foot of Aleja 3 Maja in west Kraków, ten minutes walk from Old Town. Other branches, all within Old Town, are Sukiennice Gallery, Czapski Museum and Pavilion, Matejko House, Szolayski House, Czartoryski Museum, Czartoryski Library, Menhoffer House, Erazm Ciolek Palace, and the Europeum Centre.
    - The Museum of Krakow or City Museum runs Krzysztofory Palace, Old Synagogue, Oscar Schindler's Enamel Factory, Eagle Pharmacy, Pomorska Street, Hipolit House, Town Hall Tower, the walls (including Barbican, Florian Gate and Celestat), Nowa Huta, Nowa Huta underground, Zwierzyniec House, Rynek Underground, Theatre Museum, Thesaurus Crocovensis, Podgorze, KL Plaszow and Rydlowka.
    - These are all rich, fascinating collections. To pick one highlight from so many: the Lady with an Ermine is an authentic Leonardo da Vinci portrait (in Polish Dama z gronostajem). She's been shunted hither and yon across Europe but nowadays resides in the Princes Czartoryski Museum just inside the Old Town walls.

    Nowa Huta was built in Communist times for the workforce of the colossal steelworks there. It's a monument to their crass central planning, with huge buildings surrounding green parks. The Polish Aviation Museum is in this area, 5 km northeast of the centre.
    Auschwitz-Birkenau is a simple day-trip from Kraków - lots of tours go there, but you can easily do it independently. It had offshoots all over the region, including a concentration camp in Podgórze district."""
