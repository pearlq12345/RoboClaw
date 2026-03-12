import pytest
from sim_bridge.physics import PhysicsEngine
from tests.conftest import SO100_URDF, requires_urdf


class TestPhysicsEngine:
    @pytest.fixture
    def engine(self):
        e = PhysicsEngine(headless=True)
        yield e
        e.close()

    def test_create_headless(self, engine):
        assert engine.physics_client is not None

    def test_load_plane(self, engine):
        plane_id = engine.load_plane()
        assert plane_id >= 0

    @requires_urdf
    def test_load_so100_urdf(self, engine):
        engine.load_plane()
        robot_id = engine.load_urdf(SO100_URDF, base_position=[0, 0, 0])
        assert robot_id >= 0
        info = engine.get_robot_info(robot_id)
        assert info["num_joints"] > 0
        assert len(info["joint_names"]) > 0

    @requires_urdf
    def test_get_joint_positions(self, engine):
        engine.load_plane()
        robot_id = engine.load_urdf(SO100_URDF)
        joints = engine.get_joint_positions(robot_id)
        assert isinstance(joints, dict)
        assert len(joints) > 0
        # All initial positions should be near zero
        for name, val in joints.items():
            assert abs(val) < 0.01, f"Joint {name} not at zero: {val}"

    @requires_urdf
    def test_set_and_read_joints(self, engine):
        engine.load_plane()
        robot_id = engine.load_urdf(SO100_URDF)
        joints = engine.get_joint_positions(robot_id)
        first_joint = list(joints.keys())[0]

        engine.set_joint_positions(robot_id, {first_joint: 0.5})
        engine.step(steps=240)  # 1 second at 240Hz
        new_joints = engine.get_joint_positions(robot_id)
        assert abs(new_joints[first_joint] - 0.5) < 0.15, (
            f"Joint {first_joint} didn't reach target: {new_joints[first_joint]}"
        )

    def test_step_simulation(self, engine):
        engine.load_plane()
        engine.step(steps=100)
        # Should not raise

    @requires_urdf
    def test_reset(self, engine):
        engine.load_plane()
        robot_id = engine.load_urdf(SO100_URDF)
        assert len(engine._robots) == 1

        engine.reset()
        assert len(engine._robots) == 0

    @requires_urdf
    def test_multiple_robots(self, engine):
        engine.load_plane()
        r1 = engine.load_urdf(SO100_URDF, base_position=[0, 0, 0])
        r2 = engine.load_urdf(SO100_URDF, base_position=[1, 0, 0])
        assert r1 != r2
        assert len(engine._robots) == 2

        j1 = engine.get_joint_positions(r1)
        j2 = engine.get_joint_positions(r2)
        assert len(j1) == len(j2)
