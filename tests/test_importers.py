from importers.run import transform
import pytest

def test_transform_defaults_and_types():
    assert transform('', {'default': 2, 'transform':'int'}) == 2
    assert transform(' YES ', {'transform':'bool'}) is True

def test_required_value_rejected():
    with pytest.raises(ValueError): transform('', {'required':True})
