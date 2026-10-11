"""Paragraph banks for `generate_sample.py`: the body text that grows a lead into a full
article of 300-1,500 words.

Slots ({city}, {person}, {person2}, {org}, {company}, {num}, {pct}, {year}, {county}) are
filled per article, so the same paragraph reads differently in different articles. The
prose is synthetic: what matters for benchmarking is that lengths, languages, token counts
and entity density look like real news, not literary variety.
"""

BODY = {
    "ro": [
        "Potrivit datelor publicate de {org}, situația din {city} s-a deteriorat constant în ultimii ani. Experții consultați de redacție spun că problemele nu sunt noi, dar că autoritățile locale au amânat de prea multe ori deciziile importante. „Am avertizat încă din {year} că lucrurile vor ajunge aici”, a declarat {person2}, care a coordonat un studiu pe această temă.",
        "Reprezentanții {org} au transmis că urmăresc evoluția situației și că vor publica un raport detaliat în următoarele săptămâni. Între timp, locuitorii din {city} se plâng că informațiile oficiale ajung greu la ei și că deciziile sunt luate fără consultare publică. Mai mulți consilieri locali au cerut o ședință extraordinară.",
        "Primarul din {city} a declarat că administrația a alocat deja {num} de milioane de lei pentru măsuri urgente și că va solicita sprijin de la Guvern. „Nu putem rezolva singuri o problemă de această amploare”, a spus edilul, care a adăugat că o echipă de specialiști va evalua costurile reale până la sfârșitul lunii.",
        "Datele Institutului Național de Statistică arată că în județul {county} trăiesc peste {num}0.000 de persoane, iar aproape {pct}% dintre acestea locuiesc în mediul rural. Specialiștii atrag atenția că infrastructura din zonele rurale este mult mai vulnerabilă și că investițiile din ultimii ani au fost insuficiente.",
        "Opoziția a criticat dur reacția autorităților. Deputatul {person2} a cerut demisia celor responsabili și a anunțat că va depune o interpelare în Parlament. „Este inacceptabil ca, în {year}, oamenii să fie lăsați singuri în fața unor astfel de situații”, a declarat acesta într-o conferință de presă.",
        "Analiștii economici estimează că impactul asupra economiei locale ar putea depăși {num} de milioane de euro. Firmele din zonă, în special cele mici și mijlocii, au fost cel mai grav afectate, iar unele dintre ele au fost nevoite să își suspende temporar activitatea. Camera de Comerț din {city} a cerut scutiri de taxe.",
        "Ministerul de resort a transmis un comunicat în care precizează că toate instituțiile implicate colaborează și că situația este sub control. Documentul mai arată că au fost mobilizate echipe din mai multe județe și că, dacă va fi nevoie, va fi solicitat sprijin și prin mecanismele europene de cooperare.",
        "La nivel european, Comisia Europeană a anunțat că monitorizează evoluțiile din regiune. Un purtător de cuvânt al instituției a spus că România poate accesa fonduri suplimentare, dar că cererile trebuie depuse în termenele stabilite și însoțite de documentația completă. Procedura durează, de regulă, câteva luni.",
        "Organizațiile neguvernamentale din {city} au organizat deja colecte și au mobilizat voluntari. Președintele unei asociații locale, {person2}, spune că răspunsul comunității a fost impresionant: în doar câteva zile au fost strânse peste {num} de tone de alimente și produse de igienă, distribuite familiilor afectate.",
        "Cercetătorii de la Universitatea din {city} au analizat date din ultimele două decenii și au constatat o creștere clară a frecvenței unor astfel de evenimente. Concluziile lor, publicate într-o revistă de specialitate, arată că fără investiții majore riscurile vor continua să crească în următorii ani.",
        "Sindicatele din sector susțin că angajații lucrează în condiții dificile și că lipsa de personal este una dintre principalele probleme. Liderul sindical {person2} a declarat că, dacă revendicările nu vor fi îndeplinite până la sfârșitul anului, membrii organizației vor intra în grevă de avertisment.",
        "Prefectul județului {county} a convocat Comitetul pentru Situații de Urgență, care a stabilit o serie de măsuri imediate. Printre acestea se numără verificarea tuturor clădirilor publice, suplimentarea echipajelor de intervenție și informarea constantă a populației prin mesaje RO-ALERT.",
        "Reacțiile pe rețelele sociale au fost numeroase. Mii de utilizatori au distribuit imagini și mesaje de solidaritate, însă au circulat și informații false, pe care autoritățile au fost nevoite să le dezmintă. Experții în comunicare recomandă ca oamenii să se informeze doar din surse oficiale.",
        "Bugetul local al municipiului {city} pentru anul {year} prevede investiții de aproximativ {num} de milioane de lei, însă o parte importantă a acestora depinde de atragerea fondurilor europene. Consilierii locali urmează să voteze rectificarea bugetară în ședința de luna viitoare.",
        "Specialiștii în securitate atrag atenția că astfel de incidente devin tot mai frecvente și că instituțiile publice sunt adesea slab pregătite. Un audit realizat anul trecut a arătat că aproape {pct}% dintre instituțiile verificate nu aveau planuri actualizate de răspuns la incidente.",
        "Ancheta este abia la început, iar procurorii nu exclud ca și alte persoane să fie implicate. Surse judiciare citate de presa locală spun că anchetatorii analizează documente din ultimii {num} ani și că au fost audiați deja mai mulți martori, printre care și foști angajați ai instituțiilor implicate.",
    ],
    "en": [
        "According to figures published by {org}, the situation in {city} has deteriorated steadily over recent years. Experts consulted for this article say the problems are not new, but that local authorities have repeatedly postponed key decisions. \"We warned back in {year} that it would come to this,\" said {person2}, who led a study on the subject.",
        "Representatives of {org} said they were following developments closely and would publish a detailed report in the coming weeks. Residents of {city}, meanwhile, complain that official information reaches them slowly and that decisions are taken without public consultation. Several local councillors have called for an extraordinary session.",
        "The mayor of {city} said the administration had already allocated {num} million lei for urgent measures and would ask the government for support. \"We cannot solve a problem of this size on our own,\" the mayor said, adding that a team of specialists would assess the real costs by the end of the month.",
        "National statistics show that more than {num}0,000 people live in {county} county, and almost {pct}% of them in rural areas. Specialists point out that rural infrastructure is far more vulnerable and that investment in recent years has fallen short of what is needed.",
        "The opposition sharply criticised the authorities' response. Lawmaker {person2} called for those responsible to resign and announced a formal question in parliament. \"It is unacceptable that in {year} people are left on their own in situations like this,\" the lawmaker told a press conference.",
        "Economists estimate that the impact on the local economy could exceed {num} million euros. Businesses in the area, especially small and medium-sized firms, were hit hardest, and some have had to suspend operations temporarily. The {city} Chamber of Commerce has asked for tax relief.",
        "The relevant ministry issued a statement saying all institutions involved were cooperating and that the situation was under control. The statement added that teams from several counties had been mobilised and that, if needed, support would be requested through European cooperation mechanisms.",
        "At European level, the European Commission said it was monitoring developments in the region. A Commission spokesperson said Romania could access additional funds, but that applications had to be submitted on time and with complete documentation. The procedure usually takes several months.",
        "Non-governmental organisations in {city} have already organised collections and mobilised volunteers. {person2}, who heads a local association, said the community response had been remarkable: in just a few days more than {num} tonnes of food and hygiene products were collected and distributed to affected families.",
        "Researchers at the University of {city} analysed data from the past two decades and found a clear increase in the frequency of such events. Their conclusions, published in a peer-reviewed journal, show that without major investment the risks will keep rising in the years ahead.",
        "Unions in the sector say staff are working in difficult conditions and that understaffing is one of the main problems. Union leader {person2} said that if their demands are not met by the end of the year, members would hold a warning strike.",
        "The prefect of {county} county convened the emergency committee, which agreed a series of immediate measures. They include inspections of all public buildings, additional response crews and regular public updates through the RO-ALERT system.",
        "Reactions on social media were numerous. Thousands of users shared images and messages of solidarity, but false information also circulated, which the authorities had to deny. Communication experts recommend relying only on official sources.",
        "The {city} municipal budget for {year} provides for investment of around {num} million lei, but a large part of it depends on attracting European funds. Local councillors are due to vote on the budget revision at next month's session.",
        "Security specialists warn that such incidents are becoming more frequent and that public institutions are often poorly prepared. An audit carried out last year found that almost {pct}% of the institutions checked had no up-to-date incident response plans.",
        "The investigation has only just begun, and prosecutors do not rule out that others were involved. Judicial sources quoted by local media say investigators are examining documents covering the past {num} years and have already questioned several witnesses, including former employees.",
    ],
    "fr": [
        "Selon les chiffres publiés par {org}, la situation à {city} s'est détériorée au fil des années. Les experts interrogés estiment que les problèmes ne sont pas nouveaux, mais que les autorités locales ont trop souvent reporté les décisions importantes. « Nous l'avions annoncé dès {year} », affirme {person2}.",
        "Le maire de {city} a indiqué que la municipalité avait déjà débloqué {num} millions de lei pour des mesures d'urgence et qu'elle solliciterait l'aide du gouvernement. Une équipe de spécialistes doit évaluer le coût réel d'ici la fin du mois.",
        "L'opposition a vivement critiqué la réaction des autorités. Le député {person2} a réclamé la démission des responsables et annoncé une question écrite au Parlement, dénonçant une gestion « improvisée » de la crise.",
        "Au niveau européen, la Commission européenne suit l'évolution de la situation. Un porte-parole a précisé que la Roumanie pouvait mobiliser des fonds supplémentaires, à condition de déposer des dossiers complets dans les délais.",
        "Les associations locales ont organisé des collectes et mobilisé des bénévoles. En quelques jours, plus de {num} tonnes de denrées ont été distribuées aux familles touchées, selon {person2}, responsable d'une ONG de {city}.",
        "Les chercheurs de l'université de {city} ont analysé les données des vingt dernières années et constatent une nette augmentation de la fréquence de ces événements. Sans investissements majeurs, préviennent-ils, les risques continueront de croître.",
    ],
    "de": [
        "Nach Angaben von {org} hat sich die Lage in {city} in den vergangenen Jahren stetig verschlechtert. Fachleute betonen, die Probleme seien nicht neu, die Behörden hätten wichtige Entscheidungen jedoch immer wieder vertagt. „Wir haben schon {year} davor gewarnt“, sagte {person2}.",
        "Der Bürgermeister von {city} erklärte, die Stadt habe bereits {num} Millionen Lei für Sofortmaßnahmen bereitgestellt und werde die Regierung um Unterstützung bitten. Ein Expertenteam soll die tatsächlichen Kosten bis Monatsende ermitteln.",
        "Die Opposition kritisierte die Reaktion der Behörden scharf. Der Abgeordnete {person2} forderte den Rücktritt der Verantwortlichen und kündigte eine parlamentarische Anfrage an.",
        "Auf europäischer Ebene beobachtet die Europäische Kommission die Entwicklung. Rumänien könne zusätzliche Mittel beantragen, sagte ein Sprecher, die Anträge müssten jedoch fristgerecht und vollständig eingereicht werden.",
        "Lokale Hilfsorganisationen haben Spenden gesammelt und Freiwillige mobilisiert. Innerhalb weniger Tage seien mehr als {num} Tonnen Lebensmittel verteilt worden, berichtete {person2} von einem Verein in {city}.",
        "Forscher der Universität {city} haben Daten aus zwei Jahrzehnten ausgewertet und eine deutliche Zunahme solcher Ereignisse festgestellt. Ohne große Investitionen würden die Risiken weiter steigen, warnen sie.",
    ],
    "ru": [
        "По данным {org}, ситуация в регионе за последние годы постоянно ухудшалась. Эксперты отмечают, что проблемы не новые, однако местные власти неоднократно откладывали важные решения. «Мы предупреждали об этом ещё в {year} году», — заявил {person2_cyr}.",
        "Мэр города сообщил, что администрация уже выделила {num} миллионов леев на срочные меры и обратится за помощью к правительству. Группа специалистов оценит реальные затраты до конца месяца.",
        "Оппозиция резко раскритиковала действия властей. Депутат {person2_cyr} потребовал отставки ответственных лиц и объявил о запросе в парламент.",
        "На европейском уровне Европейская комиссия следит за развитием ситуации. Представитель комиссии уточнил, что Румыния может получить дополнительные средства при условии своевременной подачи документов.",
        "Местные общественные организации организовали сбор помощи и мобилизовали волонтёров. За несколько дней было собрано более {num} тонн продуктов, сообщил {person2_cyr}.",
        "Исследователи проанализировали данные за последние двадцать лет и обнаружили явный рост частоты подобных событий. Без крупных инвестиций риски будут только расти, предупреждают они.",
    ],
    "uk": [
        "За даними {org}, ситуація в регіоні за останні роки постійно погіршувалася. Експерти наголошують, що проблеми не нові, але місцева влада неодноразово відкладала важливі рішення. «Ми попереджали про це ще у {year} році», — заявив {person2_cyr}.",
        "Мер міста повідомив, що адміністрація вже виділила {num} мільйонів леїв на термінові заходи та звернеться по допомогу до уряду. Група фахівців оцінить реальні витрати до кінця місяця.",
        "Опозиція різко розкритикувала дії влади. Депутат {person2_cyr} вимагав відставки відповідальних осіб і оголосив про депутатський запит.",
        "На європейському рівні Європейська комісія стежить за розвитком подій. Речник комісії уточнив, що Румунія може отримати додаткові кошти за умови вчасного подання документів.",
        "Місцеві громадські організації організували збір допомоги та мобілізували волонтерів. За кілька днів було зібрано понад {num} тонн продуктів, повідомив {person2_cyr}.",
        "Дослідники проаналізували дані за останні двадцять років і виявили чітке зростання частоти подібних подій. Без значних інвестицій ризики лише зростатимуть, попереджають вони.",
    ],
    "hu": [
        "A(z) {org} adatai szerint {city} helyzete az elmúlt években folyamatosan romlott. A szakértők szerint a problémák nem újak, a helyi hatóságok azonban többször elhalasztották a fontos döntéseket. „Már {year}-ben figyelmeztettünk erre” – mondta {person2}.",
        "A polgármester közölte, hogy a város már {num} millió lejt különített el sürgős intézkedésekre, és a kormánytól is támogatást kér. Szakértői csoport méri fel a valós költségeket a hónap végéig.",
        "Az ellenzék élesen bírálta a hatóságok reakcióját. {person2} képviselő a felelősök lemondását követelte, és interpellációt jelentett be a parlamentben.",
        "Európai szinten az Európai Bizottság figyelemmel kíséri a fejleményeket. Egy szóvivő szerint Románia további forrásokat igényelhet, ha a kérelmeket határidőre és hiánytalanul benyújtja.",
        "A helyi civil szervezetek gyűjtést szerveztek és önkénteseket mozgósítottak. Néhány nap alatt több mint {num} tonna élelmiszert osztottak szét az érintett családok között – mondta {person2}.",
        "A kutatók az elmúlt két évtized adatait elemezték, és az ilyen események gyakoriságának egyértelmű növekedését állapították meg. Jelentős beruházások nélkül a kockázatok tovább nőnek – figyelmeztetnek.",
    ],
}

# Opinion pieces: persuasion and propaganda techniques, a few abusive passages.
OPINION = {
    "ro": [
        "Să fim sinceri: nimeni de la București nu se gândește la oamenii obișnuiți. Elitele își împart funcțiile și banii, iar noi plătim nota de plată. De ani de zile ni se spune să avem răbdare, dar răbdarea noastră s-a terminat.",
        "Cine mai crede astăzi declarațiile oficiale? Ni s-a promis creștere, investiții și locuri de muncă, iar realitatea din {city} arată exact opusul. Cifrele sunt cosmetizate, iar cei care pun întrebări incomode sunt imediat etichetați drept dușmani.",
        "Istoria ne arată că popoarele care nu își apără identitatea dispar. Strămoșii noștri au luptat pentru fiecare palmă de pământ, iar noi îi lăsăm pe alții să decidă în locul nostru. Este momentul să spunem răspicat: ajunge!",
        "Experții de la televizor ne explică zilnic ce trebuie să gândim. Dar câți dintre ei au muncit vreodată o zi într-o fabrică sau pe un câmp? Nu vă lăsați păcăliți de titluri și de diplome: adevărul se vede în buzunarele oamenilor.",
        "Vă reamintesc ce s-a întâmplat ultima dată când am ascultat de ei: prețuri dublate, spitale închise, tineri plecați din țară. Și totuși, aceiași oameni ne cer din nou încredere. Răspunsul nostru trebuie să fie clar.",
        "Iar cei care îi apără pe acești impostori sunt la fel de vinovați. Sunt niște incompetenți și niște lași, care nu merită niciun vot și niciun respect. Să le fie rușine!",
    ],
    "en": [
        "Let's be honest: nobody in the capital is thinking about ordinary people. The elites share out the posts and the money, and the rest of us pay the bill. For years we have been told to be patient, but our patience has run out.",
        "Who still believes official statements? We were promised growth, investment and jobs, and the reality in {city} shows the exact opposite. The figures are dressed up, and anyone asking awkward questions is immediately branded an enemy.",
        "History shows that nations which do not defend their identity disappear. Our ancestors fought for every inch of land, and we let others decide for us. It is time to say it loud and clear: enough!",
        "The so-called experts on television explain every day what we should think. But how many of them have ever worked a day in a factory or on a farm? Don't be fooled by titles and degrees: the truth shows in people's pockets.",
        "Remember what happened the last time we listened to them: prices doubled, hospitals closed, young people left the country. And yet the same people are asking for our trust again. Our answer has to be clear.",
        "And those who defend these frauds are just as guilty. They are incompetent cowards who deserve neither our votes nor our respect. Shame on them!",
    ],
    "ru": [
        "Будем честны: никто в столице не думает о простых людях. Элиты делят должности и деньги, а счёт оплачиваем мы. Нам годами говорят потерпеть, но наше терпение закончилось.",
        "Кто ещё верит официальным заявлениям? Цифры приукрашены, а тех, кто задаёт неудобные вопросы, сразу объявляют врагами. Западные партнёры молчат, потому что им это выгодно.",
        "История учит: народы, которые не защищают свою идентичность, исчезают. Пора сказать громко и ясно: хватит!",
    ],
    "uk": [
        "Будьмо чесними: ніхто у столиці не думає про простих людей. Еліти ділять посади й гроші, а рахунок оплачуємо ми. Нам роками кажуть потерпіти, але наше терпіння скінчилося.",
        "Історія вчить: народи, які не захищають свою ідентичність, зникають. Настав час сказати голосно і чітко: досить!",
    ],
}

FEATURE = {
    "ro": [
        "Centrul istoric din {city} s-a transformat în ultimii ani într-o destinație preferată de turiști. Cafenelele, galeriile și micile ateliere de artizanat atrag vizitatori din toată țara, iar ghizii locali spun că numărul turiștilor străini a crescut cu {pct}% față de anul trecut.",
        "Bucătăria tradițională rămâne unul dintre principalele motive pentru care oamenii revin. Restaurantele din zonă pun accent pe ingrediente locale, iar festivalurile gastronomice organizate în fiecare vară adună mii de participanți.",
        "Organizatorii spun că ediția din acest an va avea un program mai bogat, cu concerte, expoziții și ateliere pentru copii. Biletele pot fi cumpărate online, iar accesul la o parte dintre evenimente va fi gratuit.",
        "Pentru cei care preferă natura, împrejurimile oferă trasee montane bine marcate și peisaje spectaculoase. Salvamontiștii recomandă însă echipament adecvat și verificarea prognozei meteo înainte de plecare.",
    ],
    "en": [
        "In recent years the historic centre of {city} has become a favourite with tourists. Cafés, galleries and small craft workshops draw visitors from across the country, and local guides say foreign arrivals are up {pct}% on last year.",
        "Traditional food remains one of the main reasons people come back. Restaurants in the area focus on local ingredients, and the food festivals held every summer bring together thousands of visitors.",
        "Organisers say this year's edition will have a richer programme, with concerts, exhibitions and workshops for children. Tickets are on sale online, and some events will be free to attend.",
        "For those who prefer nature, the surroundings offer well-marked mountain trails and spectacular scenery. Mountain rescuers recommend proper equipment and checking the forecast before setting off.",
    ],
    "fr": ["Le centre historique de {city} attire de plus en plus de visiteurs. Cafés, galeries et ateliers d'artisans font le bonheur des touristes, dont le nombre a progressé de {pct}% en un an.",
           "La gastronomie locale reste l'un des principaux attraits de la région, avec des festivals qui réunissent chaque été des milliers de participants."],
    "de": ["Die Altstadt von {city} hat sich zu einem beliebten Reiseziel entwickelt. Cafés, Galerien und kleine Werkstätten ziehen Besucher an; die Zahl ausländischer Gäste stieg um {pct} Prozent.",
           "Für Naturliebhaber bietet die Umgebung gut markierte Wanderwege und spektakuläre Landschaften, so die örtlichen Bergretter."],
    "hu": ["{city} történelmi belvárosa az utóbbi években a turisták kedvelt célpontjává vált; a külföldi látogatók száma {pct}%-kal nőtt.",
           "A helyi gasztronómia továbbra is az egyik fő vonzerő, a nyári fesztiválok több ezer látogatót vonzanak."],
}
