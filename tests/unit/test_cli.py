"""
Bloque 6 — tests/unit/test_cli.py

Cubre los 6 comandos CLI usando typer.testing.CliRunner.
Cada test mockea los servicios (ya cubiertos en Block 4) para
enfocarse en el comportamiento propio de la capa CLI:
exit codes, manejo de excepciones y paso correcto de argumentos.
"""

import types
from pathlib import Path

from typer.testing import CliRunner

from loom.cli.cli import app
from loom.core.exceptions import (
    AgentAlreadyExistsError,
    AgentConfigError,
    AgentNotFoundError,
    NoAgentsFoundError,
    ProjectAlreadyInitializedError,
    ProjectNotInitializedError,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# loom init
# ---------------------------------------------------------------------------


class TestCliInit:
    """CLI-I01 a CLI-I03"""

    def test_init_exitoso_retorna_exit_0(self, mocker, tmp_path):
        """CLI-I01: init sin proyecto existente → exit 0"""
        mocker.patch(
            "loom.cli.commands.init.build_workspace_paths",
            return_value=types.SimpleNamespace(project_root=tmp_path),
        )
        mocker.patch("loom.cli.commands.init.init_project", return_value=[tmp_path / "loom.toml"])
        mocker.patch("loom.cli.commands.init.show_preview_project")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0

    def test_init_proyecto_ya_existe_retorna_exit_1(self, mocker, tmp_path):
        """CLI-I02: proyecto ya existe → warning y exit 1"""
        mocker.patch(
            "loom.cli.commands.init.build_workspace_paths",
            return_value=types.SimpleNamespace(project_root=tmp_path),
        )
        mocker.patch(
            "loom.cli.commands.init.init_project",
            side_effect=ProjectAlreadyInitializedError("ya existe"),
        )

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 1

    def test_init_force_pasa_force_true_al_servicio(self, mocker, tmp_path):
        """CLI-I03: --force → init_project llamado con force=True"""
        mocker.patch(
            "loom.cli.commands.init.build_workspace_paths",
            return_value=types.SimpleNamespace(project_root=tmp_path),
        )
        mock_init = mocker.patch("loom.cli.commands.init.init_project", return_value=[])
        mocker.patch("loom.cli.commands.init.show_preview_project")

        runner.invoke(app, ["init", "--force"])

        _, call_kwargs = mock_init.call_args
        assert call_kwargs.get("force") is True


# ---------------------------------------------------------------------------
# loom agent new
# ---------------------------------------------------------------------------


class TestCliNew:
    """CLI-N01 a CLI-N04"""

    def test_new_con_nombre_retorna_exit_0(self, mocker, tmp_path):
        """CLI-N01: 'loom agent new mi_agente' → crea agente y exit 0"""
        mocker.patch(
            "loom.cli.commands.new.build_workspace_paths",
            return_value=types.SimpleNamespace(agent_dir=lambda n: tmp_path / n),
        )
        mocker.patch("loom.cli.commands.new.create_agent", return_value=[])
        mocker.patch("loom.cli.commands.new.show_preview_agent")

        result = runner.invoke(app, ["agent", "new", "mi_agente"])

        assert result.exit_code == 0

    def test_new_sin_nombre_retorna_exit_1(self, mocker):
        """CLI-N02: sin argumento name → error y exit 1"""
        result = runner.invoke(app, ["agent", "new"])

        assert result.exit_code == 1

    def test_new_proyecto_no_inicializado_retorna_exit_1(self, mocker, tmp_path):
        """CLI-N03: proyecto no inicializado → ProjectNotInitializedError → exit 1"""
        mocker.patch(
            "loom.cli.commands.new.build_workspace_paths",
            return_value=types.SimpleNamespace(agent_dir=lambda n: tmp_path / n),
        )
        mocker.patch(
            "loom.cli.commands.new.create_agent",
            side_effect=ProjectNotInitializedError("no init"),
        )

        result = runner.invoke(app, ["agent", "new", "mi_agente"])

        assert result.exit_code == 1

    def test_new_agente_duplicado_retorna_exit_1(self, mocker, tmp_path):
        """CLI-N04: agente ya existe → AgentAlreadyExistsError → exit 1"""
        mocker.patch(
            "loom.cli.commands.new.build_workspace_paths",
            return_value=types.SimpleNamespace(agent_dir=lambda n: tmp_path / n),
        )
        mocker.patch(
            "loom.cli.commands.new.create_agent",
            side_effect=AgentAlreadyExistsError("ya existe"),
        )

        result = runner.invoke(app, ["agent", "new", "mi_agente"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# loom agent list
# ---------------------------------------------------------------------------


class TestCliList:
    """CLI-L01 a CLI-L03"""

    def test_list_con_agentes_retorna_exit_0(self, mocker):
        """CLI-L01: agentes existen → renderiza tabla y exit 0"""
        from loom.schemas.config.agent_summary import AgentSummary

        mocker.patch(
            "loom.cli.commands.list.get_all_agents",
            return_value=[AgentSummary(name="mi_agente")],
        )
        mocker.patch("loom.cli.commands.list.render_agents_table")

        result = runner.invoke(app, ["agent", "list"])

        assert result.exit_code == 0

    def test_list_proyecto_no_inicializado_retorna_exit_1(self, mocker):
        """CLI-L02: proyecto no inicializado → exit 1"""
        mocker.patch(
            "loom.cli.commands.list.get_all_agents",
            side_effect=ProjectNotInitializedError("no init"),
        )

        result = runner.invoke(app, ["agent", "list"])

        assert result.exit_code == 1

    def test_list_sin_agentes_retorna_exit_0(self, mocker):
        """CLI-L03: no hay agentes → NoAgentsFoundError → exit 0 (no es un error fatal)"""
        mocker.patch(
            "loom.cli.commands.list.get_all_agents",
            side_effect=NoAgentsFoundError("vacío"),
        )

        result = runner.invoke(app, ["agent", "list"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# loom agent view
# ---------------------------------------------------------------------------


class TestCliView:
    """CLI-V01 a CLI-V03"""

    def test_view_agente_valido_retorna_exit_0(self, mocker, tmp_path):
        """CLI-V01: agente válido → renderiza YAML y exit 0"""
        yaml_path = tmp_path / "agent.yml"
        mocker.patch(
            "loom.cli.commands.view.get_agent_by_name",
            return_value=("name: mi_agente\n", yaml_path),
        )
        mocker.patch("loom.cli.commands.view.render_agent_yaml")

        result = runner.invoke(app, ["agent", "view", "mi_agente"])

        assert result.exit_code == 0

    def test_view_agente_no_encontrado_retorna_exit_1(self, mocker):
        """CLI-V02: agente no existe → NoAgentsFoundError → exit 1"""
        mocker.patch(
            "loom.cli.commands.view.get_agent_by_name",
            side_effect=NoAgentsFoundError("no existe"),
        )

        result = runner.invoke(app, ["agent", "view", "fantasma"])

        assert result.exit_code == 1

    def test_view_agente_sin_config_retorna_exit_1(self, mocker):
        """CLI-V03: agente sin YAML de config → AgentConfigError → exit 1"""
        mocker.patch(
            "loom.cli.commands.view.get_agent_by_name",
            side_effect=AgentConfigError("sin config"),
        )

        result = runner.invoke(app, ["agent", "view", "roto"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# loom agent remove
# ---------------------------------------------------------------------------


class TestCliRemove:
    """CLI-R01 a CLI-R03"""

    def test_remove_con_force_elimina_agente_y_exit_0(self, mocker):
        """CLI-R01: --force → delete_agent llamado y exit 0"""
        mock_delete = mocker.patch("loom.cli.commands.remove.delete_agent")

        result = runner.invoke(app, ["agent", "remove", "--force", "mi_agente"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("mi_agente")

    def test_remove_agente_no_encontrado_retorna_exit_1(self, mocker):
        """CLI-R02: agente no existe → NoAgentsFoundError → exit 1"""
        mocker.patch(
            "loom.cli.commands.remove.delete_agent",
            side_effect=NoAgentsFoundError("no existe"),
        )

        result = runner.invoke(app, ["agent", "remove", "--force", "fantasma"])

        assert result.exit_code == 1

    def test_remove_sin_force_muestra_confirmacion(self, mocker):
        """CLI-R03: sin --force → pide confirmación (simula 'y')"""
        mock_delete = mocker.patch("loom.cli.commands.remove.delete_agent")

        result = runner.invoke(app, ["agent", "remove", "mi_agente"], input="y\n")

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("mi_agente")


# ---------------------------------------------------------------------------
# loom agent run
# ---------------------------------------------------------------------------


class TestCliRun:
    """CLI-RU01 a CLI-RU02"""

    def test_run_error_al_cargar_agente_retorna_exit_1(self, mocker):
        """CLI-RU01: AgentNotFoundError al construir el agente → mensaje de error y exit 1"""

        mocker.patch(
            "loom.cli.commands.run.build_dev_agent",
            side_effect=AgentNotFoundError("roto"),
        )

        result = runner.invoke(app, ["agent", "run", "roto"])

        assert result.exit_code == 1

    def test_run_single_shot_llama_al_agente_y_exit_0(self, mocker):
        """CLI-RU02: -m 'mensaje' → ejecuta un turno vía run_turn y exit 0"""
        from loom.schemas.response import AgentResponse, AgentResponseMetadata

        mock_metadata = AgentResponseMetadata(
            session_id="s-1",
            user_id="cli",
            user_msg_idx=0,
            assistant_msg_idx=1,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            response_time_ms=100.0,
        )
        mock_response = AgentResponse(answer="respuesta del agente", metadata=mock_metadata)

        dev = mocker.Mock()
        dev.agent = mocker.Mock()
        mocker.patch("loom.cli.commands.run.build_dev_agent", return_value=dev)
        mock_run_turn = mocker.patch(
            "loom.cli.commands.run.run_turn", return_value=(mock_response, False)
        )
        mocker.patch("loom.cli.commands.run.console")

        result = runner.invoke(app, ["agent", "run", "-m", "hola", "mi_agente"])

        assert result.exit_code == 0
        mock_run_turn.assert_called_once()


# ---------------------------------------------------------------------------
# loom agent stats
# ---------------------------------------------------------------------------


class TestCliStats:
    """CLI-ST01 a CLI-ST04"""

    def _write_jsonl(self, path, records: list[dict]) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r) for r in records))

    def _mock_workspace_paths(self, tmp_path):
        import types

        return types.SimpleNamespace(
            agent_stats_file=lambda name: tmp_path / ".loom" / "stats" / f"{name}.jsonl"
        )

    def test_stats_sin_archivo_retorna_exit_0_y_warning(self, mocker, tmp_path):
        """CLI-ST01: no existe .loom/stats/{name}.jsonl → warning y exit 0"""
        mocker.patch(
            "loom.cli.commands.stats.build_workspace_paths",
            return_value=self._mock_workspace_paths(tmp_path),
        )

        result = runner.invoke(app, ["agent", "stats", "mi_agente"])

        assert result.exit_code == 0
        assert "No stats" in result.output

    def test_stats_con_registros_retorna_exit_0(self, mocker, tmp_path):
        """CLI-ST02: JSONL con registros válidos → muestra panel y exit 0"""
        mocker.patch(
            "loom.cli.commands.stats.build_workspace_paths",
            return_value=self._mock_workspace_paths(tmp_path),
        )
        stats_file = tmp_path / ".loom" / "stats" / "mi_agente.jsonl"
        self._write_jsonl(
            stats_file,
            [
                {
                    "ts": "2026-03-18T10:00:00+00:00",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "response_time_ms": 300.0,
                    "tool_calls": [],
                    "system_prompt_tokens": 200,
                },
            ],
        )

        result = runner.invoke(app, ["agent", "stats", "mi_agente"])

        assert result.exit_code == 0
        assert "mi_agente" in result.output
        assert "1" in result.output  # invocations

    def test_stats_agrega_multiples_registros(self, mocker, tmp_path):
        """CLI-ST03: dos registros → invocations=2, tokens sumados"""
        mocker.patch(
            "loom.cli.commands.stats.build_workspace_paths",
            return_value=self._mock_workspace_paths(tmp_path),
        )
        stats_file = tmp_path / ".loom" / "stats" / "mi_agente.jsonl"
        self._write_jsonl(
            stats_file,
            [
                {
                    "ts": "2026-03-18T10:00:00+00:00",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "response_time_ms": 200.0,
                    "tool_calls": ["search"],
                    "system_prompt_tokens": 100,
                },
                {
                    "ts": "2026-03-18T11:00:00+00:00",
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "total_tokens": 300,
                    "response_time_ms": 400.0,
                    "tool_calls": ["search", "db"],
                    "system_prompt_tokens": 100,
                },
            ],
        )

        result = runner.invoke(app, ["agent", "stats", "mi_agente"])

        assert result.exit_code == 0
        assert "2" in result.output  # invocations
        assert "450" in result.output  # total_tokens = 150 + 300

    def test_stats_muestra_top_tools(self, mocker, tmp_path):
        """CLI-ST04: tool_calls en registros → aparecen en la salida"""
        mocker.patch(
            "loom.cli.commands.stats.build_workspace_paths",
            return_value=self._mock_workspace_paths(tmp_path),
        )
        stats_file = tmp_path / ".loom" / "stats" / "mi_agente.jsonl"
        self._write_jsonl(
            stats_file,
            [
                {
                    "ts": "2026-03-18T10:00:00+00:00",
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "response_time_ms": 100.0,
                    "tool_calls": ["my_tool"],
                    "system_prompt_tokens": 0,
                },
            ],
        )

        result = runner.invoke(app, ["agent", "stats", "mi_agente"])

        assert result.exit_code == 0
        assert "my_tool" in result.output


# ---------------------------------------------------------------------------
# loom agent validate
# ---------------------------------------------------------------------------


class TestCliValidate:
    """CLI-VA01 a CLI-VA03"""

    def test_validate_todos_ok_retorna_exit_0(self, mocker):
        """CLI-VA01: validate_agent retorna todos ok=True → exit 0"""
        from loom.services.agent_service import ValidationResult

        mocker.patch(
            "loom.cli.commands.validate.validate_agent",
            return_value=[
                ValidationResult(ok=True, message="YAML schema válido"),
                ValidationResult(ok=True, message="Prompt encontrado"),
            ],
        )
        mocker.patch("loom.cli.commands.validate.render_agent_validation")

        result = runner.invoke(app, ["agent", "validate", "my_agent"])

        assert result.exit_code == 0

    def test_validate_con_errores_retorna_exit_1(self, mocker):
        """CLI-VA02: validate_agent retorna algún ok=False → exit 1"""
        from loom.services.agent_service import ValidationResult

        mocker.patch(
            "loom.cli.commands.validate.validate_agent",
            return_value=[
                ValidationResult(ok=True, message="YAML schema válido"),
                ValidationResult(ok=False, message="Prompt no encontrado", tip="Crea el archivo"),
            ],
        )
        mocker.patch("loom.cli.commands.validate.render_agent_validation")

        result = runner.invoke(app, ["agent", "validate", "broken_agent"])

        assert result.exit_code == 1

    def test_validate_excepcion_inesperada_retorna_exit_1(self, mocker):
        """CLI-VA03: validate_agent lanza excepción → mensaje de error y exit 1"""
        mocker.patch(
            "loom.cli.commands.validate.validate_agent",
            side_effect=RuntimeError("fallo inesperado"),
        )

        result = runner.invoke(app, ["agent", "validate", "crash_agent"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# loom agent copy
# ---------------------------------------------------------------------------


class TestCliCopy:
    """CLI-CP01 a CLI-CP03"""

    def test_copy_exitoso_retorna_exit_0(self, mocker):
        """CLI-CP01: copy_agent exitoso → exit 0 con mensaje de éxito"""
        mocker.patch(
            "loom.cli.commands.copy.copy_agent",
            return_value=[Path("/tmp/f1.yml"), Path("/tmp/f2.py")],
        )

        result = runner.invoke(app, ["agent", "copy", "src", "dst"])

        assert result.exit_code == 0
        assert "src" in result.output
        assert "dst" in result.output

    def test_copy_origen_no_encontrado_retorna_exit_1(self, mocker):
        """CLI-CP02: origen no existe → NoAgentsFoundError → exit 1"""
        mocker.patch(
            "loom.cli.commands.copy.copy_agent",
            side_effect=NoAgentsFoundError("not found"),
        )

        result = runner.invoke(app, ["agent", "copy", "ghost", "new"])

        assert result.exit_code == 1

    def test_copy_destino_ya_existe_retorna_exit_1(self, mocker):
        """CLI-CP03: destino ya existe → AgentAlreadyExistsError → exit 1"""
        mocker.patch(
            "loom.cli.commands.copy.copy_agent",
            side_effect=AgentAlreadyExistsError("already exists"),
        )

        result = runner.invoke(app, ["agent", "copy", "src", "dup"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# loom version
# ---------------------------------------------------------------------------


class TestCliVersion:
    """CLI-VER01"""

    def test_version_retorna_exit_0(self):
        """CLI-VER01: loom version → exit 0 y muestra tabla"""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# loom doctor
# ---------------------------------------------------------------------------


class TestCliDoctor:
    """CLI-DR01 a CLI-DR03"""

    def test_doctor_todos_ok_retorna_exit_0(self, mocker):
        """CLI-DR01: run_doctor retorna secciones sin errores → exit 0"""
        from loom.services.agent_service import ValidationResult

        mocker.patch(
            "loom.cli.commands.doctor.run_doctor",
            return_value={
                "system": [ValidationResult(ok=True, message="Python 3.14.0")],
                "aws": [],
                "project": [ValidationResult(ok=True, message="loom.toml found")],
                "agents": [],
            },
        )
        mocker.patch("loom.cli.commands.doctor.render_doctor")

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0

    def test_doctor_con_errores_retorna_exit_1(self, mocker):
        """CLI-DR02: run_doctor retorna algún ok=False → exit 1"""
        from loom.services.agent_service import ValidationResult

        mocker.patch(
            "loom.cli.commands.doctor.run_doctor",
            return_value={
                "system": [ValidationResult(ok=True, message="Python 3.14.0")],
                "aws": [],
                "project": [
                    ValidationResult(ok=False, message="loom.toml not found", tip="loom init"),
                ],
                "agents": [],
            },
        )
        mocker.patch("loom.cli.commands.doctor.render_doctor")

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 1

    def test_doctor_no_aws_pasa_check_aws_false(self, mocker):
        """CLI-DR03: --no-aws → run_doctor llamado con check_aws=False"""

        mock_run = mocker.patch(
            "loom.cli.commands.doctor.run_doctor",
            return_value={"system": [], "aws": [], "project": [], "agents": []},
        )
        mocker.patch("loom.cli.commands.doctor.render_doctor")

        runner.invoke(app, ["doctor", "--no-aws"])

        mock_run.assert_called_once_with(check_aws=False)
