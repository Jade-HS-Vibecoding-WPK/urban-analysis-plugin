"""Step 4 'Layer prüfen' (ARBEITSPLAN W5, part 1): grouped hints and confirmations."""

from urban_analysis.contracts import LayerDescriptor, PipelineResult, ValidationIssue
from urban_analysis.user_guidance import GuidedWorkflow, severity_label


def make_workflow(issues, layers=True):
    return GuidedWorkflow(
        PipelineResult(
            contract_version="1.0",
            project_crs="EPSG:25832",
            study_area_wkt="POLYGON ((0 0, 1 0, 1 1, 0 0))",
            layers=[LayerDescriptor("gebaeude", "gebaeude", "Polygon", "a.gpkg", category="Gebäude")]
            if layers
            else [],
            issues=issues,
        )
    )


def alkis_like_issues():
    return [
        ValidationIssue("clip-summary", "Layer gebaeude: 5297 von 107450 Objekten ...", severity="info"),
        ValidationIssue("crs-unverified", "CRS nicht eindeutig", requires_confirmation=True),
        ValidationIssue("uncertain-duplicate", "gebaeude: 693 Gruppe(n) ...", requires_confirmation=True),
        ValidationIssue("duplicate-row", "25 exakte Dublette(n) ..."),
        ValidationIssue("crs-mismatch", "Layer x verwendet EPSG:4326", severity="error"),
        ValidationIssue("missing-data-source", "Keine Datenquelle"),
    ]


def test_all_hints_including_infos_are_grouped_by_severity():
    groups = make_workflow(alkis_like_issues()).issues_by_severity()
    assert [i.code for i in groups["error"]] == ["crs-mismatch"]
    assert [i.code for i in groups["info"]] == ["clip-summary"]
    assert len(groups["warning"]) == 4


def test_unknown_severity_is_shown_as_warning_instead_of_disappearing():
    groups = make_workflow([ValidationIssue("x", "?", severity="notice")]).issues_by_severity()
    assert [i.code for i in groups["warning"]] == ["x"]


def test_uncertain_duplicates_are_decided_in_step_6_not_confirmed_in_step_4():
    flow = make_workflow(alkis_like_issues())
    assert [i.code for i in flow.open_review_confirmations()] == ["crs-unverified"]
    assert flow.has_uncertain_duplicates()


def test_confirming_sets_the_flag_on_the_hint_and_unblocks_the_step():
    flow = make_workflow(alkis_like_issues())
    assert "Noch 1 Hinweis bestätigen" in flow.review_blocker()

    hint = flow.open_review_confirmations()[0]
    flow.confirm_issue(hint, True)

    assert hint.confirmed is True
    assert flow.review_blocker() is None
    flow.confirm_issue(hint, False)
    assert hint.confirmed is False
    assert flow.review_blocker() is not None


def test_errors_only_block_when_no_data_is_left():
    assert make_workflow([ValidationIssue("crs-mismatch", "x", severity="error")]).review_blocker() is None
    blocked = make_workflow([ValidationIssue("no-feature-layers", "x", severity="error")])
    assert "keine verwendbaren Daten" in blocked.review_blocker()
    assert "keine verwendbaren Daten" in make_workflow([], layers=False).review_blocker()


def test_summary_line_counts_layers_and_hints_with_correct_grammar():
    text = make_workflow(alkis_like_issues()).review_summary_text()
    assert text == "1 Layer geladen · 1 Fehler · 4 Warnungen · 1 Info"
    assert severity_label("warning", 1) == "1 Warnung"
    assert severity_label("info", 0) == "0 Infos"


def test_same_objects_in_alkis_and_osm_are_decided_in_step_6():
    issue = ValidationIssue("cross-source-duplicate", "Gebäude: 841 Objekte …", severity="warning",
                            requires_confirmation=True)
    flow = make_workflow([issue])
    assert not flow.needs_review_confirmation(issue)
    assert flow.open_review_confirmations() == ()


def test_the_same_hint_from_several_sources_is_shown_once():
    from urban_analysis.user_guidance import merge_same_hints

    hints = [
        ValidationIssue("missing-source", "OpenStreetMap – Datenquelle fehlt: unbekannt.", severity="info"),
        ValidationIssue("other", "OpenStreetMap – Gebäude: 3 ohne Adresse.", severity="info"),
        ValidationIssue("missing-source", "ALKIS Niedersachsen – Datenquelle fehlt: unbekannt.",
                        severity="info"),
        ValidationIssue("plain", "Ohne Quelle davor.", severity="info"),
    ]
    merged = merge_same_hints(hints)
    assert [(text, len(members)) for text, members in merged] == [
        ("Datenquelle fehlt: unbekannt. (betrifft: OpenStreetMap, ALKIS Niedersachsen)", 2),
        ("OpenStreetMap – Gebäude: 3 ohne Adresse.", 1),
        ("Ohne Quelle davor.", 1),
    ]
