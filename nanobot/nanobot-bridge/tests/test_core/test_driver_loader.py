import pytest
from bridge_core.driver_loader import DriverLoader


class TestDriverLoader:
    def test_load_driver_from_file(self, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        loader = DriverLoader(tmp_workspace / "drivers")
        driver = loader.load("test_arm")
        assert driver.name == "test_arm"
        assert "get_joints" in driver.methods

    def test_load_nonexistent_driver_raises(self, tmp_workspace):
        loader = DriverLoader(tmp_workspace / "drivers")
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")

    def test_load_driver_missing_class_raises(self, tmp_workspace):
        (tmp_workspace / "drivers" / "bad.py").write_text("x = 1")
        loader = DriverLoader(tmp_workspace / "drivers")
        with pytest.raises(AttributeError, match="Driver"):
            loader.load("bad")

    def test_reload_driver_picks_up_changes(self, tmp_workspace, sample_driver_code):
        path = tmp_workspace / "drivers" / "test_arm.py"
        path.write_text(sample_driver_code)
        loader = DriverLoader(tmp_workspace / "drivers")
        d1 = loader.load("test_arm")
        assert d1.description == "Test robot arm"

        path.write_text(sample_driver_code.replace("Test robot arm", "Updated arm"))
        d2 = loader.load("test_arm", reload=True)
        assert d2.description == "Updated arm"

    def test_list_available_drivers(self, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "arm_a.py").write_text(sample_driver_code)
        (tmp_workspace / "drivers" / "arm_b.py").write_text(sample_driver_code)
        (tmp_workspace / "drivers" / "not_python.txt").write_text("nope")
        loader = DriverLoader(tmp_workspace / "drivers")
        names = loader.list_available()
        assert set(names) == {"arm_a", "arm_b"}

    def test_loaded_drivers_persist(self, tmp_workspace, sample_driver_code):
        (tmp_workspace / "drivers" / "test_arm.py").write_text(sample_driver_code)
        loader = DriverLoader(tmp_workspace / "drivers")
        loader.load("test_arm")
        assert "test_arm" in loader.loaded
        assert loader.loaded["test_arm"].name == "test_arm"
