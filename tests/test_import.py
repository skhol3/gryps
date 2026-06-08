def test_import_gryps() -> None:
    import gryps
    assert hasattr(gryps, "__version__")
    assert gryps.__version__ == "0.1.0"
