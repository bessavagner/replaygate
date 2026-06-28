import replaygate


def test_package_imports_and_has_version():
    assert isinstance(replaygate.__version__, str)
    assert replaygate.__version__
