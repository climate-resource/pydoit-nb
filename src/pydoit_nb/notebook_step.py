"""
Notebook-based step

A notebook-based step is the combination of a notebook and the configuration
to run it.
"""
from __future__ import annotations

import copy
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

from attrs import frozen

from pydoit_nb.config_handling import get_step_config_ids

from .typing import ConfigBundleLike, Converter, DoitTaskSpec

if TYPE_CHECKING:
    from .notebook import ConfiguredNotebook, UnconfiguredNotebook


C = TypeVar("C")
CB_contra = TypeVar("CB_contra", contravariant=True, bound=ConfigBundleLike[Any])


class ConfigureNotebooksCallable(Protocol[CB_contra]):
    """Callable that can be used for configuring notebooks"""

    def __call__(  # noqa: D102
        self,
        unconfigured_notebooks: Iterable[UnconfiguredNotebook],
        config_bundle: CB_contra,
        step_name: str,
        step_config_id: str,
    ) -> list[ConfiguredNotebook]:
        ...  # pragma: no cover


@frozen
class UnconfiguredNotebookBasedStep(Generic[C, CB_contra]):
    """
    An unconfigured notebook-based step

    A step is a step in the overall workflow. A notebook-based step can be made
    up of one or more notebooks. These are then configured at run-time with the
    run-time information so they can then be turned into doit task(s).
    """

    step_name: str
    """Name of the step"""

    unconfigured_notebooks: list[UnconfiguredNotebook]
    """Unconfigured notebooks that make up this step"""

    configure_notebooks: ConfigureNotebooksCallable[CB_contra]
    """Function which can configure the notebooks based on run-time information"""

    def gen_notebook_tasks(
        self,
        config_bundle: CB_contra,
        root_dir_raw_notebooks: Path,
        converter: Converter | None = None,
        clean: bool = True,
    ) -> Iterable[DoitTaskSpec]:
        """
        Generate notebook tasks for this step

        Parameters
        ----------
        config_bundle
            Configuration bundle to use when generating the tasks

        root_dir_raw_notebooks
            Root directory in which the raw notebooks live

        converter
            Instance that can serialise the configuration used by each notebook

        clean
            If we run `doit clean`, should the targets of each task be
            removed?

        Yields
        ------
            Task specifications for use with :mod:`doit`
        """
        unconfigured_notebooks = self.unconfigured_notebooks

        unconfigured_notebooks_base_tasks = {}
        for nb in unconfigured_notebooks:
            base_task = {
                "basename": f"({nb.notebook_path}) {nb.summary}",
                "name": None,
                "doc": nb.doc,
            }
            # yield copy of base task to avoid being mangled by doit
            yield copy.deepcopy(base_task)

            unconfigured_notebooks_base_tasks[nb.notebook_path] = base_task

        step_config_ids = get_step_config_ids(getattr(config_bundle.config_hydrated, self.step_name))

        notebook_output_dir_step = config_bundle.root_dir_output_run / "notebooks-executed" / self.step_name
        for step_config_id in step_config_ids:
            configured_notebooks = self.configure_notebooks(
                unconfigured_notebooks,
                config_bundle=config_bundle,
                step_name=self.step_name,
                step_config_id=step_config_id,
            )
            if len(unconfigured_notebooks) != len(configured_notebooks):
                msg = (
                    "The number of unconfigured and configured notebooks is not the same. "
                    "We haven't yet thought through this use case. "
                    "Please raise an issue at https://github.com/climate-resource/pydoit-nb to discuss."
                )
                raise NotImplementedError(msg)

            notebook_output_dir_step_id = notebook_output_dir_step / step_config_id

            for nb_configured in configured_notebooks:
                notebook_task = nb_configured.to_doit_task(
                    root_dir_raw_notebooks=root_dir_raw_notebooks,
                    notebook_output_dir=notebook_output_dir_step_id,
                    base_task=unconfigured_notebooks_base_tasks[
                        nb_configured.unconfigured_notebook.notebook_path
                    ],
                    converter=converter,
                    clean=clean,
                )

                yield notebook_task
