"""Tests for SO101Controller, execute argv builders, and ACTPipeline CLI arg generation."""

import sys

from roboclaw.embodied.embodiment.arm.so101 import SO101Controller
from roboclaw.embodied.learning.act import ACTPipeline
from roboclaw.embodied.ops.execute import (
    _build_policy_argv,
    _build_record_argv,
    _build_replay_argv,
    _build_teleoperate_argv,
)

_FOLLOWER = {
    "type": "so101_follower",
    "port": "/dev/ttyACM0",
    "calibration_dir": "/cal/5B14032630",
    "alias": "right_follower",
}
_LEADER = {
    "type": "so101_leader",
    "port": "/dev/ttyACM1",
    "calibration_dir": "/cal/5B14030892",
    "alias": "left_leader",
}


def test_doctor_command() -> None:
    argv = SO101Controller().doctor()
    assert argv[0] == "python3"
    assert "import lerobot" in argv[2]


def test_calibrate_follower() -> None:
    argv = SO101Controller().calibrate(
        "so101_follower",
        "/dev/ttyACM0",
        "/cal/follower",
        "5B14032630",
    )
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "calibrate"]
    assert "--robot.type=so101_follower" in argv
    assert "--robot.id=5B14032630" in argv
    assert "--robot.port=/dev/ttyACM0" in argv
    assert any("--robot.calibration_dir=" in arg for arg in argv)


def test_calibrate_leader() -> None:
    argv = SO101Controller().calibrate(
        "so101_leader",
        "/dev/ttyACM1",
        "/cal/leader",
        "5B14030892",
    )
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "calibrate"]
    assert "--teleop.type=so101_leader" in argv
    assert "--teleop.id=5B14030892" in argv
    assert "--teleop.port=/dev/ttyACM1" in argv
    assert any("--teleop.calibration_dir=" in arg for arg in argv)


def test_teleoperate() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_teleoperate_argv(robot_argv, None)
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "teleoperate"]
    assert "--robot.type=so101_follower" in argv
    assert "--robot.id=5B14032630" in argv
    assert "--teleop.type=so101_leader" in argv
    assert "--teleop.id=5B14030892" in argv


def test_teleoperate_with_cameras() -> None:
    controller = SO101Controller()
    cameras = {"front": {"type": "opencv", "index": 0}}
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_teleoperate_argv(robot_argv, cameras)
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "teleoperate"]
    assert any("--robot.cameras=" in arg for arg in argv)


def test_teleoperate_bimanual() -> None:
    controller = SO101Controller()
    robot_argv = controller.bimanual_robot_argv(
        robot_id="bimanual",
        robot_cal_dir="/cal/robot",
        left_robot={"port": "/dev/a"},
        right_robot={"port": "/dev/b"},
        teleop_id="bimanual",
        teleop_cal_dir="/cal/teleop",
        left_teleop={"port": "/dev/c"},
        right_teleop={"port": "/dev/d"},
    )
    argv = _build_teleoperate_argv(robot_argv, None)
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "teleoperate"]
    assert "--robot.id=bimanual" in argv
    assert "--robot.calibration_dir=/cal/robot" in argv
    assert "--teleop.id=bimanual" in argv
    assert "--teleop.calibration_dir=/cal/teleop" in argv
    assert "--robot.left_arm_config.port=/dev/a" in argv
    assert "--robot.right_arm_config.port=/dev/b" in argv
    assert "--teleop.left_arm_config.port=/dev/c" in argv
    assert "--teleop.right_arm_config.port=/dev/d" in argv
    assert not any(".left_arm_config.calibration_dir=" in arg for arg in argv)
    assert not any(".right_arm_config.calibration_dir=" in arg for arg in argv)


def test_record() -> None:
    cameras = {"front": {"type": "opencv", "index": 0}}
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, cameras, {
        "repo_id": "local/test_data",
        "task": "pick and place",
        "dataset_root": "/data",
        "push_to_hub": False,
        "fps": 30,
        "num_episodes": 5,
    })
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "record"]
    assert "--robot.type=so101_follower" in argv
    assert "--robot.id=5B14032630" in argv
    assert "--teleop.type=so101_leader" in argv
    assert "--teleop.id=5B14030892" in argv
    assert any("--robot.cameras=" in arg for arg in argv)
    assert "--dataset.repo_id=local/test_data" in argv
    assert "--dataset.root=/data" in argv
    assert "--dataset.push_to_hub=false" in argv
    assert "--dataset.single_task=pick and place" in argv
    assert "--dataset.fps=30" in argv
    assert "--dataset.num_episodes=5" in argv


def test_record_with_episode_time_s() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, {}, {
        "repo_id": "local/test",
        "task": "grasp",
        "dataset_root": "/data",
        "episode_time_s": 60,
    })
    assert "--dataset.episode_time_s=60" in argv


def test_record_omits_episode_time_s_when_none() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, {}, {
        "repo_id": "local/test",
        "task": "grasp",
        "dataset_root": "/data",
    })
    assert not any("episode_time_s" in arg for arg in argv)


def test_record_skips_empty_cameras() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, {}, {
        "repo_id": "local/test_data",
        "task": "pick and place",
        "dataset_root": "/data",
    })
    assert not any("--robot.cameras=" in arg for arg in argv)


def test_record_bimanual_uses_per_arm_cameras() -> None:
    cameras = {"front": {"type": "opencv", "index": 0}}
    controller = SO101Controller()
    robot_argv = controller.bimanual_robot_argv(
        robot_id="bimanual",
        robot_cal_dir="/cal/robot",
        left_robot={"port": "/dev/a"},
        right_robot={"port": "/dev/b"},
        teleop_id="bimanual",
        teleop_cal_dir="/cal/teleop",
        left_teleop={"port": "/dev/c"},
        right_teleop={"port": "/dev/d"},
        cameras=cameras,
    )
    argv = _build_record_argv(robot_argv, None, {
        "repo_id": "local/test_data",
        "task": "pick and place",
        "dataset_root": "/data",
        "push_to_hub": False,
        "fps": 30,
        "num_episodes": 5,
    })
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "record"]
    assert "--dataset.root=/data" in argv
    assert "--dataset.push_to_hub=false" in argv
    assert not any(arg.startswith("--robot.cameras=") for arg in argv)
    assert any(arg.startswith("--robot.left_arm_config.cameras=") for arg in argv)
    assert not any(arg.startswith("--robot.right_arm_config.cameras=") for arg in argv)


def test_replay() -> None:
    controller = SO101Controller()
    robot_argv = controller.follower_only_argv(_FOLLOWER)
    argv = _build_replay_argv(robot_argv, "local/test_data", "/data", 3, 30)
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "replay"]
    assert "--robot.type=so101_follower" in argv
    assert "--robot.id=5B14032630" in argv
    assert "--dataset.repo_id=local/test_data" in argv
    assert "--dataset.root=/data" in argv
    assert "--dataset.episode=3" in argv


def test_replay_bimanual() -> None:
    controller = SO101Controller()
    robot_argv = controller.bimanual_follower_only_argv(
        robot_id="bimanual",
        robot_cal_dir="/cal/robot",
        left_robot={"port": "/dev/a"},
        right_robot={"port": "/dev/b"},
    )
    argv = _build_replay_argv(robot_argv, "local/test_data", "/data", 1, 30)
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "replay"]
    assert "--robot.id=bimanual" in argv
    assert "--robot.calibration_dir=/cal/robot" in argv
    assert "--robot.left_arm_config.port=/dev/a" in argv
    assert "--robot.right_arm_config.port=/dev/b" in argv
    assert "--dataset.root=/data" in argv
    assert "--dataset.episode=1" in argv


def test_run_policy() -> None:
    cameras = {"front": {"type": "opencv", "index": 0}}
    controller = SO101Controller()
    robot_argv = controller.follower_only_argv(_FOLLOWER)
    argv = _build_policy_argv(
        robot_argv, cameras,
        policy_path="/models/act_checkpoint",
        repo_id="local/eval",
        dataset_root="",
        task="eval",
        num_episodes=1,
    )
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "record"]
    assert "--robot.type=so101_follower" in argv
    assert "--robot.id=5B14032630" in argv
    assert any("--policy.path=" in arg for arg in argv)
    assert any("--robot.cameras=" in arg for arg in argv)
    assert not any("--teleop" in arg for arg in argv)


def test_run_policy_bimanual() -> None:
    cameras = {"front": {"type": "opencv", "index": 0}}
    controller = SO101Controller()
    robot_argv = controller.bimanual_follower_only_argv(
        robot_id="bimanual",
        robot_cal_dir="/cal/robot",
        left_robot={"port": "/dev/a"},
        right_robot={"port": "/dev/b"},
        cameras=cameras,
    )
    argv = _build_policy_argv(
        robot_argv, None,
        policy_path="/models/act_checkpoint",
        repo_id="local/eval",
        dataset_root="",
        task="eval",
        num_episodes=1,
    )
    assert argv[:4] == [sys.executable, "-m", "roboclaw.embodied.lerobot_wrapper", "record"]
    assert "--robot.type=bi_so_follower" in argv
    assert "--robot.id=bimanual" in argv
    assert "--robot.calibration_dir=/cal/robot" in argv
    assert "--robot.left_arm_config.port=/dev/a" in argv
    assert "--robot.right_arm_config.port=/dev/b" in argv
    assert any("--policy.path=" in arg for arg in argv)
    assert any("--robot.left_arm_config.cameras=" in arg for arg in argv)
    assert not any("--teleop" in arg for arg in argv)


def test_run_policy_skips_empty_cameras() -> None:
    controller = SO101Controller()
    robot_argv = controller.follower_only_argv(_FOLLOWER)
    argv = _build_policy_argv(
        robot_argv, {},
        policy_path="/models/act_checkpoint",
        repo_id="local/eval",
        dataset_root="",
        task="eval",
        num_episodes=1,
    )
    assert not any("--robot.cameras=" in arg for arg in argv)


def test_train() -> None:
    argv = ACTPipeline().train(
        repo_id="local/test_data",
        dataset_root="/data",
        output_dir="/output",
        steps=50000,
        device="cuda",
    )
    assert "lerobot-train" in argv
    assert "--dataset.repo_id=local/test_data" in argv
    assert "--dataset.root=/data" in argv
    assert "--policy.type=act" in argv
    assert "--policy.push_to_hub=false" in argv
    assert "--policy.repo_id=local/test_data" in argv
    assert "--steps=50000" in argv
    assert "--policy.device=cuda" in argv


def test_checkpoint_path() -> None:
    path = ACTPipeline().checkpoint_path("/output")
    assert "checkpoints/last/pretrained_model" in path


def test_record_with_resume() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, {}, {
        "repo_id": "local/test",
        "task": "grasp",
        "dataset_root": "/data",
        "resume": True,
    })
    assert "--resume=true" in argv


def test_record_without_resume() -> None:
    controller = SO101Controller()
    robot_argv = controller.robot_argv(_FOLLOWER, _LEADER)
    argv = _build_record_argv(robot_argv, {}, {
        "repo_id": "local/test",
        "task": "grasp",
        "dataset_root": "/data",
    })
    assert "--resume=true" not in argv


def test_run_policy_with_resume() -> None:
    controller = SO101Controller()
    robot_argv = controller.follower_only_argv(_FOLLOWER)
    argv = _build_policy_argv(
        robot_argv, {},
        policy_path="/models/act",
        repo_id="local/eval",
        dataset_root="",
        task="eval",
        num_episodes=1,
        resume=True,
    )
    assert "--resume=true" in argv


def test_run_policy_without_resume() -> None:
    controller = SO101Controller()
    robot_argv = controller.follower_only_argv(_FOLLOWER)
    argv = _build_policy_argv(
        robot_argv, {},
        policy_path="/models/act",
        repo_id="local/eval",
        dataset_root="",
        task="eval",
        num_episodes=1,
    )
    assert "--resume=true" not in argv
