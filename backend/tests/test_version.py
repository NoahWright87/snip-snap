from app import version


def test_normalize_version_drops_v_prefix():
    assert version.normalize_version("v1.2.3") == "1.2.3"
    assert version.normalize_version("1.2.3") == "1.2.3"


def test_is_newer_version_handles_semver_numbers():
    assert version.is_newer_version("1.2.3", "1.2.4")
    assert version.is_newer_version("1.2", "1.2.1")
    assert not version.is_newer_version("1.2.0", "1.2")


def test_is_newer_version_falls_back_for_non_numeric_versions():
    assert version.is_newer_version("dev-build", "nightly-2")
    assert not version.is_newer_version("nightly-2", "nightly-2")

