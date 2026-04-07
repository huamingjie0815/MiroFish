"""
Simulation manager regression tests.
"""

from app.services.simulation_manager import SimulationManager


def test_read_only_lookups_do_not_create_missing_simulation_dirs(tmp_path, monkeypatch):
    """Missing simulation IDs should not leave empty directories behind."""
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))

    manager = SimulationManager()
    missing_id = "sim_missing"
    missing_dir = tmp_path / "simulations" / missing_id

    assert manager.get_simulation(missing_id) is None
    assert manager.get_simulation_config(missing_id) is None
    assert not missing_dir.exists()


def test_create_simulation_still_creates_storage_dir(tmp_path, monkeypatch):
    """Write paths should still materialize the simulation directory."""
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))

    manager = SimulationManager()
    state = manager.create_simulation(project_id="proj_1", graph_id="graph_1")

    assert (tmp_path / "simulations" / state.simulation_id).is_dir()
    assert manager.get_simulation(state.simulation_id) is not None
