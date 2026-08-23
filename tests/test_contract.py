from pathlib import Path

from context_maintainer import contract, scaffold


def test_all_required_paths_includes_seven_contract_files(tmp_path: Path):
    paths = contract.all_required_paths(tmp_path)
    # seven contract files plus the manifest
    assert len(paths) == 8
    names = {p.relative_to(tmp_path).as_posix() for p in paths}
    assert "AGENTS.md" in names
    assert "CLAUDE.md" in names
    assert "docs/context/PROJECT.md" in names
    assert contract.MANIFEST_PATH in names


def test_contract_defines_exactly_seven_files():
    assert len(contract.CONTRACT_FILES) == 7


def test_knowledge_documents_have_nonempty_required_sections():
    for contract_file in contract.CONTRACT_FILES:
        if contract_file.relative_path == "docs/context/DECISIONS.md":
            assert contract_file.requires_decision_entries
            continue
        if contract_file.relative_path == "CLAUDE.md":
            assert contract_file.requires_agents_import
            continue
        assert contract_file.required_sections, contract_file.relative_path


def test_every_contract_file_has_an_existing_template():
    for contract_file in contract.CONTRACT_FILES:
        assert (scaffold.TEMPLATES_DIR / contract_file.template_name).exists()


def test_templates_contain_their_required_sections():
    """The templates must satisfy the contract they are generated from."""
    from context_maintainer import mdsections

    for contract_file in contract.CONTRACT_FILES:
        if not contract_file.required_sections:
            continue
        text = scaffold.load_template(contract_file.template_name)
        headings = set(mdsections.list_headings(text))
        missing = [s for s in contract_file.required_sections if s not in headings]
        assert not missing, f"{contract_file.template_name} missing {missing}"


def test_context_document_paths_returns_five_knowledge_docs(tmp_path: Path):
    paths = contract.context_document_paths(tmp_path)
    assert len(paths) == 5
    assert all(p.parent.as_posix().endswith("docs/context") for p in paths)


def test_get_contract_file_finds_by_relative_path():
    found = contract.get_contract_file("docs/context/STATE.md")
    assert "Blockers" in found.required_sections
