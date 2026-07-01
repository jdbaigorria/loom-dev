"""
Bloque 2 — tests/unit/test_utils.py

Cubre: get_project_root(), load_yml(), load_toml(), apply_template(), WorkspacePaths.
"""

import warnings
from pathlib import Path

import pytest

from loom.core.paths import WorkspacePaths
from loom.utils.loaders import get_project_root, load_toml, load_yml
from loom.utils.render import apply_template

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def make_loom_paths(monkeypatch, root: Path) -> WorkspacePaths:
    """Instancia ``WorkspacePaths`` con LOOM_ROOT apuntando a ``root``."""
    monkeypatch.setenv("LOOM_ROOT", str(root))
    return WorkspacePaths(project_root=root, workspace_name="warp")


# ---------------------------------------------------------------------------
# get_project_root()
# ---------------------------------------------------------------------------


class TestGetProjectRoot:
    """UTL-01 a UTL-05"""

    def test_loom_root_env_tiene_precedencia_sobre_todo(self, monkeypatch, tmp_path):
        """UTL-01: LOOM_ROOT devuelve esa ruta sin buscar marcadores"""
        monkeypatch.setenv("LOOM_ROOT", str(tmp_path))
        assert get_project_root() == tmp_path.resolve()

    def test_encuentra_raiz_por_loom_toml_en_cwd(self, monkeypatch, tmp_path):
        """UTL-02: detecta la raíz cuando loom.toml existe en el directorio actual"""
        monkeypatch.delenv("LOOM_ROOT", raising=False)
        (tmp_path / "loom.toml").write_text("[workspace]\nname = 'test'")
        monkeypatch.chdir(tmp_path)
        assert get_project_root() == tmp_path

    def test_encuentra_raiz_por_loom_toml_en_directorio_padre(self, monkeypatch, tmp_path):
        """UTL-03: detecta loom.toml en un directorio padre (búsqueda ascendente)"""
        monkeypatch.delenv("LOOM_ROOT", raising=False)
        (tmp_path / "loom.toml").write_text("[workspace]\nname = 'test'")
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert get_project_root() == tmp_path

    def test_encuentra_raiz_por_directorio_loom(self, monkeypatch, tmp_path):
        """UTL-04: detecta la raíz cuando existe el directorio .loom/"""
        monkeypatch.delenv("LOOM_ROOT", raising=False)
        (tmp_path / ".loom").mkdir()
        monkeypatch.chdir(tmp_path)
        assert get_project_root() == tmp_path

    def test_emite_warning_cuando_no_hay_marcador(self, monkeypatch, tmp_path):
        """UTL-05: emite RuntimeWarning y retorna cwd si no encuentra ningún marcador"""
        monkeypatch.delenv("LOOM_ROOT", raising=False)
        # Directorio completamente vacío, sin ningún marcador ni pyproject.toml
        empty = tmp_path / "empty_project"
        empty.mkdir()
        monkeypatch.chdir(empty)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = get_project_root()
        assert result == empty
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 1
        assert "Loom Warning" in str(runtime_warnings[0].message)


# ---------------------------------------------------------------------------
# load_yml() / load_toml()
# ---------------------------------------------------------------------------


class TestLoadYml:
    """UTL-06"""

    def test_archivo_inexistente_levanta_file_not_found(self, tmp_path):
        """UTL-06: path que no existe → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_yml(tmp_path / "no_existe.yml")

    def test_yml_valido_retorna_dictconfig(self, tmp_path):
        """Bonus: YAML válido retorna objeto parseable"""
        yml = tmp_path / "config.yml"
        yml.write_text("name: test\nvalue: 42")
        result = load_yml(yml)
        assert result["name"] == "test"
        assert result["value"] == 42


class TestLoadToml:
    """UTL-07, UTL-08"""

    def test_archivo_inexistente_levanta_file_not_found(self, tmp_path):
        """UTL-07: path que no existe → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_toml(tmp_path / "no_existe.toml")

    def test_sintaxis_invalida_levanta_value_error(self, tmp_path):
        """UTL-08: TOML con sintaxis inválida → ValueError"""
        bad_toml = tmp_path / "broken.toml"
        bad_toml.write_text("este = no es : toml valido [[[")
        with pytest.raises(ValueError, match="Error loading toml config"):
            load_toml(bad_toml)

    def test_toml_valido_retorna_dict(self, tmp_path):
        """Bonus: TOML válido retorna dict con los valores correctos"""
        toml = tmp_path / "config.toml"
        toml.write_text('[workspace]\nname = "mi_proyecto"\n')
        result = load_toml(toml)
        assert result["workspace"]["name"] == "mi_proyecto"


# ---------------------------------------------------------------------------
# apply_template()
# ---------------------------------------------------------------------------


class TestApplyTemplate:
    """UTL-09 a UTL-14"""

    def _make_template(self, base: Path, files: dict) -> Path:
        """Helper: crea una estructura de plantilla en base/template/"""
        tpl_root = base / "template"
        tpl_root.mkdir()
        for rel_path, content in files.items():
            full = tpl_root / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        return tpl_root

    def test_j2_se_renderiza_y_pierde_extension(self, tmp_path):
        """UTL-09: archivo .j2 se renderiza con contexto y se guarda sin .j2"""
        tpl = self._make_template(tmp_path, {"hello.txt.j2": "Hola {{ nombre }}"})
        out = tmp_path / "output"
        out.mkdir()

        apply_template(tpl, out, {"nombre": "Mundo"})

        rendered = out / "hello.txt"
        assert rendered.exists()
        assert rendered.read_text() == "Hola Mundo"
        assert not (out / "hello.txt.j2").exists()

    def test_archivo_no_j2_se_copia_sin_modificar(self, tmp_path):
        """UTL-10: archivo sin .j2 se copia tal cual"""
        content = "contenido exacto del archivo"
        tpl = self._make_template(tmp_path, {"data.txt": content})
        out = tmp_path / "output"
        out.mkdir()

        apply_template(tpl, out, {})

        copied = out / "data.txt"
        assert copied.exists()
        assert copied.read_text() == content

    def test_nombre_de_directorio_con_jinja2_se_renderiza(self, tmp_path):
        """UTL-11: directorio con expresión Jinja2 en el nombre se crea con nombre real"""
        tpl = tmp_path / "template"
        dynamic_dir = tpl / "{{ folder_name }}"
        dynamic_dir.mkdir(parents=True)
        (dynamic_dir / "archivo.txt").write_text("contenido")

        out = tmp_path / "output"
        out.mkdir()

        apply_template(tpl, out, {"folder_name": "mi_agente"})

        assert (out / "mi_agente").is_dir()
        assert (out / "mi_agente" / "archivo.txt").exists()

    def test_force_false_lanza_error_si_directorio_destino_no_esta_vacio(self, tmp_path):
        """UTL-12: force=False + directorio folder_name existente y no vacío → FileExistsError"""
        tpl = self._make_template(tmp_path, {"archivo.txt": "contenido"})
        out = tmp_path / "output"
        out.mkdir()

        # Pre-crear el directorio destino con contenido
        existing = out / "mi_agente"
        existing.mkdir()
        (existing / "old_file.txt").write_text("ya existe")

        with pytest.raises(FileExistsError):
            apply_template(tpl, out, {"folder_name": "mi_agente"}, force=False)

    def test_force_true_sobreescribe_sin_error(self, tmp_path):
        """UTL-13: force=True ignora el directorio existente y no lanza error"""
        tpl = self._make_template(tmp_path, {"archivo.txt": "nuevo contenido"})
        out = tmp_path / "output"
        out.mkdir()

        existing = out / "mi_agente"
        existing.mkdir()
        (existing / "old_file.txt").write_text("ya existe")

        # No debe lanzar excepción
        apply_template(tpl, out, {"folder_name": "mi_agente"}, force=True)

    def test_retorna_lista_de_paths_creados(self, tmp_path):
        """UTL-14: el valor de retorno es una lista de Path no vacía"""
        tpl = self._make_template(
            tmp_path,
            {
                "config.txt.j2": "region: {{ region }}",
                "readme.txt": "README",
            },
        )
        out = tmp_path / "output"
        out.mkdir()

        result = apply_template(tpl, out, {"region": "us-east-1"})

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(p, Path) for p in result)


# ---------------------------------------------------------------------------
# WorkspacePaths
# ---------------------------------------------------------------------------


class TestWorkspacePaths:
    """UTL-15 a UTL-20"""

    def test_agent_dir_normaliza_espacios(self, monkeypatch, tmp_path):
        """UTL-15: nombre con espacios → directorio en snake_case"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        result = paths.agent_dir("My Agent")
        assert result.name == "my_agent"

    def test_agent_dir_normaliza_guiones(self, monkeypatch, tmp_path):
        """UTL-16: nombre con guiones → directorio en snake_case"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        result = paths.agent_dir("my-agent")
        assert result.name == "my_agent"

    def test_agent_dir_normaliza_mayusculas(self, monkeypatch, tmp_path):
        """UTL-17: nombre con mayúsculas → directorio en minúsculas"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        result = paths.agent_dir("MyAgent")
        assert result.name == "myagent"

    def test_resolve_agent_yaml_encuentra_yaml_canonico(self, monkeypatch, tmp_path):
        """UTL-18: encuentra config/{name}.yml en la ruta canónica"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        config_dir = paths.agent_config_dir("test_agent")
        config_dir.mkdir(parents=True)
        yaml_file = config_dir / "test_agent.yml"
        yaml_file.write_text("name: test_agent")

        result = paths.resolve_agent_yaml("test_agent")

        assert result == yaml_file

    def test_resolve_agent_yaml_encuentra_yaml_con_nombre_del_agente(self, monkeypatch, tmp_path):
        """UTL-19: encuentra config/{name}.yml cuando existe"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        config_dir = paths.agent_config_dir("test_agent")
        config_dir.mkdir(parents=True)
        yaml_file = config_dir / "test_agent.yml"
        yaml_file.write_text("name: test_agent")

        result = paths.resolve_agent_yaml("test_agent")

        assert result == yaml_file

    def test_resolve_agent_yaml_lanza_error_si_no_hay_yaml(self, monkeypatch, tmp_path):
        """UTL-20: sin ningún YAML → AgentNotFoundError"""
        from loom.core.exceptions import AgentNotFoundError

        paths = make_loom_paths(monkeypatch, tmp_path)
        config_dir = paths.agent_config_dir("test_agent")
        config_dir.mkdir(parents=True)
        # No creamos ningún archivo YAML

        with pytest.raises(AgentNotFoundError):
            paths.resolve_agent_yaml("test_agent")

    def test_agent_dir_apunta_dentro_de_agents_dir(self, monkeypatch, tmp_path):
        """Bonus: agent_dir retorna un path hijo de agents_dir"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        assert paths.agents_dir in paths.agent_dir("mi_agente").parents

    def test_shared_tools_dir_es_subdirectorio_de_agents_dir(self, monkeypatch, tmp_path):
        """Bonus: shared_tools_dir es agents_dir/tools"""
        paths = make_loom_paths(monkeypatch, tmp_path)
        assert paths.shared_tools_dir == paths.agents_dir / "tools"
