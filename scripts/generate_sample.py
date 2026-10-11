#!/usr/bin/env python3
"""Generate the sample datasets: `samples/sample.csv` (50,000 articles, the benchmark set)
and the nested subsets the UI offers (sample-50/500/5000/15000/30000.csv), plus
`samples/manifest.json` describing them.

    python3 scripts/generate_sample.py                     # everything, into samples/
    python3 scripts/generate_sample.py --rows 2000 --out-dir /tmp/s

Deterministic (fixed seed): the same command always writes the same file, so benchmark
numbers are comparable across runs and machines.

Shape, chosen to look like an OSINT feed and to exercise every module:
* Every row is a full article of 300-1,500 words (log-normal, median ~650), like real
  news: a unique dateline and lead, then body paragraphs in the same language.
* ~60% of rows belong to *stories*: one generated event (flood, cyber attack, protest,
  summit, arrest, ...) reported 1-4 times by different outlets, often in different
  languages, sharing the same people, places and figures. That is what event coreference
  must recover, and the `story` column is its ground truth.
* The rest: opinion and propaganda pieces (some abusive), features, ads, scams,
  recruitment and mobilization calls.
* Languages: ro, en, ru, uk, fr, de, hu; the `lang` column is the ground truth.

All people and organizations-with-people are fictional; institutions and places are real
names used in invented events dated 2027.
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))  # sample_corpus
SEED = 20271011

FIRST = ["Andrei", "Elena", "Mihai", "Ioana", "Radu", "Ana", "Cristian", "Maria", "Bogdan", "Irina", "Vlad",
         "Raluca", "Sorin", "Diana", "Tudor", "Oana", "Paul", "Alina", "Dan", "Corina", "Victor", "Laura",
         "Florin", "Simona", "Adrian", "Monica", "George", "Roxana", "Marius", "Cătălina", "Ionuț", "Gabriela",
         "Ștefan", "Bianca", "Lucian", "Mirela", "Octavian", "Delia", "Horia", "Teodora", "Emil", "Silvia",
         "Liviu", "Andreea", "Petru", "Larisa", "Sebastian", "Carmen", "Nicolae", "Daria", "Viorel", "Lavinia",
         "Costin", "Smaranda", "Eugen", "Adela", "Matei", "Iulia", "Valentin", "Camelia"]
LAST = ["Popescu", "Ionescu", "Marin", "Stan", "Dumitru", "Toma", "Neagu", "Vlad", "Ilie", "Constantin",
        "Georgescu", "Stoica", "Munteanu", "Moldovan", "Lungu", "Barbu", "Rusu", "Ene", "Matei", "Cristea",
        "Florea", "Dobre", "Nistor", "Oprea", "Sandu", "Mocanu", "Preda", "Pavel", "Tudor", "Gheorghe",
        "Voicu", "Ardeleanu", "Manole", "Bălan", "Petrescu", "Radu", "Mihăilescu", "Coman", "Enache", "Dinu",
        "Lazăr", "Nedelcu", "Pop", "Zamfir", "Tănase", "Iordache", "Avram", "Căpraru", "Drăgan", "Sârbu",
        "Vasilescu", "Ungureanu", "Cozma", "Bogdan", "Anghel", "Grigore", "Vlădescu", "Roman", "Pârvu", "Husar",
        "Stanciu", "Mitrea", "Olteanu", "Pană", "Rotaru", "Simion", "Tache", "Ursu", "Vasile", "Zaharia",
        "Bucur", "Chiriac", "Dragomir", "Fărcaș", "Ghiță", "Iancu", "Jitaru", "Lupu", "Mazilu", "Nica"]

# city: (county, ru, uk, hu) -- foreign names as those outlets would write them
CITIES = {
    "Galați": ("Galați", "Галац", "Галац", "Galac"), "Iași": ("Iași", "Яссы", "Ясси", "Jászvásár"),
    "Cluj-Napoca": ("Cluj", "Клуж-Напока", "Клуж-Напока", "Kolozsvár"), "Timișoara": ("Timiș", "Тимишоара", "Тімішоара", "Temesvár"),
    "Constanța": ("Constanța", "Констанца", "Констанца", "Konstanca"), "Brașov": ("Brașov", "Брашов", "Брашов", "Brassó"),
    "Craiova": ("Dolj", "Крайова", "Крайова", "Krajova"), "Suceava": ("Suceava", "Сучава", "Сучава", "Szucsáva"),
    "Oradea": ("Bihor", "Орадя", "Орадя", "Nagyvárad"), "Sibiu": ("Sibiu", "Сибиу", "Сібіу", "Nagyszeben"),
    "Ploiești": ("Prahova", "Плоешти", "Плоєшті", "Ploiești"), "Bacău": ("Bacău", "Бакэу", "Бакеу", "Bákó"),
    "Pitești": ("Argeș", "Питешти", "Пітешті", "Pitești"), "Arad": ("Arad", "Арад", "Арад", "Arad"),
    "Tulcea": ("Tulcea", "Тулча", "Тульча", "Tulcsa"), "Baia Mare": ("Maramureș", "Бая-Маре", "Бая-Маре", "Nagybánya"),
    "Brăila": ("Brăila", "Брэила", "Бреїла", "Brăila"), "Buzău": ("Buzău", "Бузэу", "Бузеу", "Bodzavásár"),
    "Satu Mare": ("Satu Mare", "Сату-Маре", "Сату-Маре", "Szatmárnémeti"), "Botoșani": ("Botoșani", "Ботошани", "Ботошані", "Botosány"),
}
HOSPITAL_KINDS = ["Spitalul Județean", "Spitalul de Urgență", "Institutul Oncologic", "Spitalul de Copii"]
COMPANIES = ["Electrica", "Romgaz", "Hidroelectrica", "Banca Transilvania", "Digi", "Dacia", "Petrom", "Transgaz",
             "Nuclearelectrica", "Bursa de Valori București", "Alro", "Teraplast", "Medlife", "Purcari", "Sphera"]
GANGS = ["LockNest", "BlackHarbor", "NullTide", "CrimsonByte", "SilentHydra", "VoidFang", "IronMoth", "GreyLynx"]
TEAMS = ["FC Dinamo București", "FCSB", "CFR Cluj", "Universitatea Craiova", "Rapid București", "Farul Constanța",
         "FC Botoșani", "Petrolul Ploiești", "UTA Arad", "Oțelul Galați", "Sepsi OSK", "FC Hermannstadt"]
COUNTRIES_EN = ["Ukraine", "Moldova", "Poland", "Bulgaria", "Hungary", "Serbia", "Georgia", "Turkey"]
DAYS = {"ro": ["luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "ru": ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"],
        "uk": ["у понеділок", "у вівторок", "у середу", "у четвер", "у п'ятницю", "у суботу", "у неділю"],
        "hu": ["hétfőn", "kedden", "szerdán", "csütörtökön", "pénteken", "szombaton", "vasárnap"]}

_RO2CYR = str.maketrans({"a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х", "i": "и",
                         "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р", "s": "с",
                         "t": "т", "u": "у", "v": "в", "z": "з", "ă": "э", "â": "ы", "î": "ы", "ș": "ш", "ț": "ц",
                         "A": "А", "B": "Б", "C": "К", "D": "Д", "E": "Е", "F": "Ф", "G": "Г", "H": "Х", "I": "И",
                         "L": "Л", "M": "М", "N": "Н", "O": "О", "P": "П", "R": "Р", "S": "С", "Ș": "Ш", "T": "Т",
                         "Ț": "Ц", "U": "У", "V": "В", "Z": "З", "x": "кс", "y": "й", "w": "в", "q": "к"})


def cyr(name: str) -> str:
    return name.translate(_RO2CYR)


# ------------------------------------------------------------------ story templates
# Each story kind: a slot generator + per-language report templates. {slots} are shared by
# every report of one story, which is exactly what makes them the same event.

def _flood(r):
    city = r.choice(list(CITIES))
    return {"city": city, "county": CITIES[city][0], "ru_city": CITIES[city][1], "uk_city": CITIES[city][2],
            "hu_city": CITIES[city][3], "homes": r.randint(40, 900), "evac": r.randint(20, 400)}


def _cyber(r):
    city = r.choice(list(CITIES))
    return {"city": city, "ru_city": CITIES[city][1], "uk_city": CITIES[city][2], "hu_city": CITIES[city][3],
            "gang": r.choice(GANGS), "hospital": f"{r.choice(HOSPITAL_KINDS)} {city}", "n": r.randint(2, 9),
            "ransom": r.randint(1, 9)}


def _protest(r):
    city = r.choice(list(CITIES))
    who = r.choice([("profesori", "teachers", "enseignants", "Lehrer", "учителей", "вчителів", "tanár"),
                    ("medici", "doctors", "médecins", "Ärzte", "врачей", "лікарів", "orvos"),
                    ("fermieri", "farmers", "agriculteurs", "Landwirte", "фермеров", "фермерів", "gazda"),
                    ("mineri", "miners", "mineurs", "Bergleute", "шахтёров", "шахтарів", "bányász")])
    return {"city": city, "ru_city": CITIES[city][1], "uk_city": CITIES[city][2], "hu_city": CITIES[city][3],
            "who": who, "n": r.randint(2, 40) * 500}


def _summit(r):
    return {"country": r.choice(COUNTRIES_EN), "n": r.randint(2, 6),
            "system": r.choice(["Patriot", "IRIS-T", "NASAMS", "SAMP/T"])}


def _arrest(r):
    city = r.choice(list(CITIES))
    return {"city": city, "n": r.randint(2, 12), "crime": r.choice([
        ("evaziune fiscală", "tax evasion"), ("trafic de droguri", "drug trafficking"),
        ("contrabandă cu țigări", "cigarette smuggling"), ("fraudă cu fonduri europene", "EU funds fraud")]),
        "amount": r.randint(2, 90)}


def _fire(r):
    city = r.choice(list(CITIES))
    return {"city": city, "company": r.choice(COMPANIES), "hurt": r.randint(0, 6)}


def _match(r):
    a, b = r.sample(TEAMS, 2)
    ga, gb = r.randint(0, 4), r.randint(0, 3)
    if ga == gb:
        ga += 1
    return {"a": a, "b": b, "ga": ga, "gb": gb, "minute": r.randint(5, 90)}


def _results(r):
    return {"company": r.choice(COMPANIES), "pct": r.randint(3, 48), "profit": r.randint(20, 900)}


def _outbreak(r):
    city = r.choice(list(CITIES))
    return {"city": city, "county": CITIES[city][0], "n": r.randint(12, 240),
            "disease": r.choice([("rujeolă", "measles"), ("gripă aviară", "avian flu"), ("hepatită A", "hepatitis A")])}


STORY_KINDS = {
    "flood": (_flood, {
        "ro": ["Inundațiile din județul {county} au afectat {homes} de gospodării din {city}. {person}, purtător de cuvânt al ISU {county}, a anunțat {day} că {evac} de persoane au fost evacuate.",
               "Cod roșu de inundații la {city}: {homes} de case sub ape, {evac} de oameni evacuați. „Situația este critică”, a declarat {person} de la ISU {county}."],
        "en": ["Floods in Romania's {county} county damaged {homes} homes in {city} on {day}. {person}, a spokesperson for the emergency service ISU {county}, said {evac} people were evacuated."],
        "fr": ["Des inondations dans le département de {county}, en Roumanie, ont endommagé {homes} maisons à {city}. {evac} personnes ont été évacuées, a indiqué {person}."],
        "de": ["Überschwemmungen im rumänischen Kreis {county} haben in {city} {homes} Häuser beschädigt. {evac} Menschen wurden evakuiert, sagte {person}."],
        "ru": ["Наводнение в румынском городе {ru_city} повредило {homes} домов, {evac} человек эвакуированы, сообщил {person_cyr}."],
        "uk": ["Повінь у румунському місті {uk_city} пошкодила {homes} будинків, {evac} людей евакуювали, повідомив {person_cyr}."],
        "hu": ["Árvíz sújtotta {hu_city} városát: {homes} ház megrongálódott, {evac} embert kitelepítettek – közölte {person}."],
    }),
    "cyber": (_cyber, {
        "ro": ["Directoratul Național de Securitate Cibernetică a emis {day} o alertă după un atac ransomware asupra {hospital}. Grupul {gang} revendică atacul și cere {ransom} milioane de euro.",
               "Atac cibernetic la {hospital}: sistemele informatice sunt blocate de {n} zile. DNSC confirmă că grupul {gang} se află în spatele atacului, a declarat {person}."],
        "en": ["Romania's cyber agency DNSC issued an alert on {day} after a ransomware attack hit {hospital} in {city}. The {gang} group claimed the attack and demands {ransom} million euros."],
        "de": ["Die rumänische Cyberbehörde DNSC warnte am {day} vor einem Ransomware-Angriff auf das Krankenhaus in {city}. Die Gruppe {gang} bekannte sich zu dem Angriff."],
        "fr": ["L'agence roumaine de cybersécurité DNSC a signalé {day} une attaque par rançongiciel contre un hôpital de {city}, revendiquée par le groupe {gang}."],
        "ru": ["Хакерская группа {gang} атаковала больницу в городе {ru_city}, сообщило румынское агентство DNSC."],
    }),
    "protest": (_protest, {
        "ro": ["Peste {n} de {who[0]} au protestat {day} în centrul orașului {city}, cerând salarii mai mari. Liderul sindical {person} a anunțat grevă generală.",
               "Protest de amploare la {city}: {n} de {who[0]} au ieșit în stradă. „Nu ne oprim până nu suntem ascultați”, a spus {person}."],
        "en": ["More than {n} {who[1]} rallied in {city} on {day} demanding higher pay. Union leader {person} announced a general strike."],
        "fr": ["Plus de {n} {who[2]} ont manifesté {day} à {city} pour réclamer des hausses de salaire, à l'appel du syndicaliste {person}."],
        "de": ["Mehr als {n} {who[3]} haben am {day} in {city} für höhere Löhne demonstriert. Gewerkschaftschef {person} kündigte einen Generalstreik an."],
        "uk": ["Понад {n} {who[5]} протестували в місті {uk_city}, вимагаючи підвищення зарплат, повідомив профспілковий лідер {person_cyr}."],
        "hu": ["Több mint {n} {who[6]} tüntetett {day} {hu_city} központjában magasabb béreket követelve; {person} szakszervezeti vezető általános sztrájkot jelentett be."],
    }),
    "summit": (_summit, {
        "en": ["NATO defence ministers met in Brussels on {day} to discuss air defence for {country}. Deputy Secretary General {person} said allies would deliver {n} more {system} systems.",
               "Allies agreed in Brussels to send {n} additional {system} batteries to {country}, NATO official {person} told reporters on {day}."],
        "ro": ["Miniștrii apărării din NATO s-au reunit {day} la Bruxelles pentru a discuta apărarea antiaeriană a {country}. Adjunctul secretarului general, {person}, a anunțat {n} noi sisteme {system}."],
        "fr": ["Les ministres de la Défense de l'OTAN se sont réunis {day} à Bruxelles; {person} a annoncé {n} systèmes {system} supplémentaires pour {country}."],
        "de": ["Die NATO-Verteidigungsminister haben am {day} in Brüssel über Luftverteidigung für {country} beraten; {person} kündigte {n} weitere {system}-Systeme an."],
    }),
    "arrest": (_arrest, {
        "ro": ["Procurorii DIICOT au reținut {day} {n} persoane suspectate de {crime[0]} în județul {city}. Prejudiciul este estimat la {amount} milioane de lei, a precizat {person}.",
               "Percheziții la {city} într-un dosar de {crime[0]}: {n} suspecți au fost duși la audieri. Purtătorul de cuvânt {person} vorbește de un prejudiciu de {amount} milioane de lei."],
        "en": ["Romanian prosecutors detained {n} people in {city} on {day} in a {crime[1]} case with estimated losses of {amount} million lei, spokesperson {person} said."],
    }),
    "fire": (_fire, {
        "ro": ["Un incendiu a izbucnit {day} la o hală a companiei {company} din {city}. {hurt} angajați au fost răniți, potrivit ISU, a declarat {person}.",
               "Explozie urmată de incendiu la fabrica {company} din {city}: pompierii au intervenit cu 12 autospeciale. Directorul {person} spune că producția este oprită."],
        "en": ["A fire broke out on {day} at a {company} plant in {city}, Romania. {hurt} workers were injured, plant director {person} said."],
    }),
    "match": (_match, {
        "ro": ["{a} a învins {b}, scor {ga}-{gb}, după un gol marcat de {person} în minutul {minute}.",
               "Victorie pentru {a} în meciul cu {b}: {ga}-{gb}. Decisiv a fost {person}, care a înscris în minutul {minute}."],
        "en": ["{a} beat {b} {ga}-{gb}, with {person} scoring in the {minute}th minute."],
        "hu": ["A {a} {ga}-{gb} arányban legyőzte a {b} csapatát; {person} a(z) {minute}. percben szerzett gólt."],
    }),
    "results": (_results, {
        "ro": ["Acțiunile {company} au crescut cu {pct}% după ce compania a raportat un profit trimestrial de {profit} milioane de lei. CEO-ul {person} a anunțat dividende record.",
               "{company} raportează profit de {profit} milioane de lei, în creștere cu {pct}%. „Investițiile încep să dea roade”, a spus directorul general {person}."],
        "en": ["Shares of {company} rose {pct}% after the company reported quarterly profit of {profit} million lei. CEO {person} announced a record dividend."],
        "de": ["Die Aktie von {company} stieg um {pct} Prozent, nachdem das Unternehmen einen Quartalsgewinn von {profit} Millionen Lei meldete, so Konzernchef {person}."],
    }),
    "outbreak": (_outbreak, {
        "ro": ["Ministerul Sănătății a confirmat un focar de {disease[0]} în județul {county}: {n} de cazuri la {city}. Medicul {person} recomandă vaccinarea.",
               "Alertă sanitară la {city}: {n} de cazuri de {disease[0]}. DSP {county} a declanșat ancheta epidemiologică, a anunțat {person}."],
        "en": ["Romania's health ministry confirmed a {disease[1]} outbreak in {city}, with {n} cases so far, epidemiologist {person} said."],
    }),
}

# ------------------------------------------------------------------ standalone posts
STANDALONE = [
    ("ro", "ro-blog", 3, "Trădătorii de la București ne vând țara bucată cu bucată! Doar un adevărat patriot mai poate salva România de elita coruptă și de stăpânii ei de la Bruxelles!"),
    ("ro", "ro-blog", 3, "Dacă nu închidem granițele acum, peste zece ani nu va mai exista o Românie. Nu există cale de mijloc: ori cu noi, ori cu ei."),
    ("ro", "ro-blog", 2, "Experții independenți spun clar: noul vaccin a fost testat prea puțin. Ce ne ascund autoritățile? De ce nu răspunde nimeni, domnule {person}?"),
    ("en", "en-blog", 3, "Either we close the borders tomorrow or our nation disappears within ten years. There is no middle ground, and anyone who says otherwise wants us gone."),
    ("en", "en-blog", 2, "Millions of people already switched to our movement. Everyone is joining. Don't be the last one left behind."),
    ("en", "en-blog", 2, "They call it a reform. We call it what it is: theft. {person} and his cronies are robbing the nation in broad daylight."),
    ("ru", "ru-channel", 3, "Западные СМИ снова лгут. А как насчёт их собственных войн? Почему никто не спрашивает об Ираке? Пусть сначала посмотрят на себя."),
    ("ru", "ru-channel", 2, "Только наивные люди верят официальной статистике. Правду от вас скрывают, а {person_cyr} молчит."),
    ("uk", "uk-channel", 2, "Слава нашим героям! Разом переможемо! Кожен, хто любить Батьківщину, має стати на її захист."),
    ("ro", "ro-channel", 2, "Te alături voluntarilor noștri? Batalionul de voluntari caută bărbați între 18 și 45 de ani. Scrie-ne în privat, oferim echipament și instruire."),
    ("en", "en-social", 2, "Everyone to the main square in {city} this Saturday at 6 pm! Bring your friends, bring flags. If we stay home, nothing changes. Share this post!"),
    ("ro", "ro-social", 2, "Ajutați-l pe {first}, 7 ani, să ajungă la operația din Viena! Orice donație contează. Detalii la Asociația Speranța din {city}."),
    ("en", "en-ad", 3, "Summer sale at TechNova: 30% off all laptops until Sunday. Free delivery across Romania. Order now at our stores in {city}!"),
    ("ro", "ro-ad", 3, "Reduceri de până la 50% la mobilierul de grădină! Doar în acest weekend, în magazinele noastre din {city}. Livrare gratuită."),
    ("ro", "ro-sms", 2, "Contul dumneavoastră a fost suspendat. Pentru reactivare accesați urgent linkul verificare-cont-banca.info și introduceți datele cardului."),
    ("en", "en-sms", 2, "Your parcel could not be delivered. Pay the 1.99 EUR customs fee within 24 hours at parcel-track-ro.info or it will be returned."),
    ("en", "en-social", 1, "We know where you live, {person}. Keep writing about our business and you will regret it. This is the last warning."),
    ("ro", "ro-comment", 3, "Ești un idiot și jumătate, nu știi nimic despre economie, du-te și învață înainte să mai scrii prostii."),
    ("en", "en-comment", 2, "These people are parasites. They should all be thrown out of the country, they bring nothing but crime."),
    ("en", "en-comment", 2, "What a load of crap, this damn article is a total waste of my time."),
    ("ro", "ro-comment", 4, "Articol excelent, mulțumesc pentru documentare! Ar fi util și un grafic cu evoluția prețurilor."),
    ("en", "en-comment", 3, "Great reporting, thank you. Would love a follow-up on how this affects small businesses in {city}."),
    ("ro", "ro-mag", 3, "Festivalul de film de la {city} revine în septembrie, cu peste 120 de proiecții și invitați din 30 de țări."),
    ("en", "en-mag", 3, "Ten hidden beaches on the Black Sea coast you should visit this summer, from Vama Veche to Sfântu Gheorghe."),
    ("fr", "fr-mag", 2, "Week-end à {city}: nos dix adresses préférées pour découvrir la gastronomie roumaine."),
    ("de", "de-mag", 2, "Wandern in den Karpaten: Die schönsten Routen rund um {city} für Anfänger und Profis."),
    ("hu", "hu-news", 2, "A kolozsvári egyetem kutatói új módszert fejlesztettek ki a gabonafélék szárazságtűrésének javítására, közölte {person} projektvezető."),
    ("ro", "ro-news", 3, "Parlamentul a adoptat legea privind protecția datelor în sectorul energetic, care obligă operatorii să raporteze incidentele cibernetice în 24 de ore."),
    ("en", "en-wire", 3, "Moldova and the European Union signed an agreement in Chișinău to connect Moldova's power grid to the EU market by 2028."),
    ("ro", "ro-opinion", 3, "Reforma pensiilor nu poate fi amânată la nesfârșit. Fără decizii curajoase, deficitul va continua să crească, scrie economistul {person}."),
]

def _person(r):
    return f"{r.choice(FIRST)} {r.choice(LAST)}"




def _fill(template: str, slots: dict, lang: str, r: random.Random) -> str:
    return template.format(**slots, day=r.choice(DAYS[lang]))


SUBSETS = (50, 500, 5_000, 15_000, 30_000)
ORGS = ["Institutul Național de Statistică", "Curtea de Conturi", "Consiliul Concurenței", "ANRE", "ANPC",
        "Banca Națională a României", "Agenția Națională de Administrare Fiscală", "Inspectoratul Școlar",
        "Direcția de Sănătate Publică", "Garda de Mediu", "Agenția pentru Protecția Mediului"]
OPINION_SOURCES = ("blog", "channel", "opinion", "comment")
FEATURE_SOURCES = ("mag",)


def _target_words(r: random.Random) -> int:
    """Real news lengths: log-normal around ~650 words, clipped to 300-1,500."""
    return max(300, min(1500, int(r.lognormvariate(6.48, 0.42))))


def _article(r: random.Random, lang: str, lead: str, banks: list[list[str]], slots: dict) -> str:
    """Dateline + lead, then body paragraphs until the target length (never over 1,500 words)."""
    city = slots.get("city") or r.choice(list(CITIES))
    dateline = f"{city.upper()}, {r.randint(1, 28):02d}.{r.randint(1, 12):02d}.2027 – "
    paras = [dateline + lead]
    words, target = len(paras[0].split()), _target_words(r)
    pool = [p for bank in banks for p in bank]
    while words < target:
        person2 = _person(r)
        fill = {"city": city, "county": CITIES.get(city, (city,))[0], "org": r.choice(ORGS),
                "company": r.choice(COMPANIES), "num": r.randint(2, 95), "pct": r.randint(3, 72),
                "year": r.randint(2019, 2026), "person": slots.get("person", _person(r)),
                "person2": person2, "person2_cyr": cyr(person2)}
        p = r.choice(pool).format(**fill)
        if words + len(p.split()) > 1500:
            break
        paras.append(p)
        words += len(p.split())
    return "\n\n".join(paras)


def generate(rows: int, seed: int = SEED) -> list[list[str]]:
    from sample_corpus import BODY, FEATURE, OPINION

    r = random.Random(seed)
    out: list[list[str]] = []
    story_n = 0
    while len(out) < rows:
        if r.random() < 0.6:
            # A story: one event reported 1-4 times, by different outlets / in different languages.
            kind = r.choice(list(STORY_KINDS))
            make, templates = STORY_KINDS[kind]
            slots = make(r)
            person = _person(r)
            slots.update(person=person, person_cyr=cyr(person))
            story_n += 1
            sid = f"s{story_n}"
            reports = min(r.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0], rows - len(out))
            langs = list(templates)
            for k in range(reports):
                lang = langs[0] if k == 0 else r.choices(langs, weights=[4 if x in ("ro", "en") else 1 for x in langs])[0]
                lead = _fill(r.choice(templates[lang]), slots, lang, r)
                text = _article(r, lang, lead, [BODY[lang]], slots)
                out.append([str(len(out) + 1), f"{lang}-{'wire' if lang == 'en' else 'news'}", lang, sid, text])
        else:
            lang, src, _, tmpl = r.choices(STANDALONE, weights=[w for *_, w, _ in STANDALONE])[0]
            person = _person(r)
            city = r.choice(list(CITIES))
            lead = tmpl.format(person=person, person_cyr=cyr(person), city=city, first=r.choice(FIRST))
            kind = src.split("-", 1)[1]
            if kind in OPINION_SOURCES:
                banks = [OPINION.get(lang, OPINION["en"]), BODY[lang]]
            elif kind in FEATURE_SOURCES:
                banks = [FEATURE.get(lang, FEATURE["en"])] * 2 + [BODY[lang]]
            else:
                banks = [BODY[lang]]
            text = _article(r, lang, lead, banks, {"city": city, "person": person})
            out.append([str(len(out) + 1), src, lang, "", text])
    return out[:rows]


def _write(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "lang", "story", "text"])
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rows", type=int, default=50_000)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "samples")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    rows = generate(a.rows, a.seed)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    # Nested prefixes of one generation: sample-500 is the first 500 rows of sample.csv, etc.
    for n in [s for s in SUBSETS if s < a.rows] + [a.rows]:
        name = "sample.csv" if n == a.rows else f"sample-{n}.csv"
        part = rows[:n]
        _write(a.out_dir / name, part)
        words = sorted(len(x[4].split()) for x in part)
        manifest.append({"file": name, "rows": n, "ui": n in SUBSETS, "bytes": (a.out_dir / name).stat().st_size,
                         "words_median": words[len(words) // 2], "words_min": words[0], "words_max": words[-1],
                         "languages": sorted({x[2] for x in part}),
                         "stories_multi_report": sum(1 for c in _story_sizes(part).values() if c > 1)})
        print(f"wrote {name}: {n:,} rows, median {words[len(words) // 2]} words, "
              f"{manifest[-1]['bytes'] / 1e6:.1f} MB")
    (a.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _story_sizes(rows: list[list[str]]) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for x in rows:
        if x[3]:
            sizes[x[3]] = sizes.get(x[3], 0) + 1
    return sizes


if __name__ == "__main__":
    main()
