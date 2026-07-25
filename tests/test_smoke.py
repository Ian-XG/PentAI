import pentai

def test_version_present():
    assert isinstance(pentai.__version__, str)
    assert pentai.__version__
