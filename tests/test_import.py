from living_adr import main


def test_package_imports() -> None:
    assert callable(main)
