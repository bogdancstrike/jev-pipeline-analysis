from app.modules.entity_resolution.resolver import EntityRegistry, loose_equal, normalize

GROUPS = {"person": ["person"], "organization": ["organization", "government agency"],
          "place": ["country", "city"]}


def span(text, label, start=0):
    return {"text": text, "label": label, "start": start, "end": start + len(text), "score": 0.9}


def reg():
    return EntityRegistry(GROUPS, aliases=[["European Union", "UE", "EU"]],
                          stopwords=("de", "a", "pentru"))


def test_normalize_folds_case_diacritics_and_punctuation():
    assert normalize("Bucureşti") == normalize("BUCUREȘTI") == "bucuresti"
    assert normalize("  The  N.A.T.O. ") == "n a t o"


def test_loose_equal_tolerates_inflection_not_different_words():
    assert loose_equal("romania", "romaniei")
    assert loose_equal("guvernul romaniei", "guvernului romania")
    assert not loose_equal("austria", "australia")
    assert not loose_equal("banca nationala", "banca")


def test_inflected_forms_and_aliases_merge_across_rows():
    r = reg()
    a = r.resolve_row(0, [span("România", "country"), span("UE", "organization", 20)])
    b = r.resolve_row(1, [span("României", "country"), span("European Union", "organization", 30)])
    assert a[0]["id"] == b[0]["id"] and a[1]["id"] == b[1]["id"]


def test_acronym_links_to_long_name_in_either_order():
    r = reg()
    a = r.resolve_row(0, [span("DNSC", "government agency")])
    b = r.resolve_row(1, [span("Directoratul Național de Securitate Cibernetică", "government agency")])
    results = [{"entities": a}, {"entities": b}]
    r.settle(results)
    assert results[0]["entities"][0]["id"] == results[1]["entities"][0]["id"]


def test_surname_resolves_within_a_row_only():
    r = reg()
    row = r.resolve_row(0, [span("Andrei Popescu", "person"), span("Popescu", "person", 40)])
    assert len(row) == 1 and row[0]["mentions"] == ["Andrei Popescu", "Popescu"]
    other = r.resolve_row(1, [span("Popescu", "person")])
    assert other[0]["id"] != row[0]["id"]


def test_people_with_similar_first_names_do_not_merge():
    r = reg()
    a = r.resolve_row(0, [span("Maria Ionescu", "person")])
    b = r.resolve_row(1, [span("Marian Ionescu", "person")])
    assert a[0]["id"] != b[0]["id"]


def test_unresolvable_labels_are_skipped():
    assert reg().resolve_row(0, [span("2027", "date")]) == []


def test_cyrillic_mentions_match_their_latin_spelling():
    r = EntityRegistry(GROUPS, aliases=[["Romania", "România", "Румунія"]])
    a = r.resolve_row(0, [span("Elena Marin", "person"), span("România", "country", 20)])
    b = r.resolve_row(1, [span("Елена Марін", "person"), span("Румунії", "country", 20)])  # genitive
    assert [e["id"] for e in a] == [e["id"] for e in b]


def test_titles_before_a_full_name_do_not_split_the_person():
    r = reg()
    a = r.resolve_row(0, [span("Andrei Popescu", "person")])
    b = r.resolve_row(1, [span("Finance Minister Andrei Popescu", "person")])
    results = [{"entities": a}, {"entities": b}]
    r.settle(results)
    assert results[0]["entities"][0]["id"] == results[1]["entities"][0]["id"]
    assert results[1]["entities"][0]["canonical"] == "Andrei Popescu"


def test_ignored_generic_mentions_are_dropped():
    r = EntityRegistry(GROUPS, ignore=("everyone",))
    assert r.resolve_row(0, [span("Everyone", "person")]) == []
